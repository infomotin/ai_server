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
import asyncio

import httpx

# SDK Imports
try:
    import telegram
    from telegram import Bot as TelegramBot
    TELEGRAM_SDK_AVAILABLE = True
except ImportError:
    TELEGRAM_SDK_AVAILABLE = False

try:
    import discord
    from discord import Client as DiscordClient
    DISCORD_SDK_AVAILABLE = True
except ImportError:
    DISCORD_SDK_AVAILABLE = False

try:
    import facebook
    FACEBOOK_SDK_AVAILABLE = True
except ImportError:
    FACEBOOK_SDK_AVAILABLE = False


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
        if TELEGRAM_SDK_AVAILABLE and self.bot_token:
            self.bot = TelegramBot(token=self.bot_token)
        else:
            self.bot = None

    def test_connection(self) -> Dict[str, Any]:
        try:
            if self.bot:
                import asyncio
                loop = asyncio.new_event_loop()
                me = loop.run_until_complete(self.bot.get_me())
                loop.close()
                return {"success": True, "message": f"Bot: @{me.username}", "username": me.username, "id": me.id}
            resp = httpx.get(f"{self.base_url}/getMe", timeout=10)
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "message": f"Bot: @{data['result'].get('username', 'unknown')}"}
            return {"success": False, "message": data.get("description", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            if self.bot:
                import asyncio
                loop = asyncio.new_event_loop()
                updates = loop.run_until_complete(self.bot.get_updates(limit=limit))
                loop.close()
                messages = []
                for update in updates:
                    msg = update.message
                    if msg:
                        messages.append({
                            "id": str(update.update_id),
                            "from": msg.from_user.username or msg.from_user.first_name or "unknown",
                            "from_id": msg.from_user.id,
                            "chat_id": msg.chat.id,
                            "text": msg.text or "",
                            "date": msg.date.isoformat() if msg.date else "",
                            "message_id": msg.message_id
                        })
                return messages
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
            if self.bot:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.bot.send_message(chat_id=chat_id, text=text))
                loop.close()
                return {"success": True, "message": "Sent via SDK"}
            resp = httpx.post(f"{self.base_url}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "Sent" if data.get("ok") else data.get("description", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def send_photo(self, chat_id: int, photo: str, caption: str = "") -> Dict[str, Any]:
        try:
            if self.bot:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption))
                loop.close()
                return {"success": True, "message": "Photo sent via SDK"}
            resp = httpx.post(f"{self.base_url}/sendPhoto", json={"chat_id": chat_id, "photo": photo, "caption": caption}, timeout=10)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "Sent" if data.get("ok") else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def send_document(self, chat_id: int, document: str, caption: str = "") -> Dict[str, Any]:
        try:
            if self.bot:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self.bot.send_document(chat_id=chat_id, document=document, caption=caption))
                loop.close()
                return {"success": True, "message": "Document sent via SDK"}
            resp = httpx.post(f"{self.base_url}/sendDocument", json={"chat_id": chat_id, "document": document, "caption": caption}, timeout=10)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "Sent" if data.get("ok") else "Failed"}
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
                return {"success": True, "message": f"Bot: {data.get('username', 'unknown')}", "username": data.get('username'), "id": data.get('id')}
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

    def send_embed(self, channel_id: str, title: str, description: str, color: int = 0x5865F2) -> Dict[str, Any]:
        try:
            embed = {"title": title, "description": description, "color": color}
            resp = httpx.post(f"{self.API_BASE}/channels/{channel_id}/messages", headers=self.headers, json={"embeds": [embed]}, timeout=10)
            return {"success": resp.status_code == 201, "message": "Embed sent" if resp.status_code == 201 else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def send_file(self, channel_id: str, file_path: str, content: str = "") -> Dict[str, Any]:
        try:
            import os
            if not os.path.exists(file_path):
                return {"success": False, "message": "File not found"}
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                data = {'content': content} if content else {}
                resp = httpx.post(f"{self.API_BASE}/channels/{channel_id}/messages", headers={"Authorization": f"Bot {self.bot_token}"}, data=data, files=files, timeout=30)
            return {"success": resp.status_code == 201, "message": "File sent" if resp.status_code == 201 else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_webhooks(self, channel_id: str) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/channels/{channel_id}/webhooks", headers=self.headers, timeout=10)
            return resp.json() if resp.status_code == 200 else []
        except:
            return []

    def create_webhook(self, channel_id: str, name: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.API_BASE}/channels/{channel_id}/webhooks", headers=self.headers, json={"name": name}, timeout=10)
            return resp.json() if resp.status_code in (200, 201) else {}
        except:
            return {}


class WhatsAppIntegration:
    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(self, config: Dict[str, Any]):
        self.phone_number_id = config.get("phone_number_id", "")
        self.access_token = config.get("access_token", "")
        self.business_phone = config.get("business_phone", "")
        self.headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{self.API_BASE}/{self.phone_number_id}", headers=self.headers, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Phone: {data.get('display_phone_number', 'unknown')}", "phone": data.get('display_phone_number', ''), "verified_name": data.get('verified_name', '')}
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

    def send_template(self, to: str, template_name: str, language: str = "en", params: list = None) -> Dict[str, Any]:
        try:
            components = []
            if params:
                components.append({"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]})
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {"name": template_name, "language": {"code": language}, "components": components}
            }
            resp = httpx.post(f"{self.API_BASE}/{self.phone_number_id}/messages", headers=self.headers, json=payload, timeout=10)
            data = resp.json()
            return {"success": "messages" in data, "message": "Template sent" if "messages" in data else data.get("error", {}).get("message", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    @staticmethod
    def get_qr_link(business_phone: str, message: str = "") -> str:
        phone = ''.join(c for c in business_phone if c.isdigit() or c == '+')
        phone = phone.lstrip('+')
        if message:
            import urllib.parse
            return f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
        return f"https://wa.me/{phone}"


class FacebookIntegration:
    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(self, config: Dict[str, Any]):
        self.page_id = config.get("page_id", "")
        self.access_token = config.get("access_token", "")
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        if FACEBOOK_SDK_AVAILABLE and self.access_token:
            self.graph = facebook.GraphAPI(access_token=self.access_token, version="3.1.0")
        else:
            self.graph = None

    def test_connection(self) -> Dict[str, Any]:
        try:
            if self.graph:
                me = self.graph.get_object("me")
                if "id" in me:
                    return {"success": True, "message": f"Page: {me.get('name', 'unknown')}", "id": me.get('id'), "name": me.get('name')}
            resp = httpx.get(f"{self.API_BASE}/me", headers=self.headers, timeout=10)
            data = resp.json()
            if "id" in data:
                return {"success": True, "message": f"Page: {data.get('name', 'unknown')}"}
            return {"success": False, "message": data.get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            if self.graph:
                posts = self.graph.get_connections(self.page_id, "posts", limit=limit)
                return [{
                    "id": p["id"],
                    "message": p.get("message", ""),
                    "created_time": p.get("created_time", ""),
                    "from": p.get("from", {}).get("name", "unknown")
                } for p in posts.get("data", [])]
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
            if self.graph:
                comments = self.graph.get_connections(post_id, "comments")
                return [{
                    "id": c["id"],
                    "message": c.get("message", ""),
                    "from": c.get("from", {}).get("name", "unknown"),
                    "created_time": c.get("created_time", "")
                } for c in comments.get("data", [])]
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
            if self.graph:
                result = self.graph.put_object(post_id, "comments", message=message)
                return {"success": "id" in result, "message": "Commented via SDK"}
            resp = httpx.post(f"{self.API_BASE}/{post_id}/comments", headers=self.headers, json={"message": message}, timeout=10)
            data = resp.json()
            return {"success": "id" in data, "message": "Commented" if "id" in data else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_page_info(self) -> Dict[str, Any]:
        try:
            if self.graph:
                info = self.graph.get_object(self.page_id, fields="id,name,fan_count,followers_count,category,about")
                return {"success": True, "data": info}
            resp = httpx.get(f"{self.API_BASE}/{self.page_id}", headers=self.headers, params={"fields": "id,name,fan_count,followers_count,category,about"}, timeout=10)
            return {"success": True, "data": resp.json()}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_insights(self, metric: str = "page_engagement") -> Dict[str, Any]:
        try:
            if self.graph:
                insights = self.graph.get_connections(self.page_id, "insights", metric=metric, period="day")
                return {"success": True, "data": insights.get("data", [])}
            resp = httpx.get(f"{self.API_BASE}/{self.page_id}/insights", headers=self.headers, params={"metric": metric, "period": "day"}, timeout=10)
            return {"success": True, "data": resp.json().get("data", [])}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def publish_post(self, message: str) -> Dict[str, Any]:
        try:
            if self.graph:
                result = self.graph.put_object(self.page_id, "feed", message=message)
                return {"success": "id" in result, "message": "Post published via SDK", "post_id": result.get("id")}
            resp = httpx.post(f"{self.API_BASE}/{self.page_id}/feed", headers=self.headers, json={"message": message}, timeout=10)
            data = resp.json()
            return {"success": "id" in data, "message": "Post published" if "id" in data else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def upload_photo(self, image_path: str, message: str = "") -> Dict[str, Any]:
        try:
            if self.graph:
                with open(image_path, 'rb') as f:
                    result = self.graph.put_photo(image=f, message=message, album_path=f"{self.page_id}/photos")
                return {"success": True, "message": "Photo uploaded via SDK"}
            return {"success": False, "message": "SDK not available"}
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


class TwitterIntegration:
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.access_token = config.get("access_token", "")
        self.access_token_secret = config.get("access_token_secret", "")
        self.bearer_token = config.get("bearer_token", "")
        if all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            try:
                import tweepy
                auth = tweepy.OAuth1UserHandler(self.api_key, self.api_secret, self.access_token, self.access_token_secret)
                self.client = tweepy.API(auth)
            except:
                self.client = None
        else:
            self.client = None

    def test_connection(self) -> Dict[str, Any]:
        try:
            if self.client:
                me = self.client.verify_credentials()
                return {"success": True, "message": f"@{me.screen_name}", "username": me.screen_name, "name": me.name}
            return {"success": False, "message": "Twitter SDK not configured. Provide API keys."}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_timeline(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            if self.client:
                tweets = self.client.home_timeline(count=limit)
                return [{"id": str(t.id), "text": t.text, "from": t.user.screen_name, "created_at": t.created_at.isoformat()} for t in tweets]
            return []
        except:
            return []

    def get_mentions(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            if self.client:
                mentions = self.client.mentions_timeline(count=limit)
                return [{"id": str(m.id), "text": m.text, "from": m.user.screen_name, "created_at": m.created_at.isoformat()} for m in mentions]
            return []
        except:
            return []

    def send_tweet(self, text: str) -> Dict[str, Any]:
        try:
            if self.client:
                tweet = self.client.update_status(text)
                return {"success": True, "message": "Tweet posted", "tweet_id": str(tweet.id)}
            return {"success": False, "message": "Twitter SDK not configured"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def reply_tweet(self, tweet_id: str, text: str) -> Dict[str, Any]:
        try:
            if self.client:
                tweet = self.client.update_status(text, in_reply_to_status_id=tweet_id)
                return {"success": True, "message": "Reply posted", "tweet_id": str(tweet.id)}
            return {"success": False, "message": "Twitter SDK not configured"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def retweet(self, tweet_id: str) -> Dict[str, Any]:
        try:
            if self.client:
                self.client.retweet(tweet_id)
                return {"success": True, "message": "Retweeted"}
            return {"success": False, "message": "Twitter SDK not configured"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def search_tweets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            if self.client:
                tweets = tweepy.Cursor(self.client.search_tweets, q=query, lang="en").items(limit)
                return [{"id": str(t.id), "text": t.text, "from": t.user.screen_name, "created_at": t.created_at.isoformat()} for t in tweets]
            return []
        except:
            return []


class SlackIntegration:
    API_BASE = "https://slack.com/api"

    def __init__(self, config: Dict[str, Any]):
        self.bot_token = config.get("bot_token", "")
        self.app_token = config.get("app_token", "")
        self.headers = {"Authorization": f"Bearer {self.bot_token}", "Content-Type": "application/json"}

    def test_connection(self) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.API_BASE}/auth.test", headers=self.headers, timeout=10)
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "message": f"Workspace: {data.get('team', 'unknown')}", "team": data.get("team"), "user": data.get("user")}
            return {"success": False, "message": data.get("error", "Unknown error")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_channels(self) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/conversations.list", headers=self.headers, params={"types": "public_channel,private_channel"}, timeout=10)
            data = resp.json()
            if data.get("ok"):
                return [{"id": c["id"], "name": c["name"], "is_member": c.get("is_member", False)} for c in data.get("channels", [])]
            return []
        except:
            return []

    def get_messages(self, channel_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            resp = httpx.get(f"{self.API_BASE}/conversations.history", headers=self.headers, params={"channel": channel_id, "limit": limit}, timeout=10)
            data = resp.json()
            if data.get("ok"):
                return [{"id": m["ts"], "text": m.get("text", ""), "from": m.get("user", "unknown"), "date": datetime.fromtimestamp(float(m["ts"])).isoformat()} for m in data.get("messages", [])]
            return []
        except:
            return []

    def send_message(self, channel_id: str, text: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.API_BASE}/chat.postMessage", headers=self.headers, json={"channel": channel_id, "text": text}, timeout=10)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "Sent" if data.get("ok") else data.get("error", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def upload_file(self, channel_id: str, file_path: str, title: str = "") -> Dict[str, Any]:
        try:
            import os
            if not os.path.exists(file_path):
                return {"success": False, "message": "File not found"}
            with open(file_path, 'rb') as f:
                resp = httpx.post(f"{self.API_BASE}/files.upload", headers={"Authorization": f"Bearer {self.bot_token}"}, data={"channels": channel_id, "title": title}, files={"file": (os.path.basename(file_path), f)}, timeout=30)
            data = resp.json()
            return {"success": data.get("ok", False), "message": "File uploaded" if data.get("ok") else "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}


INTEGRATIONS = {
    "email": EmailIntegration,
    "telegram": TelegramIntegration,
    "discord": DiscordIntegration,
    "whatsapp": WhatsAppIntegration,
    "facebook": FacebookIntegration,
    "messenger": MessengerIntegration,
    "twitter": TwitterIntegration,
    "slack": SlackIntegration,
}


def get_integration(integration_type: str, config: Dict[str, Any]):
    cls = INTEGRATIONS.get(integration_type)
    if cls:
        return cls(config)
    return None


class IntegrationsService:
    def test_integration(self, db, integration_id: str, user_id: int) -> Dict[str, Any]:
        from src.models.database import AssistantIntegration
        integration = db.query(AssistantIntegration).filter(AssistantIntegration.id == integration_id).first()
        if not integration:
            return {"success": False, "message": "Integration not found"}
        config = json.loads(integration.config) if integration.config else {}
        itype = integration.integration_type
        if itype in ("imap", "smtp", "email"):
            client = EmailIntegration(config)
            res = client.test_connection()
        elif itype == "telegram":
            client = TelegramIntegration(config)
            res = client.test_connection()
        elif itype == "whatsapp_api":
            return {"success": False, "message": "WhatsApp API test not supported yet"}
        elif itype == "facebook_api":
            client = FacebookIntegration(config)
            res = client.test_connection()
        elif itype == "slack":
            return {"success": True, "message": "Slack integration configured (API test requires bot presence)"}
        elif itype == "github":
            return {"success": True, "message": "GitHub token saved"}
        elif itype == "notification":
            return {"success": True, "message": "Notification integration saved"}
        else:
            return {"success": True, "message": f"{itype} integration saved"}
        if res.get("success"):
            integration.status = "connected"
        else:
            integration.status = "error"
        db.commit()
        return res


integrations_service = IntegrationsService()
