import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import (
    AIAssistant, AssistantIntegration, AssistantTask,
    AssistantLog, AssistantMessage, AssistantConversation
)
from src.inference.ollama_client import ollama_client, lmstudio_client, get_inference_client


ASSISTANT_TEMPLATES = {
    "email": {
        "name": "Email Assistant",
        "icon": "fas fa-envelope",
        "color": "blue",
        "description": "Read, draft, and reply to emails",
        "capabilities": ["Read incoming emails", "Draft replies", "Send responses", "Summarize threads", "Filter important emails"],
        "default_prompt": "You are an email assistant. Help users manage their email inbox professionally. Draft clear, concise replies. Always maintain a professional tone. Use markdown for clarity.",
        "integrations": ["imap", "smtp"],
        "tags": ["productivity", "communication"]
    },
    "whatsapp": {
        "name": "WhatsApp Assistant",
        "icon": "fab fa-whatsapp",
        "color": "green",
        "description": "Read and reply to WhatsApp messages",
        "capabilities": ["Read messages", "Send replies", "Voice-to-text", "Message summarization", "Auto-reply"],
        "default_prompt": "You are a WhatsApp message assistant. Help users manage their WhatsApp conversations. Be friendly and concise in replies.",
        "integrations": ["whatsapp_api"],
        "tags": ["communication", "social"]
    },
    "facebook": {
        "name": "Facebook Assistant",
        "icon": "fab fa-facebook",
        "color": "indigo",
        "description": "Manage Facebook posts and interactions",
        "capabilities": ["Read posts", "Draft replies", "Create posts", "Manage comments", "Analytics"],
        "default_prompt": "You are a Facebook assistant. Help users manage their Facebook presence. Draft engaging posts and professional replies.",
        "integrations": ["facebook_api"],
        "tags": ["social", "marketing"]
    },
    "web_research": {
        "name": "Web Research Assistant",
        "icon": "fas fa-globe",
        "color": "cyan",
        "description": "Search, read, and summarize web content",
        "capabilities": ["Web search", "Page reading", "Content summarization", "Fact checking", "Source verification"],
        "default_prompt": "You are a web research assistant. Help users find and summarize information from the web. Always cite sources and provide accurate information. Use markdown formatting with clear sections.",
        "integrations": ["web_search", "web_fetch"],
        "tags": ["research", "productivity"]
    },
    "calendar": {
        "name": "Calendar & Reminder Assistant",
        "icon": "fas fa-calendar",
        "color": "amber",
        "description": "Manage calendar events and reminders",
        "capabilities": ["Set reminders", "Create events", "Manage schedule", "Send notifications", "Time zone handling"],
        "default_prompt": "You are a calendar and reminder assistant. Help users manage their schedule efficiently. Set reminders and create events as requested.",
        "integrations": ["calendar_api", "notification"],
        "tags": ["productivity"]
    },
    "git": {
        "name": "Git Repository Assistant",
        "icon": "fab fa-git-alt",
        "color": "red",
        "description": "Manage git repositories and code",
        "capabilities": ["Read repos", "Explain code", "Create commits", "Manage branches", "Code review"],
        "default_prompt": "You are a Git repository assistant. Help users manage their code repositories. Explain code clearly and help with git operations. Always provide code examples in fenced markdown blocks.",
        "integrations": ["git"],
        "tags": ["developer", "code"]
    },
    "code": {
        "name": "Code Assistant",
        "icon": "fas fa-code",
        "color": "purple",
        "description": "Read, explain, and write code",
        "capabilities": ["Code explanation", "Code generation", "Bug fixing", "Refactoring", "Documentation"],
        "default_prompt": "You are an expert code assistant. Help users understand, debug, and write code across languages. Always use fenced markdown code blocks with the language identifier. Be concise but thorough.",
        "integrations": [],
        "tags": ["developer", "code"]
    },
    "data": {
        "name": "Data Analysis Assistant",
        "icon": "fas fa-chart-line",
        "color": "teal",
        "description": "Analyze data and generate reports",
        "capabilities": ["Data analysis", "Chart generation", "Report creation", "Pattern detection", "Predictions"],
        "default_prompt": "You are a data analysis assistant. Help users analyze their data and generate insightful reports. Use markdown tables when presenting structured data.",
        "integrations": ["database"],
        "tags": ["analytics", "business"]
    },
    "customer": {
        "name": "Customer Support Assistant",
        "icon": "fas fa-headset",
        "color": "orange",
        "description": "Handle customer inquiries and support",
        "capabilities": ["Answer questions", "Ticket management", "Escalation", "Knowledge base", "Sentiment analysis"],
        "default_prompt": "You are a customer support assistant. Help users with customer inquiries professionally and efficiently. Show empathy and provide actionable answers.",
        "integrations": ["email", "chat"],
        "tags": ["support", "business"]
    },
    "writer": {
        "name": "Creative Writer",
        "icon": "fas fa-pen-fancy",
        "color": "pink",
        "description": "Help with creative writing, blogs, and content",
        "capabilities": ["Blog posts", "Story writing", "Copywriting", "Editing", "SEO content"],
        "default_prompt": "You are a creative writing assistant. Help users craft engaging content. Use vivid language, varied sentence structure, and markdown formatting for headings and emphasis.",
        "integrations": [],
        "tags": ["creative", "writing"]
    },
    "translator": {
        "name": "Language Translator",
        "icon": "fas fa-language",
        "color": "yellow",
        "description": "Translate text between languages",
        "capabilities": ["Multi-language translation", "Context preservation", "Idioms", "Formal/informal tone"],
        "default_prompt": "You are a professional translator. Translate text accurately between languages while preserving tone, context, and idioms. Always respond with the translation first, then any notes.",
        "integrations": [],
        "tags": ["language", "productivity"]
    },
    "tutor": {
        "name": "Personal Tutor",
        "icon": "fas fa-graduation-cap",
        "color": "lime",
        "description": "Explain concepts and help you learn",
        "capabilities": ["Concept explanation", "Quiz generation", "Step-by-step walkthroughs", "Examples", "Analogies"],
        "default_prompt": "You are a patient personal tutor. Explain concepts step by step using clear language, examples, and analogies. Encourage the learner. Use markdown formatting with sections.",
        "integrations": [],
        "tags": ["education"]
    },
    "custom": {
        "name": "Custom Assistant",
        "icon": "fas fa-user-gear",
        "color": "gray",
        "description": "Build your own custom assistant",
        "capabilities": ["Custom tasks", "Custom integrations", "Custom workflows", "Flexible configuration"],
        "default_prompt": "You are a custom assistant. Help users with their specific tasks as configured. Be helpful, accurate, and adapt to the user's needs.",
        "integrations": [],
        "tags": ["custom"]
    }
}


INTEGRATION_TYPES = {
    "imap": {"name": "Email (IMAP)", "icon": "fas fa-inbox", "color": "blue", "fields": ["host", "port", "username", "password"]},
    "smtp": {"name": "Email (SMTP)", "icon": "fas fa-paper-plane", "color": "blue", "fields": ["host", "port", "username", "password"]},
    "whatsapp_api": {"name": "WhatsApp API", "icon": "fab fa-whatsapp", "color": "green", "fields": ["api_key", "phone_number"]},
    "facebook_api": {"name": "Facebook API", "icon": "fab fa-facebook", "color": "indigo", "fields": ["app_id", "app_secret", "access_token"]},
    "web_search": {"name": "Web Search", "icon": "fas fa-search", "color": "cyan", "fields": ["api_key", "search_engine"]},
    "web_fetch": {"name": "Web Fetcher", "icon": "fas fa-globe", "color": "cyan", "fields": ["proxy_url"]},
    "calendar_api": {"name": "Calendar API", "icon": "fas fa-calendar", "color": "amber", "fields": ["provider", "api_key"]},
    "notification": {"name": "Notifications", "icon": "fas fa-bell", "color": "amber", "fields": ["email", "webhook_url"]},
    "git": {"name": "Git Repository", "icon": "fab fa-git-alt", "color": "red", "fields": ["repo_path", "remote_url"]},
    "database": {"name": "Database", "icon": "fas fa-database", "color": "teal", "fields": ["connection_url"]},
    "chat": {"name": "Live Chat", "icon": "fas fa-comments", "color": "orange", "fields": ["widget_id"]},
    "slack": {"name": "Slack", "icon": "fab fa-slack", "color": "purple", "fields": ["bot_token", "channel"]},
    "telegram": {"name": "Telegram", "icon": "fab fa-telegram", "color": "cyan", "fields": ["bot_token"]},
    "github": {"name": "GitHub", "icon": "fab fa-github", "color": "gray", "fields": ["token", "repo"]},
    "google_drive": {"name": "Google Drive", "icon": "fab fa-google-drive", "color": "amber", "fields": ["credentials_json"]},
    "dropbox": {"name": "Dropbox", "icon": "fab fa-dropbox", "color": "blue", "fields": ["access_token"]},
    "notion": {"name": "Notion", "icon": "fas fa-book", "color": "gray", "fields": ["api_key", "database_id"]},
    "trello": {"name": "Trello", "icon": "fas fa-trello", "color": "blue", "fields": ["api_key", "token"]}
}


TASK_TYPES = {
    "email_read": {"name": "Read Emails", "category": "email", "icon": "fas fa-inbox", "description": "Fetch and read incoming emails"},
    "email_reply": {"name": "Reply to Email", "category": "email", "icon": "fas fa-reply", "description": "Draft and send email replies"},
    "email_summary": {"name": "Summarize Emails", "category": "email", "icon": "fas fa-list-ul", "description": "Summarize email threads"},
    "whatsapp_read": {"name": "Read Messages", "category": "whatsapp", "icon": "fab fa-whatsapp", "description": "Read WhatsApp messages"},
    "whatsapp_reply": {"name": "Reply to Message", "category": "whatsapp", "icon": "fas fa-reply", "description": "Reply to WhatsApp messages"},
    "facebook_read": {"name": "Read Posts", "category": "facebook", "icon": "fab fa-facebook", "description": "Read Facebook posts and comments"},
    "facebook_post": {"name": "Create Post", "category": "facebook", "icon": "fas fa-pen", "description": "Create Facebook posts"},
    "web_search": {"name": "Web Search", "category": "research", "icon": "fas fa-search", "description": "Search the web for information"},
    "web_read": {"name": "Read Web Page", "category": "research", "icon": "fas fa-globe", "description": "Read and extract web content"},
    "web_summarize": {"name": "Summarize Content", "category": "research", "icon": "fas fa-compress", "description": "Summarize web content"},
    "reminder_set": {"name": "Set Reminder", "category": "calendar", "icon": "fas fa-bell", "description": "Set a reminder"},
    "event_create": {"name": "Create Event", "category": "calendar", "icon": "fas fa-calendar-plus", "description": "Create calendar event"},
    "git_read": {"name": "Read Repository", "category": "git", "icon": "fab fa-git-alt", "description": "Read git repository contents"},
    "git_commit": {"name": "Create Commit", "category": "git", "icon": "fas fa-code-commit", "description": "Create a git commit"},
    "git_explain": {"name": "Explain Code", "category": "git", "icon": "fas fa-lightbulb", "description": "Explain code functionality"},
    "code_write": {"name": "Write Code", "category": "code", "icon": "fas fa-code", "description": "Generate code"},
    "code_review": {"name": "Review Code", "category": "code", "icon": "fas fa-search", "description": "Review code quality"},
    "data_analyze": {"name": "Analyze Data", "category": "data", "icon": "fas fa-chart-line", "description": "Analyze data patterns"},
    "report_create": {"name": "Create Report", "category": "data", "icon": "fas fa-file-alt", "description": "Generate reports"},
    "ticket_handle": {"name": "Handle Ticket", "category": "support", "icon": "fas fa-ticket", "description": "Handle support tickets"},
    "customer_reply": {"name": "Reply to Customer", "category": "support", "icon": "fas fa-headset", "description": "Reply to customer inquiries"},
    "custom_task": {"name": "Custom Task", "category": "custom", "icon": "fas fa-cog", "description": "Execute custom task"}
}


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


class AIAssistantService:

    @staticmethod
    def _normalize_config(value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {}
        return {}

    def get_templates(self) -> Dict[str, Any]:
        return ASSISTANT_TEMPLATES

    def get_integration_types(self) -> Dict[str, Any]:
        return INTEGRATION_TYPES

    def get_task_types(self) -> Dict[str, Any]:
        return TASK_TYPES

    def get_assistants(self, db: Session, user_id: str) -> List[AIAssistant]:
        return db.query(AIAssistant).filter(
            AIAssistant.user_id == user_id
        ).order_by(AIAssistant.created_at.desc()).all()

    def get_assistant(self, db: Session, assistant_id: str, user_id: str) -> Optional[AIAssistant]:
        return db.query(AIAssistant).filter(
            AIAssistant.id == assistant_id,
            AIAssistant.user_id == user_id
        ).first()

    def create_assistant(self, db: Session, user_id: str, name: str, template: str = "custom",
                         model_id: str = "llama3.2:1b", description: str = None,
                         system_prompt: str = None, personality: str = "professional",
                         temperature: float = None, max_tokens: int = None,
                         color: str = None, icon: str = None, tags: List[str] = None) -> AIAssistant:
        tmpl = ASSISTANT_TEMPLATES.get(template, ASSISTANT_TEMPLATES["custom"])

        assistant = AIAssistant(
            user_id=user_id,
            name=name,
            description=description or tmpl["description"],
            avatar=icon or tmpl["icon"],
            model_id=model_id,
            system_prompt=system_prompt or tmpl["default_prompt"],
            personality=personality,
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens if max_tokens is not None else 1000,
            is_active=True,
            auto_reply=False
        )
        if color:
            assistant.color = color
        if tags:
            try:
                assistant.tags = json.dumps(tags)
            except Exception:
                pass

        db.add(assistant)
        db.flush()

        for integ_type in tmpl.get("integrations", []):
            integ_config = INTEGRATION_TYPES.get(integ_type, {})
            integration = AssistantIntegration(
                assistant_id=assistant.id,
                integration_type=integ_type,
                name=integ_config.get("name", integ_type),
                config=json.dumps({field: "" for field in integ_config.get("fields", [])}),
                is_active=False,
                status="disconnected"
            )
            db.add(integration)

        db.commit()
        db.refresh(assistant)
        return assistant

    def update_assistant(self, db: Session, assistant_id: str, user_id: str, **kwargs) -> Optional[AIAssistant]:
        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return None

        if "tags" in kwargs and isinstance(kwargs["tags"], list):
            kwargs["tags"] = json.dumps(kwargs["tags"])

        for key, value in kwargs.items():
            if hasattr(assistant, key) and value is not None:
                setattr(assistant, key, value)

        db.commit()
        db.refresh(assistant)
        return assistant

    def delete_assistant(self, db: Session, assistant_id: str, user_id: str) -> bool:
        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return False
        db.delete(assistant)
        db.commit()
        return True

    def duplicate_assistant(self, db: Session, assistant_id: str, user_id: str) -> Optional[AIAssistant]:
        original = self.get_assistant(db, assistant_id, user_id)
        if not original:
            return None

        clone = AIAssistant(
            user_id=user_id,
            name=f"{original.name} (Copy)",
            description=original.description,
            avatar=original.avatar,
            model_id=original.model_id,
            system_prompt=original.system_prompt,
            personality=original.personality,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            is_active=True,
            auto_reply=False
        )
        db.add(clone)
        db.flush()

        for integ in original.integrations:
            new_integ = AssistantIntegration(
                assistant_id=clone.id,
                integration_type=integ.integration_type,
                name=integ.name,
                config=integ.config,
                credentials=integ.credentials,
                is_active=False,
                status="disconnected"
            )
            db.add(new_integ)

        db.commit()
        db.refresh(clone)
        return clone

    def get_integrations(self, db: Session, assistant_id: str) -> List[AssistantIntegration]:
        return db.query(AssistantIntegration).filter(
            AssistantIntegration.assistant_id == assistant_id
        ).all()

    def update_integration(self, db: Session, integration_id: str, **kwargs) -> Optional[AssistantIntegration]:
        integration = db.query(AssistantIntegration).filter(
            AssistantIntegration.id == integration_id
        ).first()
        if not integration:
            return None

        if "config" in kwargs and isinstance(kwargs["config"], dict):
            kwargs["config"] = json.dumps(kwargs["config"])

        for key, value in kwargs.items():
            if hasattr(integration, key) and value is not None:
                setattr(integration, key, value)

        db.commit()
        db.refresh(integration)
        return integration

    def add_integration(self, db: Session, assistant_id: str, integration_type: str,
                        config: Dict = None) -> Optional[AssistantIntegration]:
        info = INTEGRATION_TYPES.get(integration_type, {})
        integration = AssistantIntegration(
            assistant_id=assistant_id,
            integration_type=integration_type,
            name=info.get("name", integration_type),
            config=json.dumps(config or {f: "" for f in info.get("fields", [])}),
            is_active=False,
            status="disconnected"
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)
        return integration

    def delete_integration(self, db: Session, integration_id: str) -> bool:
        integration = db.query(AssistantIntegration).filter(
            AssistantIntegration.id == integration_id
        ).first()
        if not integration:
            return False
        db.delete(integration)
        db.commit()
        return True

    def get_tasks(self, db: Session, assistant_id: str) -> List[AssistantTask]:
        return db.query(AssistantTask).filter(
            AssistantTask.assistant_id == assistant_id
        ).order_by(AssistantTask.created_at.desc()).all()

    def create_task(self, db: Session, assistant_id: str, task_type: str, name: str,
                    description: str = None, config: Dict = None, schedule: str = None) -> Optional[AssistantTask]:
        task_info = TASK_TYPES.get(task_type, {})

        task = AssistantTask(
            assistant_id=assistant_id,
            task_type=task_type,
            name=name or task_info.get("name", task_type),
            description=description or task_info.get("description", ""),
            config=json.dumps(config or {}),
            schedule=schedule,
            is_active=True,
            run_count=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update_task(self, db: Session, task_id: str, **kwargs) -> Optional[AssistantTask]:
        task = db.query(AssistantTask).filter(AssistantTask.id == task_id).first()
        if not task:
            return None

        if "config" in kwargs and isinstance(kwargs["config"], dict):
            kwargs["config"] = json.dumps(kwargs["config"])

        for key, value in kwargs.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        db.commit()
        db.refresh(task)
        return task

    def delete_task(self, db: Session, task_id: str) -> bool:
        task = db.query(AssistantTask).filter(AssistantTask.id == task_id).first()
        if not task:
            return False
        db.delete(task)
        db.commit()
        return True

    def run_task(self, db: Session, task_id: str) -> Dict[str, Any]:
        task = db.query(AssistantTask).filter(AssistantTask.id == task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}

        task.last_run = datetime.utcnow()
        task.run_count = (task.run_count or 0) + 1
        db.commit()
        db.refresh(task)

        self.add_log(
            db=db,
            assistant_id=task.assistant_id,
            task_id=task.id,
            action=f"run_task:{task.task_type}",
            input_text=task.description or task.name,
            status="success",
            duration_ms=10
        )

        return {
            "success": True,
            "task_id": task.id,
            "run_count": task.run_count,
            "last_run": str(task.last_run)
        }

    def get_logs(self, db: Session, assistant_id: str, limit: int = 50) -> List[AssistantLog]:
        return db.query(AssistantLog).filter(
            AssistantLog.assistant_id == assistant_id
        ).order_by(AssistantLog.created_at.desc()).limit(limit).all()

    def add_log(self, db: Session, assistant_id: str, action: str, input_text: str = None,
                output_text: str = None, status: str = "success", task_id: str = None,
                tokens_used: int = 0, duration_ms: int = 0,
                error_message: str = None) -> AssistantLog:
        log = AssistantLog(
            assistant_id=assistant_id,
            task_id=task_id,
            action=action,
            input_text=input_text[:2000] if input_text else None,
            output_text=output_text[:5000] if output_text else None,
            status=status,
            error_message=error_message,
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    # ---------- Conversation history ----------

    def _get_or_create_conversation(self, db: Session, assistant_id: str,
                                    conversation_id: str = None) -> AssistantConversation:
        if conversation_id:
            conv = db.query(AssistantConversation).filter(
                AssistantConversation.id == conversation_id,
                AssistantConversation.assistant_id == assistant_id
            ).first()
            if conv:
                return conv

        conv = AssistantConversation(
            assistant_id=assistant_id,
            title="New conversation"
        )
        db.add(conv)
        db.flush()
        return conv

    def get_conversations(self, db: Session, assistant_id: str) -> List[AssistantConversation]:
        return db.query(AssistantConversation).filter(
            AssistantConversation.assistant_id == assistant_id
        ).order_by(AssistantConversation.updated_at.desc()).all()

    def get_messages(self, db: Session, conversation_id: str, limit: int = 100) -> List[AssistantMessage]:
        return db.query(AssistantMessage).filter(
            AssistantMessage.conversation_id == conversation_id
        ).order_by(AssistantMessage.created_at.asc()).limit(limit).all()

    def delete_conversation(self, db: Session, conversation_id: str) -> bool:
        conv = db.query(AssistantConversation).filter(
            AssistantConversation.id == conversation_id
        ).first()
        if not conv:
            return False
        db.query(AssistantMessage).filter(
            AssistantMessage.conversation_id == conversation_id
        ).delete()
        db.delete(conv)
        db.commit()
        return True

    def rename_conversation(self, db: Session, conversation_id: str, title: str) -> bool:
        conv = db.query(AssistantConversation).filter(
            AssistantConversation.id == conversation_id
        ).first()
        if not conv:
            return False
        conv.title = title[:200]
        conv.updated_at = datetime.utcnow()
        db.commit()
        return True

    # ---------- Core chat ----------

    async def process_chat(self, db: Session, assistant_id: str, user_id: str,
                           message: str, conversation_id: str = None,
                           integration_type: str = None) -> Dict[str, Any]:
        start = time.time()

        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return {"response": "Assistant not found", "success": False}

        conv = self._get_or_create_conversation(db, assistant_id, conversation_id)

        user_msg = AssistantMessage(
            conversation_id=conv.id,
            role="user",
            content=message
        )
        db.add(user_msg)
        db.flush()

        history = db.query(AssistantMessage).filter(
            AssistantMessage.conversation_id == conv.id
        ).order_by(AssistantMessage.created_at.asc()).limit(20).all()

        personality_suffix = {
            "professional": "Maintain a professional, courteous tone.",
            "friendly": "Be warm, friendly, and encouraging.",
            "concise": "Be very concise. Keep answers short and direct.",
            "detailed": "Provide detailed, thorough explanations.",
            "technical": "Use precise technical language. Include examples.",
            "creative": "Be creative, imaginative, and engaging."
        }.get(assistant.personality, "")

        system_content = assistant.system_prompt or ASSISTANT_TEMPLATES["custom"]["default_prompt"]
        if personality_suffix:
            system_content += "\n\n" + personality_suffix

        messages_payload = [{"role": "system", "content": system_content}]
        for h in history:
            messages_payload.append({"role": h.role, "content": h.content})

        response_text = ""
        tokens_used = 0
        error_message = None
        status = "success"

        try:
            client = get_inference_client()
            model = assistant.model_id or "llama3.2:1b"

            if isinstance(client, type(ollama_client)):
                result = await client.chat(
                    messages=messages_payload,
                    model=model,
                    temperature=assistant.temperature or 0.7,
                    top_p=0.9,
                    max_tokens=assistant.max_tokens or 1000,
                    stream=False
                )
                response_text = result.get("message", {}).get("content", "")
            else:
                result = await client.chat(
                    messages=messages_payload,
                    model=model,
                    temperature=assistant.temperature or 0.7,
                    top_p=0.9,
                    max_tokens=assistant.max_tokens or 1000,
                    stream=False
                )
                response_text = result["choices"][0]["message"]["content"]

            tokens_used = _estimate_tokens(system_content) + _estimate_tokens(message) + _estimate_tokens(response_text)
        except Exception as e:
            response_text = (
                "I couldn't reach the inference backend. "
                "Please ensure the local AI server (llama.cpp on port 8080) is running and the model is loaded."
            )
            error_message = str(e)[:500]
            status = "error"

        assistant_msg = AssistantMessage(
            conversation_id=conv.id,
            role="assistant",
            content=response_text
        )
        db.add(assistant_msg)
        db.flush()

        if history and history[0].role == "user":
            title_seed = message[:60].strip()
            if title_seed and (not conv.title or conv.title == "New conversation"):
                conv.title = title_seed

        conv.updated_at = datetime.utcnow()
        db.commit()

        duration_ms = int((time.time() - start) * 1000)
        self.add_log(
            db=db,
            assistant_id=assistant_id,
            action="chat",
            input_text=message,
            output_text=response_text,
            status=status,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            error_message=error_message
        )

        return {
            "success": status == "success",
            "response": response_text,
            "conversation_id": conv.id,
            "message_id": assistant_msg.id,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
            "model": model,
            "error": error_message
        }

    def get_assistant_with_details(self, db: Session, assistant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return None

        integrations = self.get_integrations(db, assistant_id)
        tasks = self.get_tasks(db, assistant_id)
        logs = self.get_logs(db, assistant_id, limit=20)
        conversations_raw = self.get_conversations(db, assistant_id)
        from src.models.database import AssistantMessage
        conversations = []
        for c in conversations_raw:
            msg_count = db.query(AssistantMessage).filter(
                AssistantMessage.conversation_id == c.id
            ).count()
            conversations.append({
                "id": c.id,
                "title": c.title,
                "created_at": str(c.created_at),
                "updated_at": str(c.updated_at) if c.updated_at else None,
                "message_count": msg_count
            })

        tmpl_key = None
        for key, info in ASSISTANT_TEMPLATES.items():
            if info["description"] == assistant.description or info["icon"] == assistant.avatar:
                tmpl_key = key
                break

        return {
            "assistant": assistant,
            "integrations": integrations,
            "tasks": tasks,
            "recent_logs": logs,
            "conversations": conversations,
            "template": ASSISTANT_TEMPLATES.get(tmpl_key, ASSISTANT_TEMPLATES["custom"])
        }

    def get_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        assistants = self.get_assistants(db, user_id)
        active = [a for a in assistants if a.is_active]

        total_tasks = 0
        total_logs = 0
        total_messages = 0
        total_tokens = 0
        action_counter = {}
        for a in assistants:
            total_tasks += len(self.get_tasks(db, a.id))
            logs = self.get_logs(db, a.id, limit=1000)
            total_logs += len(logs)
            for l in logs:
                total_tokens += (l.tokens_used or 0)
                action_counter[l.action] = action_counter.get(l.action, 0) + 1
            for c in self.get_conversations(db, a.id):
                total_messages += db.query(func.count(AssistantMessage.id)).filter(
                    AssistantMessage.conversation_id == c.id
                ).scalar() or 0

        by_day = {}
        for a in assistants:
            logs = self.get_logs(db, a.id, limit=1000)
            for l in logs:
                day = str(l.created_at)[:10]
                by_day[day] = by_day.get(day, 0) + 1
        activity_series = [{"date": k, "count": v} for k, v in sorted(by_day.items())[-14:]]

        return {
            "total_assistants": len(assistants),
            "active_assistants": len(active),
            "total_tasks": total_tasks,
            "total_logs": total_logs,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "actions_breakdown": action_counter,
            "activity_series": activity_series
        }


ai_assistant_service = AIAssistantService()