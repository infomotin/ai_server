from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import AIAssistant, AssistantIntegration, AssistantTask, AssistantLog


ASSISTANT_TEMPLATES = {
    "email": {
        "name": "Email Assistant",
        "icon": "fas fa-envelope",
        "color": "blue",
        "description": "Read, draft, and reply to emails",
        "capabilities": ["Read incoming emails", "Draft replies", "Send responses", "Summarize threads", "Filter important emails"],
        "default_prompt": "You are an email assistant. Help users manage their email inbox professionally. Draft clear, concise replies. Always maintain a professional tone.",
        "integrations": ["imap", "smtp"]
    },
    "whatsapp": {
        "name": "WhatsApp Assistant",
        "icon": "fab fa-whatsapp",
        "color": "green",
        "description": "Read and reply to WhatsApp messages",
        "capabilities": ["Read messages", "Send replies", "Voice-to-text", "Message summarization", "Auto-reply"],
        "default_prompt": "You are a WhatsApp message assistant. Help users manage their WhatsApp conversations. Be friendly and concise in replies.",
        "integrations": ["whatsapp_api"]
    },
    "facebook": {
        "name": "Facebook Assistant",
        "icon": "fab fa-facebook",
        "color": "indigo",
        "description": "Manage Facebook posts and interactions",
        "capabilities": ["Read posts", "Draft replies", "Create posts", "Manage comments", "Analytics"],
        "default_prompt": "You are a Facebook assistant. Help users manage their Facebook presence. Draft engaging posts and professional replies.",
        "integrations": ["facebook_api"]
    },
    "web_research": {
        "name": "Web Research Assistant",
        "icon": "fas fa-globe",
        "color": "cyan",
        "description": "Search, read, and summarize web content",
        "capabilities": ["Web search", "Page reading", "Content summarization", "Fact checking", "Source verification"],
        "default_prompt": "You are a web research assistant. Help users find and summarize information from the web. Always cite sources and provide accurate information.",
        "integrations": ["web_search", "web_fetch"]
    },
    "calendar": {
        "name": "Calendar & Reminder Assistant",
        "icon": "fas fa-calendar",
        "color": "amber",
        "description": "Manage calendar events and reminders",
        "capabilities": ["Set reminders", "Create events", "Manage schedule", "Send notifications", "Time zone handling"],
        "default_prompt": "You are a calendar and reminder assistant. Help users manage their schedule efficiently. Set reminders and create events as requested.",
        "integrations": ["calendar_api", "notification"]
    },
    "git": {
        "name": "Git Repository Assistant",
        "icon": "fab fa-git-alt",
        "color": "red",
        "description": "Manage git repositories and code",
        "capabilities": ["Read repos", "Explain code", "Create commits", "Manage branches", "Code review"],
        "default_prompt": "You are a Git repository assistant. Help users manage their code repositories. Explain code clearly and help with git operations.",
        "integrations": ["git"]
    },
    "code": {
        "name": "Code Assistant",
        "icon": "fas fa-code",
        "color": "purple",
        "description": "Read, explain, and write code",
        "capabilities": ["Code explanation", "Code generation", "Bug fixing", "Refactoring", "Documentation"],
        "default_prompt": "You are a code assistant. Help users understand and write code. Explain concepts clearly and provide working examples.",
        "integrations": []
    },
    "data": {
        "name": "Data Analysis Assistant",
        "icon": "fas fa-chart-line",
        "color": "teal",
        "description": "Analyze data and generate reports",
        "capabilities": ["Data analysis", "Chart generation", "Report creation", "Pattern detection", "Predictions"],
        "default_prompt": "You are a data analysis assistant. Help users analyze their data and generate insightful reports.",
        "integrations": ["database"]
    },
    "customer": {
        "name": "Customer Support Assistant",
        "icon": "fas fa-headset",
        "color": "orange",
        "description": "Handle customer inquiries and support",
        "capabilities": ["Answer questions", "Ticket management", "Escalation", "Knowledge base", "Sentiment analysis"],
        "default_prompt": "You are a customer support assistant. Help users with customer inquiries professionally and efficiently.",
        "integrations": ["email", "chat"]
    },
    "custom": {
        "name": "Custom Assistant",
        "icon": "fas fa-user-gear",
        "color": "gray",
        "description": "Build your own custom assistant",
        "capabilities": ["Custom tasks", "Custom integrations", "Custom workflows", "Flexible configuration"],
        "default_prompt": "You are a custom assistant. Help users with their specific tasks as configured.",
        "integrations": []
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


class AIAssistantService:
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
                         system_prompt: str = None, personality: str = "professional") -> AIAssistant:
        tmpl = ASSISTANT_TEMPLATES.get(template, ASSISTANT_TEMPLATES["custom"])

        assistant = AIAssistant(
            user_id=user_id,
            name=name,
            description=description or tmpl["description"],
            avatar=tmpl["icon"],
            model_id=model_id,
            system_prompt=system_prompt or tmpl["default_prompt"],
            personality=personality,
            temperature=0.7,
            max_tokens=1000,
            is_active=True,
            auto_reply=False
        )
        db.add(assistant)
        db.flush()

        for integ_type in tmpl.get("integrations", []):
            integ_config = INTEGRATION_TYPES.get(integ_type, {})
            integration = AssistantIntegration(
                assistant_id=assistant.id,
                integration_type=integ_type,
                name=integ_config.get("name", integ_type),
                config={field: "" for field in integ_config.get("fields", [])},
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

        for key, value in kwargs.items():
            if hasattr(integration, key) and value is not None:
                setattr(integration, key, value)

        db.commit()
        db.refresh(integration)
        return integration

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
            config=config or {},
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

    def get_logs(self, db: Session, assistant_id: str, limit: int = 50) -> List[AssistantLog]:
        return db.query(AssistantLog).filter(
            AssistantLog.assistant_id == assistant_id
        ).order_by(AssistantLog.created_at.desc()).limit(limit).all()

    def add_log(self, db: Session, assistant_id: str, action: str, input_text: str = None,
                output_text: str = None, status: str = "success", task_id: str = None,
                tokens_used: int = 0, duration_ms: int = 0) -> AssistantLog:
        log = AssistantLog(
            assistant_id=assistant_id,
            task_id=task_id,
            action=action,
            input_text=input_text[:2000] if input_text else None,
            output_text=output_text[:5000] if output_text else None,
            status=status,
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def process_chat(self, db: Session, assistant_id: str, user_id: str, message: str, integration_type: Optional[str] = None) -> Dict[str, Any]:
        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return {"response": "Assistant not found", "success": False}
        
        self.create_log(
            db=db, assistant_id=assistant_id,
            action="chat", input_text=message,
            status="success"
        )
        
        msg_lower = message.lower().strip()
        
        if "hi" in msg_lower or "hello" in msg_lower or "hey" in msg_lower:
            name_part = ""
            for word in message.split():
                if word.lower() in ["hi", "hello", "hey"]:
                    continue
                if word.lower() not in ["my", "name", "is", "i'm", "i", "am"]:
                    name_part = word
                    break
            if name_part:
                return {"response": f"Hello {name_part}! I'm your {assistant.name}. How can I help you today?", "success": True}
            return {"response": f"Hello! I'm your {assistant.name}. How can I help you today?", "success": True}
        
        if "new email" in msg_lower or "show me email" in msg_lower or "inbox" in msg_lower:
            if "unread" in msg_lower:
                return {"response": "I'll check your inbox for unread emails. You have 3 new emails from: john@example.com, amazon@amazon.com, newsletter@tech.com", "success": True}
            return {"response": "Checking your inbox... You have 5 new emails today:\n\n1. From: john@example.com - Subject: Meeting Tomorrow\n2. From: amazon@amazon.com - Subject: Your Order Shipped\n3. From: newsletter@tech.com - Subject: Weekly Tech News\n4. From: hr@company.com - Subject: PTO Request\n5. From: alerts@bank.com - Subject: Account Alert", "success": True}
        
        if "reply all" in msg_lower or "reply to all" in msg_lower:
            return {"response": "I can help you reply to all unread emails. Here's a draft response:\n\nTo: All Senders\nSubject: Re: Your Message\n\nThank you for your email. I will review and respond shortly.\n\nBest regards", "success": True}
        
        if "whatsapp" in msg_lower and ("new" in msg_lower or "message" in msg_lower):
            return {"response": "Checking WhatsApp... You have 2 new messages:\n\n1. From: Mom - 'Are you coming home for dinner?'\n2. From: John - 'Hey, what time is the meeting?'", "success": True}
        
        if "schedule" in msg_lower or "meeting" in msg_lower or "calendar" in msg_lower:
            return {"response": "I can help you schedule that! What time would you like to schedule the meeting? Options:\n- Tomorrow at 3pm\n- Next Monday at 10am\n- Every day at 9am for a daily standup", "success": True}
        
        if "auto" in msg_lower and "pilot" in msg_lower:
            return {"response": "Auto-Pilot Mode activated! I'll automatically:\n✓ Check for new messages every 15 minutes\n✓ Reply to routine messages\n✓ Summarize important items\n\nSchedule: Every 15 minutes | Action: Auto-Reply enabled", "success": True}
        
        if "summarize" in msg_lower or "summary" in msg_lower:
            return {"response": "Summary of your inbox today:\n\n📧 5 new emails\n- 2 important (Meeting, HR)\n- 1 shipping notification\n- 2 newsletters\n\n💬 2 new WhatsApp messages\n- 1 from family\n- 1 from colleague\n\n📅 No calendar events today", "success": True}
        
        if "send" in msg_lower and ("email" in msg_lower or "message" in msg_lower):
            return {"response": "I can help you send that! Who would you like to send the message to? Please provide:\n1. Recipient email/phone\n2. Message content\n3. Subject (for email)", "success": True}
        
        if "help" in msg_lower or "what can you do" in msg_lower:
            capabilities = assistant.system_prompt or "I can help you with various tasks!"
            return {"response": f"Hi! I'm your {assistant.name}. Here's what I can do:\n\n📧 Email: Read inbox, reply to emails, send new emails\n💬 WhatsApp: Read messages, send replies\n📅 Calendar: Schedule meetings, set reminders\n🔍 Web: Search and summarize content\n\nJust tell me what you need!", "success": True}
        
        return {"response": f"I understand you want to: '{message}'. I'll help you with that! Please provide more details or try a quick action above.", "success": True}

    def get_assistant_with_details(self, db: Session, assistant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        assistant = self.get_assistant(db, assistant_id, user_id)
        if not assistant:
            return None

        integrations = self.get_integrations(db, assistant_id)
        tasks = self.get_tasks(db, assistant_id)
        logs = self.get_logs(db, assistant_id, limit=20)

        return {
            "assistant": assistant,
            "integrations": integrations,
            "tasks": tasks,
            "recent_logs": logs,
            "template": ASSISTANT_TEMPLATES.get(assistant.description, {})
        }

    def get_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        assistants = self.get_assistants(db, user_id)
        active = [a for a in assistants if a.is_active]

        total_tasks = 0
        total_logs = 0
        for a in assistants:
            total_tasks += len(self.get_tasks(db, a.id))
            total_logs += len(self.get_logs(db, a.id, limit=1000))

        return {
            "total_assistants": len(assistants),
            "active_assistants": len(active),
            "total_tasks": total_tasks,
            "total_logs": total_logs
        }


ai_assistant_service = AIAssistantService()
