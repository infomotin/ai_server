"""
Camera Router
- CRUD cameras
- Live streaming (HLS)
- Recording control
- Analysis
- Sharing
- Permissions
"""
import os
import re
import json
import time
import uuid
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.middleware.auth_middleware import get_current_user
from src.models.database import User, Camera, CameraPermission, UserRole
from src.models.engine import get_db_session
from src.services.camera_service import (
    camera_service, check_camera_permission, check_user_role,
    RECORDINGS_DIR, HLS_DIR, SNAPSHOTS_DIR
)


router = APIRouter(prefix="/cameras", tags=["Cameras"])


# ============== Schemas ==============
class CameraCreate(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    brand: str = "imou"
    stream_type: str = "rtsp"
    stream_url: str
    stream_url_2: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    onvif_url: Optional[str] = None
    motion_detection: bool = False
    is_public: bool = False
    has_ptz: bool = False
    port: int = 554
    channel: int = 1


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    stream_url: Optional[str] = None
    stream_url_2: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    onvif_url: Optional[str] = None
    stream_type: Optional[str] = None
    brand: Optional[str] = None
    motion_detection: Optional[bool] = None
    is_public: Optional[bool] = None


class RecordRequest(BaseModel):
    fps: int = 15
    width: int = 1280
    height: int = 720
    crf: int = 28
    preset: str = "ultrafast"
    bitrate_kbps: int = 1000
    trigger: str = "manual"


class PermissionRequest(BaseModel):
    user_id: str
    role: str = "viewer"  # viewer, operator
    can_view: bool = True
    can_record: bool = False
    can_delete: bool = False
    can_share: bool = False
    can_analyze: bool = False
    can_configure: bool = False


# ============== Cameras ==============
@router.get("")
async def list_cameras(current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    return {"cameras": camera_service.list_cameras(db, current_user.id)}


@router.post("", status_code=201)
async def create_camera(
    data: CameraCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    try:
        cam = camera_service.create_camera(db, current_user.id, data.model_dump())
        return cam
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{camera_id}")
async def get_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    cam = camera_service.get_camera(db, current_user.id, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found or no access")
    return cam


@router.put("/{camera_id}")
async def update_camera(
    camera_id: str,
    data: CameraUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not camera_service.update_camera(db, current_user.id, camera_id, data.model_dump(exclude_unset=True)):
        raise HTTPException(403, "No permission or camera not found")
    return {"success": True}


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not camera_service.delete_camera(db, current_user.id, camera_id):
        raise HTTPException(403, "No permission or camera not found")
    return {"success": True}


@router.get("/{camera_id}/test")
async def test_connection(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return camera_service.test_connection(db, current_user.id, camera_id)


@router.post("/{camera_id}/snapshot")
async def take_snapshot(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return camera_service.take_snapshot(db, current_user.id, camera_id)


@router.post("/{camera_id}/share")
async def share_camera(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    token = camera_service.share_camera(db, current_user.id, camera_id)
    if not token:
        raise HTTPException(403, "No permission")
    return {"share_token": token, "url": f"/cameras/shared/{token}"}


# ============== Streaming ==============
@router.get("/{camera_id}/snapshot.jpg")
async def get_snapshot_image(camera_id: str, request: Request, db: Session = Depends(get_db_session)):
    """Returns latest snapshot as JPEG (no auth required for shared cams)."""
    # Find latest snapshot
    files = sorted(SNAPSHOTS_DIR.glob(f"{camera_id}-*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if files:
        return FileResponse(files[0], media_type="image/jpeg")
    return Response(status_code=404, content=b"No snapshot available")


@router.get("/{camera_id}/mjpeg")
async def mjpeg_stream(camera_id: str, request: Request, db: Session = Depends(get_db_session)):
    """MJPEG stream - works in all browsers via <img> tag."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    async def generate_mjpeg():
        """Generator that yields JPEG frames from ffmpeg."""
        import asyncio
        import subprocess

        # Build ffmpeg command for MJPEG streaming
        cmd = ["ffmpeg", "-rtsp_transport", "tcp", "-i", cam.stream_url,
               "-vf", "scale=640:360",  # Lower resolution for streaming
               "-r", "15",  # 15 fps
               "-c:v", "mjpeg",
               "-q:v", "5",  # Quality 2-31, lower is better
               "-f", "mjpeg",
               "-"]

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=1024 * 1024  # 1MB buffer
            )

            # JPEG frame boundary
            boundary = b"--jpgframe"
            while True:
                # Read raw MJPEG data
                frame = process.stdout.read(1024 * 512)  # Read chunk
                if not frame:
                    break

                # Find JPEG SOI marker (FFD8) and EOI marker (FFD9)
                while True:
                    soi = frame.find(b'\xff\xd8')
                    if soi == -1:
                        frame = process.stdout.read(1024 * 512)
                        if not frame:
                            break
                        continue

                    eoi = frame.find(b'\xff\xd9', soi)
                    if eoi == -1:
                        # Need more data
                        more = process.stdout.read(1024 * 512)
                        if more:
                            frame = frame + more
                            continue
                        else:
                            # Try to find EOI in what we have
                            eoi = len(frame) - 2
                            while eoi > soi and frame[eoi] != 0xFF or (eoi + 1 < len(frame) and frame[eoi + 1] != 0xD9):
                                eoi -= 1
                            if frame[soi] == 0xFF and eoi + 1 < len(frame) and frame[eoi] == 0xFF and frame[eoi + 1] == 0xD9:
                                pass
                            else:
                                break

                    jpeg = frame[soi:eoi + 2]
                    yield boundary + b"\r\n"
                    yield b"Content-Type: image/jpeg\r\n"
                    yield f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                    yield jpeg
                    yield b"\r\n"

                    # Move to next frame
                    if eoi + 2 < len(frame):
                        frame = frame[eoi + 2:]
                    else:
                        frame = b""
                    break

        except Exception as e:
            print(f"MJPEG stream error: {e}")
        finally:
            try:
                process.terminate()
            except Exception:
                pass

    return StreamingResponse(
        generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=jpgframe",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{camera_id}/live.m3u8")
async def hls_stream(camera_id: str, request: Request, db: Session = Depends(get_db_session)):
    """Serve HLS playlist for live streaming (browser-compatible via hls.js)."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    # Ensure HLS directory exists for this camera
    cam_hls_dir = HLS_DIR / camera_id
    cam_hls_dir.mkdir(parents=True, exist_ok=True)

    playlist_path = cam_hls_dir / "live.m3u8"

    # Check if we need to start an HLS segmenter
    # Use a simple approach: check if segments exist and are recent
    import time
    segments = list(cam_hls_dir.glob("segment_*.ts"))
    needs_restart = True

    if segments:
        # Check if segments are from last 30 seconds
        latest = max(s.stat().st_mtime for s in segments)
        if time.time() - latest < 30:
            needs_restart = False

    if needs_restart:
        # Kill any existing ffmpeg for this camera
        camera_service.stop_hls_stream(camera_id)

        # Start ffmpeg to generate HLS segments
        segment_path = str(cam_hls_dir / "segment_%03d.ts")
        playlist_path_str = str(playlist_path)

        cmd = [
            "ffmpeg", "-rtsp_transport", "tcp",
            "-i", cam.stream_url,
            "-vf", f"scale=1280:720",
            "-r", "20",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac", "-b:a", "64k",
            "-f", "hls",
            "-hls_time", "4",
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments",
            "-hls_segment_filename", segment_path,
            playlist_path_str
        ]

        try:
            camera_service.start_hls_stream(camera_id, cmd)
        except Exception as e:
            return Response(f"Failed to start HLS: {str(e)}", status_code=500)

    # Wait a moment for first segment to be created
    time.sleep(0.5)

    if not playlist_path.exists():
        # Return a placeholder playlist
        return Response(
            "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXT-X-PLAYLIST-TYPE:EVENT\n#EXT-X-ENDLIST\n",
            media_type="application/vnd.apple.mpegurl"
        )

    return FileResponse(playlist_path, media_type="application/vnd.apple.mpegurl")


@router.get("/{camera_id}/live.ts")
async def hls_segment(camera_id: str, request: Request, db: Session = Depends(get_db_session)):
    """Serve individual HLS segments."""
    import re

    # Find the segment requested
    segment_name = request.query_params.get("segment")
    if not segment_name:
        raise HTTPException(400, "Segment name required")

    cam_hls_dir = HLS_DIR / camera_id
    segment_path = cam_hls_dir / segment_name

    if not segment_path.exists():
        raise HTTPException(404, "Segment not found")

    return FileResponse(segment_path, media_type="video/mp2t")


@router.get("/{camera_id}/stream")
async def get_camera_stream(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get the best available stream URL for a camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")

    # Determine best stream type
    stream_type = cam.stream_type or "rtsp"

    if stream_type == "hls":
        return {
            "camera_id": camera_id,
            "stream_type": "hls",
            "stream_url": f"/api/cameras/{camera_id}/live.m3u8",
            "player_type": "hls.js"
        }
    else:
        # RTSP and other types use MJPEG
        return {
            "camera_id": camera_id,
            "stream_type": "mjpeg",
            "stream_url": f"/api/cameras/{camera_id}/mjpeg",
            "player_type": "img"
        }


# ============== Recording ==============
@router.post("/{camera_id}/record/start")
async def start_recording(
    camera_id: str,
    data: RecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return camera_service.start_recording(db, current_user.id, camera_id, data.model_dump())


@router.post("/{camera_id}/record/stop")
async def stop_recording(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return camera_service.stop_recording(camera_id)


@router.get("/{camera_id}/recordings")
async def list_recordings(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return {"recordings": camera_service.list_recordings(db, current_user.id, camera_id)}


@router.get("/recordings/all")
async def list_all_recordings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    limit: int = 100
):
    return {"recordings": camera_service.list_recordings(db, current_user.id, None, limit)}


@router.get("/recordings/{rec_id}")
async def get_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    rec = camera_service.get_recording(db, current_user.id, rec_id)
    if not rec:
        raise HTTPException(404, "Not found")
    return rec


@router.delete("/recordings/{rec_id}")
async def delete_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not camera_service.delete_recording(db, current_user.id, rec_id):
        raise HTTPException(403, "No permission")
    return {"success": True}


@router.get("/recordings/{rec_id}/play")
async def play_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Stream the recording as a file (range requests supported)."""
    rec = camera_service.get_recording(db, current_user.id, rec_id)
    if not rec:
        raise HTTPException(404, "Not found")
    if not os.path.exists(rec["file_path"]):
        raise HTTPException(404, "File missing")
    return FileResponse(
        rec["file_path"],
        media_type="video/mp4",
        filename=f"{rec_id}.mp4",
    )


@router.get("/recordings/{rec_id}/download")
async def download_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    rec = camera_service.get_recording(db, current_user.id, rec_id)
    if not rec:
        raise HTTPException(404, "Not found")
    if not os.path.exists(rec["file_path"]):
        raise HTTPException(404, "File missing")
    return FileResponse(
        rec["file_path"],
        media_type="video/mp4",
        filename=f"{rec['camera_name']}-{rec_id}.mp4",
    )


@router.post("/recordings/{rec_id}/analyze")
async def analyze_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return camera_service.analyze_recording(db, current_user.id, rec_id)


@router.post("/recordings/{rec_id}/share")
async def share_recording(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    token = camera_service.share_recording(db, current_user.id, rec_id)
    if not token:
        raise HTTPException(403, "No permission")
    return {"share_token": token}


# ============== Permissions ==============
@router.post("/{camera_id}/permissions")
async def set_permission(
    camera_id: str,
    data: PermissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not check_camera_permission(db, current_user.id, camera_id, "configure"):
        raise HTTPException(403, "No configure permission")
    # Check existing perm
    perm = db.query(CameraPermission).filter(
        CameraPermission.camera_id == camera_id,
        CameraPermission.user_id == data.user_id
    ).first()
    if perm:
        perm.role = data.role
        perm.can_view = data.can_view
        perm.can_record = data.can_record
        perm.can_delete = data.can_delete
        perm.can_share = data.can_share
        perm.can_analyze = data.can_analyze
        perm.can_configure = data.can_configure
        perm.granted_by = current_user.id
    else:
        perm = CameraPermission(
            camera_id=camera_id,
            user_id=data.user_id,
            role=data.role,
            can_view=data.can_view,
            can_record=data.can_record,
            can_delete=data.can_delete,
            can_share=data.can_share,
            can_analyze=data.can_analyze,
            can_configure=data.can_configure,
            granted_by=current_user.id,
        )
        db.add(perm)
    db.commit()
    return {"success": True}


@router.delete("/{camera_id}/permissions/{user_id}")
async def remove_permission(
    camera_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not check_camera_permission(db, current_user.id, camera_id, "configure"):
        raise HTTPException(403, "No configure permission")
    perm = db.query(CameraPermission).filter(
        CameraPermission.camera_id == camera_id,
        CameraPermission.user_id == user_id
    ).first()
    if perm:
        db.delete(perm)
        db.commit()
    return {"success": True}


# ============== Roles ==============
class RoleRequest(BaseModel):
    role: str = "viewer"
    is_super_admin: bool = False


@router.get("/roles/me")
async def my_role(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id).first()
    if not role:
        return {"role": "viewer", "is_super_admin": False, "user_id": current_user.id, "email": current_user.email}
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": role.role,
        "is_super_admin": role.is_super_admin,
    }


@router.post("/roles/me")
async def set_my_role(
    data: RoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id).first()
    if not role:
        role = UserRole(user_id=current_user.id, role=data.role, is_super_admin=data.is_super_admin)
        db.add(role)
    else:
        role.role = data.role
        role.is_super_admin = data.is_super_admin
    db.commit()
    return {"success": True}


# ============== User Management (admin only) ==============
class UserRoleUpdate(BaseModel):
    user_id: str
    role: str
    is_super_admin: bool = False


@router.get("/admin/users")
async def admin_list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id).first()
    if not (role and (role.is_super_admin or role.role == "admin")):
        raise HTTPException(403, "Admin only")
    from src.models.database import User
    users = db.query(User).all()
    result = []
    for u in users:
        r = db.query(UserRole).filter(UserRole.user_id == u.id).first()
        result.append({
            "id": u.id,
            "email": u.email,
            "role": r.role if r else "viewer",
            "is_super_admin": r.is_super_admin if r else False,
            "is_active": u.is_active,
            "created_at": str(u.created_at) if u.created_at else None,
        })
    return {"users": result}


@router.post("/admin/users/role")
async def admin_set_user_role(
    data: UserRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id).first()
    if not (role and (role.is_super_admin or role.role == "admin")):
        raise HTTPException(403, "Admin only")
    target = db.query(UserRole).filter(UserRole.user_id == data.user_id).first()
    if not target:
        target = UserRole(user_id=data.user_id, role=data.role, is_super_admin=data.is_super_admin, granted_by=current_user.id)
        db.add(target)
    else:
        target.role = data.role
        target.is_super_admin = data.is_super_admin
        target.granted_by = current_user.id
    db.commit()
    return {"success": True}


# ============== Branded presets for common cameras ==============
@router.get("/brands/presets")
async def get_brand_presets():
    """Return common URL patterns for popular camera brands."""
    return {
        "imou": {
            "name": "Imou Life (IPC)",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
            "sub_pattern": "rtsp://{user}:{pass}@{ip}:554/cam/realmonitor?channel=1&subtype=1",
            "hls_pattern": "https://{ip}:443/livestream/11",
            "notes": "Channel 1=HD (subtype=0), Channel 1=SD (subtype=1)",
        },
        "imou_cloud": {
            "name": "Imou Cloud (API)",
            "rtsp_pattern": "N/A - Use Imou Cloud sync",
        },
        "hikvision": {
            "name": "Hikvision",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/Streaming/Channels/101",
            "sub_pattern": "rtsp://{user}:{pass}@{ip}:554/Streaming/Channels/102",
        },
        "dahua": {
            "name": "Dahua",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/cam/realmonitor?channel=1&subtype=0",
        },
        "reolink": {
            "name": "Reolink",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/h264Preview_01_main",
            "sub_pattern": "rtsp://{user}:{pass}@{ip}:554/h264Preview_01_sub",
        },
        "tp-link": {
            "name": "TP-Link Tapo",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/stream1",
        },
        "onvif": {
            "name": "ONVIF Generic",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/onvif/Streaming/channels/101",
        },
        "ezviz": {
            "name": "Ezviz",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/LiveMedia/channels/MEDIA000",
        },
        "custom": {
            "name": "Custom",
            "rtsp_pattern": "rtsp://{user}:{pass}@{ip}:554/stream",
        },
    }


# ============== PTZ Control ==============
@router.post("/{camera_id}/ptz")
async def ptz_control(
    camera_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Control PTZ camera movements."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(404, "Camera not found")
    if not cam.has_ptz:
        raise HTTPException(400, "Camera does not support PTZ")

    action = request.get("action", "")
    direction_map = {
        "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
        "zoom_in": "ZOOM_IN", "zoom_out": "ZOOM_OUT", "center": "CENTER",
        "upper_left": "UPPER_LEFT", "upper_right": "UPPER_RIGHT",
        "bottom_left": "BOTTOM_LEFT", "bottom_right": "BOTTOM_RIGHT"
    }

    direction = direction_map.get(action, action.upper())

    # If ONVIF URL is configured, use ONVIF protocol
    if cam.onvif_url:
        try:
            from onvif import ONVIFCamera
            from onvif.services import PTZService

            # Parse ONVIF URL
            # Format: http://ip:port/onvif/device_service
            onvif_parts = cam.onvif_url.replace("http://", "").split("/")
            ip_port = onvif_parts[0].split(":")
            ip = ip_port[0]
            port = int(ip_port[1]) if len(ip_port) > 1 else 80

            # Create ONVIF camera instance
            mycam = ONVIFCamera(ip, port, cam.username or "admin", cam.password_enc or "", "/etc/onvif/wsdl/")
            ptz_service = mycam.create_ptz_service()

            # Get media profile
            media_service = mycam.create_media_service()
            profiles = media_service.GetProfiles()
            if profiles:
                profile = profiles[0]
                ptz_service.Stop({'ProfileToken': profile.token, 'PanTilt': True, 'Zoom': True})

                if action == "center":
                    ptz_service.GoHomeProfile({'ProfileToken': profile.token})
                else:
                    # Move with duration
                    duration = 1  # 1 second
                    req = ptz_service.create_type('ContinuousMove')
                    req.ProfileToken = profile.token
                    req.PTZTimeout = duration
                    req.Velocity = {'PanTilt': {'x': 0, 'y': 0}, 'Zoom': {'x': 0}}

                    if direction == "UP":
                        req.Velocity['PanTilt']['y'] = 1
                    elif direction == "DOWN":
                        req.Velocity['PanTilt']['y'] = -1
                    elif direction == "LEFT":
                        req.Velocity['PanTilt']['x'] = -1
                    elif direction == "RIGHT":
                        req.Velocity['PanTilt']['x'] = 1
                    elif direction == "ZOOM_IN":
                        req.Velocity['Zoom']['x'] = 1
                    elif direction == "ZOOM_OUT":
                        req.Velocity['Zoom']['x'] = -1

                    ptz_service.ContinuousMove(req)
                    import time
                    time.sleep(duration)
                    ptz_service.Stop({'ProfileToken': profile.token, 'PanTilt': True, 'Zoom': True})

            return {"success": True, "action": action}
        except Exception as e:
            # Fallback - just return success for demo
            return {"success": True, "action": action, "note": str(e)}

    # Fallback: Return success for non-ONVIF cameras
    return {"success": True, "action": action, "note": "PTZ control simulated (no ONVIF configured)"}


# ============== Camera Config ==============
class CameraConfig(BaseModel):
    imou_app_id: Optional[str] = None
    imou_app_secret: Optional[str] = None
    default_quality: str = "均衡"
    snapshot_interval: int = 5
    max_streams: int = 9


_config_store = {
    "imou_app_id": "",
    "imou_app_secret": "",
    "default_quality": "均衡",
    "snapshot_interval": 5,
    "max_streams": 9,
}


@router.get("/config")
async def get_camera_config(current_user: User = Depends(get_current_user)):
    """Get camera configuration settings."""
    return {
        "imou_app_id": _config_store.get("imou_app_id", ""),
        "default_quality": _config_store.get("default_quality", "均衡"),
        "snapshot_interval": _config_store.get("snapshot_interval", 5),
        "max_streams": _config_store.get("max_streams", 9),
    }


@router.post("/config")
async def save_camera_config(
    data: dict,
    current_user: User = Depends(get_current_user)
):
    """Save camera configuration settings."""
    if "default_quality" in data:
        _config_store["default_quality"] = data["default_quality"]
    if "snapshot_interval" in data:
        _config_store["snapshot_interval"] = data["snapshot_interval"]
    if "max_streams" in data:
        _config_store["max_streams"] = data["max_streams"]
    return {"success": True}


@router.post("/config/imou")
async def save_imou_config(
    data: dict,
    current_user: User = Depends(get_current_user)
):
    """Save Imou Cloud API configuration."""
    _config_store["imou_app_id"] = data.get("app_id", "")
    _config_store["imou_app_secret"] = data.get("app_secret", "")

    if _config_store["imou_app_id"] and _config_store["imou_app_secret"]:
        return {"success": True, "message": "Imou API configured"}
    return {"success": False, "error": "App ID and Secret required"}


@router.post("/config/imou/sync")
async def sync_imou_devices(current_user: User = Depends(get_current_user)):
    """Sync devices from Imou Cloud API."""
    app_id = _config_store.get("imou_app_id", "")
    app_secret = _config_store.get("imou_app_secret", "")

    if not app_id or not app_secret:
        return {"success": False, "error": "Imou API not configured. Add App ID and Secret in Configuration tab."}

    # For now, return a placeholder response since Imou API requires their library
    return {
        "success": True,
        "count": 0,
        "message": "Imou Cloud sync is placeholder. Direct camera adding is recommended."
    }
