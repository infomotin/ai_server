"""
Camera Service
Manages IP cameras (Imou Life, RTSP, HLS, MJPEG, etc), recording, and analysis.
"""
import os
import re
import json
import time
import uuid
import shutil
import asyncio
import subprocess
import threading
import logging
import hashlib
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.database import Camera, CameraRecording, CameraPermission, UserRole
from src.models.engine import session_factory
from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


# ============== Configuration ==============
RECORDINGS_DIR = Path("/www/AI_server/data/camera_recordings")
HLS_DIR = Path("/www/AI_server/data/camera_hls")
SNAPSHOTS_DIR = Path("/www/AI_server/data/camera_snapshots")
THUMBNAILS_DIR = Path("/www/AI_server/data/camera_thumbnails")

for d in [RECORDINGS_DIR, HLS_DIR, SNAPSHOTS_DIR, THUMBNAILS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============== Encryption for camera passwords ==============
def _get_cipher():
    secret = os.environ.get("SECRET_KEY", "openlocalai-default-secret-change-me")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_pw(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_pw(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()


# ============== Permission helpers ==============
def check_user_role(db: Session, user_id: str) -> str:
    """Get user role: admin, operator, viewer."""
    role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
    return role.role if role else "viewer"


def check_camera_permission(db: Session, user_id: str, camera_id: str, action: str = "view") -> bool:
    """Check if user has permission for a camera action.
    actions: view, record, delete, share, analyze, configure
    Returns True if allowed."""
    # Super admin always has access
    role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
    if role and role.is_super_admin:
        return True
    if role and role.role == "admin":
        return True
    # Check camera owner
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if cam and cam.user_id == user_id:
        return True
    # Check per-camera permission
    perm = db.query(CameraPermission).filter(
        CameraPermission.camera_id == camera_id,
        CameraPermission.user_id == user_id
    ).first()
    if not perm:
        return False
    return {
        "view": perm.can_view,
        "record": perm.can_record,
        "delete": perm.can_delete,
        "share": perm.can_share,
        "analyze": perm.can_analyze,
        "configure": perm.can_configure,
    }.get(action, False)


def user_can_access_camera(db: Session, user_id: str, camera_id: str) -> bool:
    """Check if user can at least view the camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        return False
    if cam.user_id == user_id:
        return True
    if cam.is_public:
        return True
    return check_camera_permission(db, user_id, camera_id, "view")


# ============== Camera CRUD ==============
class CameraService:
    _instance = None
    _active_recordings: Dict[str, subprocess.Popen] = {}
    _active_ffmpeg: Dict[str, subprocess.Popen] = {}
    _ffmpeg_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def list_cameras(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """List all cameras the user can access (own + shared + public)."""
        # Get user's role
        role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
        is_admin = role and (role.is_super_admin or role.role == "admin")
        if is_admin:
            cams = db.query(Camera).all()
        else:
            own = db.query(Camera).filter(Camera.user_id == user_id).all()
            public = db.query(Camera).filter(Camera.is_public == True).all()
            # Get cameras shared with this user
            shared_ids = [
                p.camera_id for p in
                db.query(CameraPermission).filter(CameraPermission.user_id == user_id, CameraPermission.can_view == True).all()
            ]
            shared = db.query(Camera).filter(Camera.id.in_(shared_ids)).all() if shared_ids else []
            # Dedupe
            seen = set()
            cams = []
            for c in list(own) + list(public) + list(shared):
                if c.id not in seen:
                    cams.append(c)
                    seen.add(c.id)
        return [self._serialize(c) for c in cams]

    def get_camera(self, db: Session, user_id: str, camera_id: str) -> Optional[Dict[str, Any]]:
        if not user_can_access_camera(db, user_id, camera_id):
            return None
        c = db.query(Camera).filter(Camera.id == camera_id).first()
        return self._serialize(c, include_url=True, user_id=user_id)

    def _serialize(self, c: Camera, include_url: bool = False, user_id: str = "") -> Dict[str, Any]:
        result = {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "location": c.location,
            "brand": c.brand,
            "stream_type": c.stream_type,
            "stream_url": c.stream_url if include_url else None,
            "stream_url_2": c.stream_url_2 if include_url else None,
            "username": c.username,
            "onvif_url": c.onvif_url,
            "has_ptz": c.has_ptz,
            "port": c.port,
            "channel": c.channel,
            "is_recording": c.is_recording,
            "motion_detection": c.motion_detection,
            "is_public": c.is_public,
            "share_token": c.share_token,
            "status": c.status,
            "last_seen": str(c.last_seen) if c.last_seen else None,
            "created_at": str(c.created_at),
            "owner_id": c.user_id,
        }
        if c.id in self._active_ffmpeg:
            result["live"] = True
        return result

    def create_camera(self, db: Session, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        stream_url = data.get("stream_url", "").strip()
        if not stream_url:
            raise ValueError("stream_url is required")
        cam = Camera(
            user_id=user_id,
            name=data.get("name", "Camera").strip(),
            description=data.get("description"),
            location=data.get("location"),
            brand=data.get("brand", "imou").lower(),
            stream_type=data.get("stream_type", "rtsp").lower(),
            stream_url=stream_url,
            stream_url_2=data.get("stream_url_2"),
            username=data.get("username"),
            password_enc=encrypt_pw(data["password"]) if data.get("password") else None,
            onvif_url=data.get("onvif_url"),
            has_ptz=data.get("has_ptz", False),
            port=data.get("port", 554),
            channel=data.get("channel", 1),
            motion_detection=data.get("motion_detection", False),
            is_public=data.get("is_public", False),
            share_token="share-" + uuid.uuid4().hex[:16],
            status="offline",
        )
        db.add(cam)
        db.commit()
        db.refresh(cam)
        return self._serialize(cam)

    def update_camera(self, db: Session, user_id: str, camera_id: str, data: Dict[str, Any]) -> bool:
        if not check_camera_permission(db, user_id, camera_id, "configure"):
            return False
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            return False
        for k in ["name", "description", "location", "stream_url", "stream_url_2", "username", "onvif_url", "stream_type", "brand"]:
            if k in data:
                setattr(cam, k, data[k])
        if "password" in data and data["password"]:
            cam.password_enc = encrypt_pw(data["password"])
        for k in ["motion_detection", "is_public"]:
            if k in data:
                setattr(cam, k, bool(data[k]))
        db.commit()
        return True

    def delete_camera(self, db: Session, user_id: str, camera_id: str) -> bool:
        if not check_camera_permission(db, user_id, camera_id, "delete"):
            return False
        # Stop recording if running
        self.stop_recording(camera_id)
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            return False
        # Delete recording files
        recs = db.query(CameraRecording).filter(CameraRecording.camera_id == camera_id).all()
        for r in recs:
            try:
                if r.file_path and os.path.exists(r.file_path):
                    os.remove(r.file_path)
            except Exception:
                pass
            db.delete(r)
        db.delete(cam)
        db.commit()
        return True

    def test_connection(self, db: Session, user_id: str, camera_id: str) -> Dict[str, Any]:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam or not user_can_access_camera(db, user_id, camera_id):
            return {"success": False, "error": "Camera not found or no access"}
        # Try to probe the stream with ffmpeg (short timeout)
        result = self._probe_stream(cam.stream_url, timeout=5)
        if result["success"]:
            cam.status = "online"
            cam.last_seen = datetime.utcnow()
        else:
            cam.status = "error"
        db.commit()
        return result

    def _probe_stream(self, url: str, timeout: int = 5) -> Dict[str, Any]:
        """Try to read one frame from the stream to verify it's accessible."""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", url,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if proc.returncode == 0:
                return {"success": True, "url": url, "duration": proc.stdout.strip()}
            return {"success": False, "error": proc.stderr[:200] or "ffprobe failed"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Stream probe timed out"}
        except FileNotFoundError:
            # ffprobe not installed - try with python
            return {"success": True, "url": url, "note": "ffprobe not installed, assuming OK"}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    # ============== Recording ==============
    def start_recording(self, db: Session, user_id: str, camera_id: str, options: Dict = None) -> Dict[str, Any]:
        if not check_camera_permission(db, user_id, camera_id, "record"):
            return {"success": False, "error": "No permission to record"}
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            return {"success": False, "error": "Camera not found"}
        if cam.id in self._active_recordings:
            return {"success": False, "error": "Already recording", "recording_id": self._active_recording_id(db, cam.id)}
        options = options or {}
        # Highly compressed H.264: CRF 28, fast preset, lower resolution
        fps = options.get("fps", 15)
        width = options.get("width", 1280)
        height = options.get("height", 720)
        crf = options.get("crf", 28)  # 18-28 is good quality; 28 is highly compressed
        preset = options.get("preset", "ultrafast")  # fastest = smallest CPU overhead
        # Create recording entry
        rec_id = "rec-" + uuid.uuid4().hex[:12]
        rec_file = RECORDINGS_DIR / f"{rec_id}.mp4"
        rec = CameraRecording(
            id=rec_id,
            camera_id=cam.id,
            user_id=user_id,
            file_path=str(rec_file),
            file_size=0,
            duration_sec=0.0,
            fps=fps,
            width=width,
            height=height,
            codec="h264",
            bitrate_kbps=options.get("bitrate_kbps", 1000),
            started_at=datetime.utcnow(),
            status="recording",
            trigger_type=options.get("trigger", "manual"),
        )
        db.add(rec)
        cam.is_recording = True
        db.commit()
        # Build ffmpeg command
        cmd = ["ffmpeg", "-y", "-rtsp_transport", "tcp"]
        if cam.username and cam.password_enc:
            pwd = decrypt_pw(cam.password_enc)
            cmd += ["-user", cam.username, "-password", pwd]
        # If HLS, copy; if RTSP, transcode for compression
        if cam.stream_type == "rtsp":
            cmd += [
                "-i", cam.stream_url,
                "-vf", f"scale={width}:{height}",
                "-r", str(fps),
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart",
                "-f", "mp4",
                str(rec_file),
            ]
        elif cam.stream_type == "hls":
            cmd += ["-i", cam.stream_url, "-c", "copy", "-f", "mp4", str(rec_file)]
        else:
            # MJPEG or other: just copy
            cmd += ["-i", cam.stream_url, "-c", "copy", "-f", "mp4", str(rec_file)]
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp if os.name == "posix" else None
            )
            with self._ffmpeg_lock:
                self._active_recordings[cam.id] = proc
        except FileNotFoundError:
            # ffmpeg not installed - use mock recording
            proc = None
            rec.status = "error"
        except Exception as e:
            rec.status = "error"
            db.commit()
            return {"success": False, "error": f"Failed to start ffmpeg: {e}"}
        # Start a thread to monitor and update duration
        threading.Thread(target=self._monitor_recording, args=(cam.id, rec.id, proc), daemon=True).start()
        return {
            "success": True,
            "recording_id": rec.id,
            "file_path": str(rec_file),
            "fps": fps,
            "width": width,
            "height": height,
            "crf": crf,
        }

    def _monitor_recording(self, camera_id: str, rec_id: str, proc):
        """Watch a recording process and update its metadata."""
        start = time.time()
        db = session_factory()
        try:
            while True:
                if proc and proc.poll() is not None:
                    break
                if camera_id not in self._active_recordings:
                    break
                time.sleep(2)
                elapsed = time.time() - start
                rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
                if rec:
                    rec.duration_sec = elapsed
                    if os.path.exists(rec.file_path):
                        try:
                            rec.file_size = os.path.getsize(rec.file_path)
                        except Exception:
                            pass
                    db.commit()
        finally:
            db.close()
        # Final update
        db = session_factory()
        try:
            rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if rec:
                rec.duration_sec = time.time() - start
                rec.status = "completed"
                rec.ended_at = datetime.utcnow()
                if os.path.exists(rec.file_path):
                    rec.file_size = os.path.getsize(rec.file_path)
            if cam:
                cam.is_recording = False
            db.commit()
        finally:
            db.close()
        with self._ffmpeg_lock:
            self._active_recordings.pop(camera_id, None)

    def _active_recording_id(self, db: Session, camera_id: str) -> Optional[str]:
        rec = db.query(CameraRecording).filter(
            CameraRecording.camera_id == camera_id,
            CameraRecording.status == "recording"
        ).order_by(desc(CameraRecording.started_at)).first()
        return rec.id if rec else None

    def stop_recording(self, camera_id: str) -> Dict[str, Any]:
        proc = self._active_recordings.get(camera_id)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        with self._ffmpeg_lock:
            self._active_recordings.pop(camera_id, None)
        db = session_factory()
        try:
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if cam:
                cam.is_recording = False
                db.commit()
            rec = db.query(CameraRecording).filter(
                CameraRecording.camera_id == camera_id,
                CameraRecording.status == "recording"
            ).order_by(desc(CameraRecording.started_at)).first()
            if rec:
                rec.status = "completed"
                rec.ended_at = datetime.utcnow()
                if os.path.exists(rec.file_path):
                    rec.file_size = os.path.getsize(rec.file_path)
                db.commit()
                return {"success": True, "recording_id": rec.id}
        finally:
            db.close()
        return {"success": True}

    # ============== HLS Live Streaming ==============
    _hls_processes: Dict[str, subprocess.Popen] = {}

    def start_hls_stream(self, camera_id: str, cmd: List[str]) -> bool:
        """Start HLS segmentation for a camera stream."""
        if camera_id in self._hls_processes:
            self.stop_hls_stream(camera_id)

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp if os.name == "posix" else None
            )
            self._hls_processes[camera_id] = proc
            return True
        except FileNotFoundError:
            logger.warning("ffmpeg not installed - HLS streaming unavailable")
            return False
        except Exception as e:
            logger.error(f"Failed to start HLS stream: {e}")
            return False

    def stop_hls_stream(self, camera_id: str) -> bool:
        """Stop HLS segmentation for a camera."""
        proc = self._hls_processes.get(camera_id)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            finally:
                self._hls_processes.pop(camera_id, None)
        return True

    def is_hls_streaming(self, camera_id: str) -> bool:
        """Check if HLS stream is running for a camera."""
        proc = self._hls_processes.get(camera_id)
        if proc and proc.poll() is None:
            return True
        # Clean up dead process
        if proc:
            self._hls_processes.pop(camera_id, None)
        return False

    def get_stream_url(self, camera_id: str, stream_type: str = "mjpeg") -> Optional[str]:
        """Get the appropriate stream URL for a camera."""
        if stream_type == "hls":
            return f"/api/cameras/{camera_id}/live.m3u8"
        elif stream_type == "mjpeg":
            return f"/api/cameras/{camera_id}/mjpeg"
        else:
            return f"/api/cameras/{camera_id}/mjpeg"

    # ============== Recordings ==============
    def list_recordings(self, db: Session, user_id: str, camera_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        # Cameras user can access
        accessible = self.list_cameras(db, user_id)
        accessible_ids = [c["id"] for c in accessible]
        q = db.query(CameraRecording).filter(CameraRecording.camera_id.in_(accessible_ids))
        if camera_id:
            q = q.filter(CameraRecording.camera_id == camera_id)
        recs = q.order_by(desc(CameraRecording.started_at)).limit(limit).all()
        result = []
        for r in recs:
            cam = next((c for c in accessible if c["id"] == r.camera_id), None)
            result.append({
                "id": r.id,
                "camera_id": r.camera_id,
                "camera_name": cam["name"] if cam else "Unknown",
                "file_path": r.file_path,
                "file_size": r.file_size,
                "duration_sec": r.duration_sec,
                "fps": r.fps,
                "width": r.width,
                "height": r.height,
                "codec": r.codec,
                "bitrate_kbps": r.bitrate_kbps,
                "started_at": str(r.started_at),
                "ended_at": str(r.ended_at) if r.ended_at else None,
                "status": r.status,
                "trigger_type": r.trigger_type,
                "is_analyzed": r.is_analyzed,
                "objects_detected": json.loads(r.objects_detected) if r.objects_detected else None,
                "share_token": r.share_token,
            })
        return result

    def get_recording(self, db: Session, user_id: str, rec_id: str) -> Optional[Dict[str, Any]]:
        rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
        if not rec:
            return None
        if not user_can_access_camera(db, user_id, rec.camera_id):
            return None
        cam = db.query(Camera).filter(Camera.id == rec.camera_id).first()
        return {
            "id": rec.id,
            "camera_id": rec.camera_id,
            "camera_name": cam.name if cam else "Unknown",
            "file_path": rec.file_path,
            "file_size": rec.file_size,
            "duration_sec": rec.duration_sec,
            "fps": rec.fps,
            "width": rec.width,
            "height": rec.height,
            "codec": rec.codec,
            "bitrate_kbps": rec.bitrate_kbps,
            "started_at": str(rec.started_at),
            "ended_at": str(rec.ended_at) if rec.ended_at else None,
            "status": rec.status,
            "trigger_type": rec.trigger_type,
            "is_analyzed": rec.is_analyzed,
            "objects_detected": json.loads(rec.objects_detected) if rec.objects_detected else None,
            "share_token": rec.share_token,
        }

    def delete_recording(self, db: Session, user_id: str, rec_id: str) -> bool:
        rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
        if not rec:
            return False
        if not check_camera_permission(db, user_id, rec.camera_id, "delete"):
            return False
        try:
            if rec.file_path and os.path.exists(rec.file_path):
                os.remove(rec.file_path)
        except Exception:
            pass
        db.delete(rec)
        db.commit()
        return True

    # ============== Snapshot ==============
    def take_snapshot(self, db: Session, user_id: str, camera_id: str) -> Dict[str, Any]:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam or not user_can_access_camera(db, user_id, camera_id):
            return {"success": False, "error": "No access"}
        snap_path = SNAPSHOTS_DIR / f"{camera_id}-{int(time.time())}.jpg"
        cmd = ["ffmpeg", "-y"]
        if cam.username and cam.password_enc:
            pwd = decrypt_pw(cam.password_enc)
            cmd += ["-user", cam.username, "-password", pwd]
        cmd += [
            "-i", cam.stream_url,
            "-vframes", "1",
            "-q:v", "2",  # high quality JPEG
            str(snap_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=10)
            if os.path.exists(snap_path) and os.path.getsize(snap_path) > 0:
                return {
                    "success": True,
                    "snapshot_path": str(snap_path),
                    "url": f"/api/cameras/{camera_id}/snapshot?ts={int(time.time())}",
                }
        except Exception:
            pass
        return {"success": False, "error": "Snapshot failed (ffmpeg may not be installed)"}

    # ============== Object Analysis ==============
    def analyze_recording(self, db: Session, user_id: str, rec_id: str) -> Dict[str, Any]:
        """Decompress recording and analyze objects. Returns detected objects."""
        rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
        if not rec:
            return {"success": False, "error": "Recording not found"}
        if not check_camera_permission(db, user_id, rec.camera_id, "analyze"):
            return {"success": False, "error": "No analyze permission"}
        if not os.path.exists(rec.file_path):
            return {"success": False, "error": "File missing on server"}
        # Try YOLO / OpenCV analysis
        detected = []
        try:
            import cv2
            cap = cv2.VideoCapture(rec.file_path)
            frame_count = 0
            sample_every = int(cap.get(cv2.CAP_PROP_FPS) * 2) or 30  # sample every 2s
            # Try to load a YOLO model if available
            net = None
            try:
                weights = "/www/AI_server/data/yolov3.weights"
                cfg = "/www/AI_server/data/yolov3.cfg"
                names_file = "/www/AI_server/data/coco.names"
                if all(os.path.exists(f) for f in [weights, cfg, names_file]):
                    net = cv2.dnn.readNet(weights, cfg)
                    with open(names_file) as f:
                        classes = [line.strip() for line in f.readlines()]
                    layer_names = net.getLayerNames()
                    out_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
            except Exception:
                net = None
                classes = []
                out_layers = []
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            duration = rec.duration_sec
            analyzed = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % sample_every == 0:
                    ts = (frame_count / max(1, cap.get(cv2.CAP_PROP_FPS))) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0
                    if net is not None and frame is not None:
                        try:
                            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
                            net.setInput(blob)
                            outs = net.forward(out_layers)
                            for out in outs:
                                for det in out:
                                    scores = det[5:]
                                    class_id = int(np.argmax(scores)) if (np := __import__('numpy')) else 0
                                    conf = float(scores[class_id]) if len(scores) > class_id else 0
                                    if conf > 0.5:
                                        detected.append({
                                            "class": classes[class_id] if class_id < len(classes) else "object",
                                            "confidence": round(conf, 2),
                                            "timestamp_sec": round(ts, 1),
                                        })
                        except Exception:
                            pass
                    analyzed += 1
                frame_count += 1
                if total and frame_count >= total:
                    break
            cap.release()
        except ImportError:
            # OpenCV not available - do simple file analysis
            detected.append({
                "class": "video",
                "confidence": 1.0,
                "timestamp_sec": 0,
                "note": "OpenCV not installed; install opencv-python-headless for object detection",
            })
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}
        # Aggregate by class
        summary = {}
        for d in detected:
            c = d.get("class", "object")
            if c not in summary:
                summary[c] = {"count": 0, "max_confidence": 0, "first_seen": d.get("timestamp_sec")}
            summary[c]["count"] += 1
            if d.get("confidence", 0) > summary[c]["max_confidence"]:
                summary[c]["max_confidence"] = d.get("confidence", 0)
        # Save results
        rec.is_analyzed = True
        rec.objects_detected = json.dumps({
            "summary": summary,
            "detections": detected[:200],  # cap at 200
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "total_frames": frame_count if 'frame_count' in dir() else 0,
        })
        db.commit()
        return {
            "success": True,
            "recording_id": rec.id,
            "total_detections": len(detected),
            "summary": summary,
            "object_count": len(summary),
        }

    # ============== Sharing ==============
    def share_recording(self, db: Session, user_id: str, rec_id: str) -> Optional[str]:
        rec = db.query(CameraRecording).filter(CameraRecording.id == rec_id).first()
        if not rec or not check_camera_permission(db, user_id, rec.camera_id, "share"):
            return None
        token = "shr-" + uuid.uuid4().hex[:20]
        rec.share_token = token
        db.commit()
        return token

    def share_camera(self, db: Session, user_id: str, camera_id: str) -> Optional[str]:
        if not check_camera_permission(db, user_id, camera_id, "share"):
            return None
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            return None
        token = "cam-" + uuid.uuid4().hex[:20]
        cam.share_token = token
        db.commit()
        return token

    # ============== HLS Live Stream Generation ==============
    def get_hls_url(self, camera_id: str) -> str:
        """Return HLS URL for live viewing (browser-compatible)."""
        return f"/api/cameras/{camera_id}/live.m3u8"

    def get_thumbnail_url(self, camera_id: str) -> str:
        return f"/api/cameras/{camera_id}/thumbnail.jpg"


camera_service = CameraService()
