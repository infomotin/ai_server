import os
import uuid
import threading
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

import psutil
from sqlalchemy.orm import Session

from src.models.database import TrainingTask, KnowledgeBase, RestrictionProfile, Model
from src.models.schemas import (
    TrainingTaskCreate, KnowledgeBaseCreate, RestrictionProfileCreate,
    RestrictionProfileUpdate, WebCrawlRequest, ResourceAllocationUpdate
)
from src.services.model_service import DEFAULT_MODELS


LIGHTER_MODEL_MAP = {
    "llama3.2:1b": ["qwen2.5:0.5b"],
    "llama3.2:3b": ["llama3.2:1b", "qwen2.5:0.5b"],
    "qwen2.5:3b": ["qwen2.5:1.5b", "qwen2.5:0.5b"],
    "qwen2.5:1.5b": ["qwen2.5:0.5b"],
    "phi3:mini": ["llama3.2:1b", "qwen2.5:0.5b"],
    "mistral-nemo": ["phi3:mini", "llama3.2:1b"],
    "codellama:3.5": ["llama3.2:1b"],
}

MODEL_RECOMMENDATIONS = {
    "qwen2.5:0.5b": "lightweight",
    "llama3.2:1b": "lightweight",
    "deepseek-r1:1.5b": "lightweight",
    "qwen2.5:1.5b": "balanced",
    "llama3.2:3b": "balanced",
    "qwen2.5:3b": "balanced",
    "phi3:mini": "balanced",
    "codellama:3.5": "balanced",
    "mistral-nemo": "powerful",
}

MODEL_CAPABILITIES = {
    "llama3.2:1b": ["general", "conversation", "summarization"],
    "llama3.2:3b": ["general", "conversation", "summarization", "reasoning"],
    "qwen2.5:0.5b": ["general", "conversation", "multilingual"],
    "qwen2.5:1.5b": ["general", "conversation", "multilingual", "coding"],
    "qwen2.5:3b": ["general", "conversation", "multilingual", "coding", "math"],
    "phi3:mini": ["general", "reasoning", "math", "coding"],
    "mistral-nemo": ["general", "conversation", "reasoning", "multilingual"],
    "codellama:3.5": ["coding", "general"],
}

SECURITY_PROMPTS = {
    "none": "",
    "low": "You must avoid discussing harmful, illegal, or explicit content. Stay professional and helpful.",
    "medium": "You must strictly avoid discussing harmful, illegal, explicit, violent, or dangerous content. You must not provide instructions for illegal activities, weapons, hacking, or self-harm. Stay professional, ethical, and helpful at all times.",
    "high": "You are a highly restricted AI assistant. You must strictly avoid ALL harmful, illegal, explicit, violent, dangerous, controversial, political, religiously sensitive, or adult content. You must not provide any information about weapons, hacking, drugs, self-harm, fraud, or any illegal activity. You must not express opinions on controversial topics. You must only provide safe, factual, family-friendly information. If asked about restricted topics, politely decline and redirect to appropriate subjects."
}

TOPIC_RESTRICTION_PROMPT = "You must ONLY answer questions related to the following allowed topics: {topics}. If asked about anything else, politely decline and redirect to the allowed topics."

BLOCKED_TOPIC_PROMPT = "You must NOT discuss the following topics: {topics}. If asked about these topics, politely decline and redirect to other subjects."


class ManagementService:

    def create_training_task(self, db: Session, user_id: str, data: TrainingTaskCreate) -> TrainingTask:
        task = TrainingTask(
            user_id=user_id,
            task_type=data.task_type,
            model_id=data.model_id,
            source_info=data.source_info,
            status="pending"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def get_training_tasks(self, db: Session, user_id: str) -> List[TrainingTask]:
        return db.query(TrainingTask).filter(
            TrainingTask.user_id == user_id
        ).order_by(TrainingTask.created_at.desc()).all()

    def get_training_task(self, db: Session, task_id: str, user_id: str) -> Optional[TrainingTask]:
        return db.query(TrainingTask).filter(
            TrainingTask.id == task_id,
            TrainingTask.user_id == user_id
        ).first()

    def cancel_task(self, db: Session, task_id: str, user_id: str) -> bool:
        task = self.get_training_task(db, task_id, user_id)
        if not task or task.status not in ("pending", "running"):
            return False
        task.status = "cancelled"
        task.completed_at = datetime.now()
        db.commit()
        return True

    def extract_pdf_text(self, file_path: str) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract PDF text: {str(e)}")

    def process_pdf_task(self, db: Session, task_id: str, file_path: str, kb_name: str, model_id: Optional[str] = None):
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return

        task.status = "running"
        task.started_at = datetime.now()
        task.progress_percent = 10
        db.commit()

        try:
            task.progress_percent = 30
            db.commit()

            text = self.extract_pdf_text(file_path)
            if not text.strip():
                raise ValueError("No text content found in PDF")

            task.progress_percent = 70
            db.commit()

            chunks = self._chunk_text(text)
            chunk_count = len(chunks)

            kb = KnowledgeBase(
                user_id=task.user_id,
                name=kb_name,
                source_type="pdf",
                content_text=text[:100000],
                file_path=file_path,
                model_id=model_id,
                chunk_count=chunk_count,
                total_chars=len(text)
            )
            db.add(kb)

            task.progress_percent = 100
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result_summary = f"Extracted {len(text)} characters in {chunk_count} chunks. Knowledge base created."
            db.commit()

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

    def crawl_website(self, url: str, max_pages: int = 10) -> Dict[str, Any]:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse

        visited = set()
        pages_data = []
        base_domain = urlparse(url).netloc

        def crawl_page(current_url, depth=0):
            if depth > 3 or len(visited) >= max_pages or current_url in visited:
                return
            visited.add(current_url)

            try:
                headers = {"User-Agent": "Mozilla/5.0 (compatible; OpenLocalAI/1.0)"}
                resp = requests.get(current_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    return
                if "text/html" not in resp.headers.get("content-type", ""):
                    return

                soup = BeautifulSoup(resp.text, "html.parser")

                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                title = soup.title.string if soup.title else ""
                text = soup.get_text(separator="\n", strip=True)
                text = "\n".join(line for line in text.splitlines() if line.strip())

                if len(text) > 100:
                    pages_data.append({
                        "url": current_url,
                        "title": title.strip() if title else "",
                        "text": text[:50000],
                        "char_count": len(text)
                    })

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    full_url = urljoin(current_url, href)
                    parsed = urlparse(full_url)
                    if parsed.netloc == base_domain and full_url not in visited:
                        crawl_page(full_url, depth + 1)

                time.sleep(0.5)

            except Exception:
                pass

        crawl_page(url)

        combined_text = "\n\n---\n\n".join(
            f"[{p['title'] or p['url']}]\n{p['text']}" for p in pages_data
        )

        return {
            "pages_crawled": len(pages_data),
            "total_chars": len(combined_text),
            "pages": pages_data,
            "combined_text": combined_text
        }

    def process_web_crawl_task(self, db: Session, task_id: str, url: str, max_pages: int, kb_name: str, model_id: Optional[str] = None):
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return

        task.status = "running"
        task.started_at = datetime.now()
        task.progress_percent = 5
        db.commit()

        try:
            task.progress_percent = 15
            db.commit()

            result = self.crawl_website(url, max_pages)

            task.progress_percent = 70
            db.commit()

            if not result["combined_text"].strip():
                raise ValueError("No content extracted from website")

            chunks = self._chunk_text(result["combined_text"])
            chunk_count = len(chunks)

            kb = KnowledgeBase(
                user_id=task.user_id,
                name=kb_name,
                source_type="web",
                content_text=result["combined_text"][:100000],
                source_url=url,
                model_id=model_id,
                chunk_count=chunk_count,
                total_chars=result["total_chars"]
            )
            db.add(kb)

            task.progress_percent = 100
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result_summary = f"Crawled {result['pages_crawled']} pages, extracted {result['total_chars']} characters in {chunk_count} chunks."
            db.commit()

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

    def start_pdf_task(self, db: Session, task_id: str, file_path: str, kb_name: str, model_id: Optional[str] = None):
        thread = threading.Thread(
            target=self.process_pdf_task,
            args=(db, task_id, file_path, kb_name, model_id),
            daemon=True
        )
        thread.start()

    def start_web_crawl_task(self, db: Session, task_id: str, url: str, max_pages: int, kb_name: str, model_id: Optional[str] = None):
        thread = threading.Thread(
            target=self.process_web_crawl_task,
            args=(db, task_id, url, max_pages, kb_name, model_id),
            daemon=True
        )
        thread.start()

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
        return chunks

    def create_knowledge_base(self, db: Session, user_id: str, data: KnowledgeBaseCreate) -> KnowledgeBase:
        content = data.content_text or ""
        chunks = self._chunk_text(content) if content else []
        kb = KnowledgeBase(
            user_id=user_id,
            name=data.name,
            source_type=data.source_type,
            content_text=content[:100000] if content else None,
            source_url=data.source_url,
            file_path=data.file_path,
            model_id=data.model_id,
            chunk_count=len(chunks),
            total_chars=len(content)
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        return kb

    def get_knowledge_bases(self, db: Session, user_id: str) -> List[KnowledgeBase]:
        return db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id
        ).order_by(KnowledgeBase.created_at.desc()).all()

    def delete_knowledge_base(self, db: Session, kb_id: str, user_id: str) -> bool:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user_id
        ).first()
        if not kb:
            return False
        db.delete(kb)
        db.commit()
        return True

    def toggle_knowledge_base(self, db: Session, kb_id: str, user_id: str) -> Optional[KnowledgeBase]:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user_id
        ).first()
        if not kb:
            return None
        kb.is_active = not kb.is_active
        db.commit()
        db.refresh(kb)
        return kb

    def create_restriction_profile(self, db: Session, user_id: str, data: RestrictionProfileCreate) -> RestrictionProfile:
        profile = RestrictionProfile(
            user_id=user_id,
            name=data.name,
            restriction_mode=data.restriction_mode,
            allowed_topics=data.allowed_topics,
            blocked_topics=data.blocked_topics,
            security_level=data.security_level,
            custom_rules=data.custom_rules,
            system_prompt_override=data.system_prompt_override,
            is_active=False
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def get_restriction_profiles(self, db: Session, user_id: str) -> List[RestrictionProfile]:
        return db.query(RestrictionProfile).filter(
            RestrictionProfile.user_id == user_id
        ).order_by(RestrictionProfile.created_at.desc()).all()

    def update_restriction_profile(self, db: Session, profile_id: str, user_id: str, data: RestrictionProfileUpdate) -> Optional[RestrictionProfile]:
        profile = db.query(RestrictionProfile).filter(
            RestrictionProfile.id == profile_id,
            RestrictionProfile.user_id == user_id
        ).first()
        if not profile:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)

        profile.updated_at = datetime.now()
        db.commit()
        db.refresh(profile)
        return profile

    def delete_restriction_profile(self, db: Session, profile_id: str, user_id: str) -> bool:
        profile = db.query(RestrictionProfile).filter(
            RestrictionProfile.id == profile_id,
            RestrictionProfile.user_id == user_id
        ).first()
        if not profile:
            return False
        db.delete(profile)
        db.commit()
        return True

    def activate_restriction_profile(self, db: Session, profile_id: str, user_id: str) -> bool:
        db.query(RestrictionProfile).filter(
            RestrictionProfile.user_id == user_id
        ).update({"is_active": False})

        profile = db.query(RestrictionProfile).filter(
            RestrictionProfile.id == profile_id,
            RestrictionProfile.user_id == user_id
        ).first()
        if not profile:
            return False

        profile.is_active = True
        db.commit()
        return True

    def deactivate_all_restrictions(self, db: Session, user_id: str):
        db.query(RestrictionProfile).filter(
            RestrictionProfile.user_id == user_id
        ).update({"is_active": False})
        db.commit()

    def build_system_prompt(self, db: Session, user_id: str) -> str:
        parts = []

        profile = db.query(RestrictionProfile).filter(
            RestrictionProfile.user_id == user_id,
            RestrictionProfile.is_active == True
        ).first()

        if profile:
            if profile.system_prompt_override:
                parts.append(profile.system_prompt_override)
            else:
                if profile.restriction_mode == "security" or profile.security_level != "none":
                    level = profile.security_level if profile.restriction_mode == "security" else profile.security_level
                    security_prompt = SECURITY_PROMPTS.get(level, "")
                    if security_prompt:
                        parts.append(security_prompt)

                if profile.restriction_mode == "topic":
                    if profile.allowed_topics:
                        topics_str = ", ".join(profile.allowed_topics)
                        parts.append(TOPIC_RESTRICTION_PROMPT.format(topics=topics_str))
                    if profile.blocked_topics:
                        topics_str = ", ".join(profile.blocked_topics)
                        parts.append(BLOCKED_TOPIC_PROMPT.format(topics=topics_str))

                if profile.restriction_mode == "custom" and profile.custom_rules:
                    rules = profile.custom_rules
                    if isinstance(rules, dict):
                        for key, value in rules.items():
                            parts.append(f"{key}: {value}")

        active_kbs = db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.is_active == True
        ).all()

        if active_kbs:
            kb_parts = []
            for kb in active_kbs[:3]:
                if kb.content_text:
                    preview = kb.content_text[:2000]
                    kb_parts.append(f"Knowledge base '{kb.name}':\n{preview}")
            if kb_parts:
                parts.append("Use the following knowledge base information when answering questions:\n\n" + "\n\n---\n\n".join(kb_parts))

        return "\n\n".join(parts) if parts else ""

    def get_system_resources(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": round(disk.percent, 1)
        }

    def get_model_recommendations(self, current_model: str = None) -> List[Dict[str, Any]]:
        recommendations = []
        for model_def in DEFAULT_MODELS:
            model_id = model_def["id"]
            rec = MODEL_RECOMMENDATIONS.get(model_id, "balanced")
            param_count = model_def.get("parameter_count", 0)
            size_gb = round(param_count * 0.5 / 1e9, 2) if param_count else 0

            recommendations.append({
                "id": model_id,
                "name": model_def["name"],
                "provider": model_def["provider"],
                "parameter_count": param_count,
                "quantization": model_def.get("quantization", "Q4_0"),
                "size_gb": size_gb,
                "recommendation": rec,
                "vram_required": f"~{max(1, int(size_gb * 1.2))}GB",
                "capabilities": MODEL_CAPABILITIES.get(model_id, ["general"]),
                "is_current": model_id == current_model
            })

        recommendations.sort(key=lambda x: x["parameter_count"])
        return recommendations

    def get_lighter_models(self, model_id: str) -> List[str]:
        return LIGHTER_MODEL_MAP.get(model_id, [])


management_service = ManagementService()
