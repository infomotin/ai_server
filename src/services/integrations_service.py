import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import re

import httpx


class EmailIntegration:
    def __init__(self, config: Dict[str, Any]):
        self.host = config.get("imap_host", "imap.gmail.com")
        self.port = config.get("imap_port", 993)
        self.smtp_host = config.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.use_ssl = config.get("use_ssl", True)

    def test_connection(self) -> Dict[str, Any]:
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port) if self.use_ssl else imaplib.IMAP4(self.host, self.port)
            mail.login(self.username, self.password)
            mail.logout()
            return {"success": True, "message": "Connection successful"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def read_emails(self, folder: str = "INBOX", limit: int = 20, unread_only: bool = False) -> List[Dict[str, Any]]:
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port) if self.use_ssl else imaplib.IMAP4(self.host, self.port)
            mail.login(self.username, self.password)
            mail.select(folder)

            status, messages = mail.search(None, "UNSEEN" if unread_only else "ALL")
            if status != "OK":
                return []

            msg_ids = messages[0].split()[-limit:]
            emails = []

            for msg_id in reversed(msg_ids):
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                from_addr = msg.get("From", "")
                date_str = msg.get("Date", "")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                emails.append({
                    "id": msg_id.decode(),
                    "from": from_addr,
                    "to": msg.get("To", ""),
                    "subject": subject,
                    "body": body[:5000],
                    "date": date_str,
                    "has_attachments": any(m.get_content_disposition() == "attachment" for m in msg.walk()) if msg.is_multipart() else False
                })

            mail.logout()
            return emails
        except Exception as e:
            print(f"Error reading emails: {e}")
            return []

    def send_email(self, to: str, subject: str, body: str, reply_to: str = None) -> Dict[str, Any]:
        try:
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = to
            msg["Subject"] = subject
            if reply_to:
                msg["In-Reply-To"] = reply_to
                msg["References"] = reply_to

            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()

            return {"success": True, "message": "Email sent"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


class TelegramIntegration:
    API_BASE = "https://api.telegram.org/bot"

    def __init__(self, config: Dict[str, Any]):
        self.bot_token = config.get("bot_token", "")
        self.base_url = f"{self.API_BASE}{self.bot_token}"

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.base_url}/getMe", timeout=10)
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "message": f"Bot: @{data['result'].get('username', 'unknown')}"}
            return {"success": False, "message": data.get("description", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.base_url}/getUpdates", params={"limit": limit}, timeout=10)
            data = resp.json()
            if not data.get("ok"):
                return []

            messages = []
            for update in data.get("result", []):
                msg = update.get("message", {})
                if msg:
                    messages.append({
                        "id": str(update["update_id"]),
                        "from": msg.get("from", {}).get("username", msg.get("from", {}).get("first_name", "unknown")),
                        "from_id": msg.get("from", {}).get("id"),
                        "chat_id": msg.get("chat", {}).get("id"),
                        "text": msg.get("text", ""),
                        "date": datetime.fromtimestamp(msg.get("date", 0)).isoformat(),
                        "message_id": msg.get("message_id")
                    })
            return messages
        except Exception as e:
            print(f"Error getting updates: {e}")
            return []

    def send_message(self, chat_id: int, text: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "Sent" if data.get("ok") else data.get("description", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


class DiscordIntegration:
    API_BASE = "https://discord.com/api/v10"

    def __init__(self, config: Dict[str, Any]):
        self.bot_token = config.get("bot_token", "")
        self.headers = {"Authorization": f"Bot {self.bot_token}", "Content-Type": "application/json"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.API_BASE}/users/@me", headers=self.headers, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Bot: {data.get('username', 'unknown')}"}
            return {"success": False, "message": data.get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_guilds(self) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/users/@me/guilds", headers=self.headers, timeout=10)
            return resp.json() if resp.status_code == 200 else []
        except:
            return []

    def get_channels(self, guild_id: str) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/guilds/{guild_id}/channels", headers=self.headers, timeout=10)
            return [c for c in resp.json() if c.get("type") == 0] if resp.status_code == 200 else []
        except:
            return []

    def get_messages(self, channel_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/channels/{channel_id}/messages", headers=self.headers, params={"limit": limit}, timeout=10)
            if resp.status_code != 200:
                return []
            return [{
                "id": m["id"],
                "from": m.get("author", {}).get("username", "unknown"),
                "text": m.get("content", ""),
                "date": m.get("timestamp", ""),
                "channel_id": channel_id
            } for m in resp.json()]
        except:
            return []

    def send_message(self, channel_id: str, text: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.API_BASE}/channels/{channel_id}/messages", headers=self.headers, json={"content": text}, timeout=10)
            return {"success": resp.status_code == 201, "message": "Sent" if resp.status_code == 201 else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


class WhatsAppIntegration:
    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(self, config: Dict[str, Any]):
        self.phone_number_id = config.get("phone_number_id", "")
        self.access_token = config.get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.API_BASE}/{self.phone_number_id}", headers=selfheaders, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Phone: {data.get('display_phone_number', 'unknown')}"}
            return {"success": False, "message": data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def send_message(self, to: str, text: str) -> Dict[str, Any]:
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text}
            }
            resp = httpx.post(f"{self.API_BASE}/{self.phone_number_id}/messages", headers=self.headers, json=payload, timeout=10)
            data = resp.json()
            return {"success": "messages" in data, "message": "Sent" if "messages" in data else data.get("error", {}).get("message", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


class FacebookIntegration:
    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(self, config: Dict[str, Any]):
        self.page_id = config.get("page_id", "")
        self.access_token = config.get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.API_BASE}/me", headers=self.headers, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Page: {data.get('name', 'unknown')}"}
            return {"success": False, "message": data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/{self.page_id}/posts", headers=self.headers, params={"limit": limit}, timeout=10)
            data = resp.json()
            return [{
                "id": p["id"],
                "message": p.get("message", ""),
                "created_time": p.get("created_time", ""),
                "from": p.get("from", {}).get("name", "unknown")
            } for p in data.get("data", [])]
        except:
            return []

    def get_comments(self, post_id: str) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/{post_id}/comments", headers=self.headers, timeout=10)
            data = resp.json()
            return [{
                "id": c["id"],
                "message": c.get("message", ""),
                "from": c.get("from", {}).get("name", "unknown"),
                "created_time": c.get("created_time", "")
            } for c in data.get("data", [])]
        except:
            return []

    def post_comment(self, post_id: str, message: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.API_BASE}/{post_id}/comments", headers=self.headers, json={"message": message}, timeout=10)
            data = resp.json()
            return {"success": "id" in data, "message": "Commented" if "id" in data else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


class MessengerIntegration:
    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(self, config: Dict[str, Any]):
        self.page_id = config.get("page_id", "")
        self.access_token = config.get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.API_BASE}/me", headers=self.headers, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Page: {data.get('name', 'unknown')}"}
            return {"success": False, "message": data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def send_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        try:
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": text}
            }
            resp = httpx.post(f"{self.API_BASE}/me/messages", headers=self.headers, json=payload, timeout=10)
            data = resp.json()
            return {"success": "message_id" in data, "message": "Sent" if "message_id" in data else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


INTEGRATIONS = {
    "email": EmailIntegration,
    "telegram": TelegramIntegration,
    "discord": DiscordIntegration,
    "whatsapp": WhatsAppIntegration,
    "facebook": FacebookIntegration,
    "messenger": MessengerIntegration,
}


def get_integration(integration_type: str, config: Dict[str, Any]):
    cls = INTEGRATIONS.get(integration_type)
    if cls:
        return cls(config)
    return None
