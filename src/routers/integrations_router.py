from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.middleware.auth_middleware import get_current_user
from src.services.integrations_service import get_integration

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class IntegrationTest(BaseModel):
    integration_type: str
    config: Dict[str, Any]


class IntegrationConfig(BaseModel):
    integration_type: str
    name: str
    config: Dict[str, Any]
    assistant_id: Optional[str] = None


class SendMessage(BaseModel):
    to: str
    text: str
    reply_to: Optional[str] = None


class ComposeEmail(BaseModel):
    to: str
    subject: str
    body: str
    reply_to: Optional[str] = None


@router.post("/test")
async def test_integration(
    data: IntegrationTest,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration(data.integration_type, data.config)
    if not integration:
        raise HTTPException(status_code=400, detail=f"Unknown integration type: {data.integration_type}")

    result = integration.test_connection()
    return result


@router.post("/{integration_type}/read")
async def read_messages(
    integration_type: str,
    config: Dict[str, Any],
    folder: str = "INBOX",
    channel_id: str = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration(integration_type, config)
    if not integration:
        raise HTTPException(status_code=400, detail=f"Unknown integration type: {integration_type}")

    try:
        if integration_type == "email":
            messages = integration.read_emails(folder=folder, limit=limit)
        elif integration_type == "telegram":
            messages = integration.get_updates(limit=limit)
        elif integration_type == "discord":
            if channel_id:
                messages = integration.get_messages(channel_id, limit=limit)
            else:
                guilds = integration.get_guilds()
                messages = [{"guilds": guilds}]
        elif integration_type == "facebook":
            messages = integration.get_posts(limit=limit)
        else:
            messages = []

        return {"success": True, "messages": messages, "count": len(messages)}
    except Exception as e:
        return {"success": False, "error": str(e)[:200], "messages": []}


@router.post("/{integration_type}/send")
async def send_message(
    integration_type: str,
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration(integration_type, config)
    if not integration:
        raise HTTPException(status_code=400, detail=f"Unknown integration type: {integration_type}")

    try:
        if integration_type == "email":
            result = integration.send_email(to=data.to, subject="Reply", body=data.text, reply_to=data.reply_to)
        elif integration_type == "telegram":
            result = integration.send_message(chat_id=int(data.to), text=data.text)
        elif integration_type == "discord":
            result = integration.send_message(channel_id=data.to, text=data.text)
        elif integration_type == "whatsapp":
            result = integration.send_message(to=data.to, text=data.text)
        elif integration_type == "facebook":
            result = integration.post_comment(post_id=data.to, message=data.text)
        elif integration_type == "messenger":
            result = integration.send_message(recipient_id=data.to, text=data.text)
        else:
            result = {"success": False, "message": "Unsupported integration"}

        return result
    except Exception as e:
        return {"success": False, "message": str(e)[:200]}


@router.post("/email/compose")
async def compose_email(
    data: ComposeEmail,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("email", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Email integration not configured")

    result = integration.send_email(to=data.to, subject=data.subject, body=data.body, reply_to=data.reply_to)
    return result


@router.post("/email/read")
async def read_emails(
    config: Dict[str, Any],
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("email", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Email integration not configured")

    emails = integration.read_emails(folder=folder, limit=limit, unread_only=unread_only)
    return {"success": True, "emails": emails, "count": len(emails)}


@router.post("/telegram/updates")
async def get_telegram_updates(
    config: Dict[str, Any],
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("telegram", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Telegram integration not configured")

    messages = integration.get_updates(limit=limit)
    return {"success": True, "messages": messages, "count": len(messages)}


@router.post("/telegram/send")
async def send_telegram(
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("telegram", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Telegram integration not configured")

    result = integration.send_message(chat_id=int(data.to), text=data.text)
    return result


@router.post("/discord/guilds")
async def get_discord_guilds(
    config: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("discord", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Discord integration not configured")

    guilds = integration.get_guilds()
    return {"guilds": guilds}


@router.post("/discord/channels")
async def get_discord_channels(
    guild_id: str,
    config: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("discord", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Discord integration not configured")

    channels = integration.get_channels(guild_id)
    return {"channels": channels}


@router.post("/discord/messages")
async def get_discord_messages(
    channel_id: str,
    config: Dict[str, Any],
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("discord", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Discord integration not configured")

    messages = integration.get_messages(channel_id, limit=limit)
    return {"messages": messages}


@router.post("/discord/send")
async def send_discord(
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("discord", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Discord integration not configured")

    result = integration.send_message(channel_id=data.to, text=data.text)
    return result


@router.post("/facebook/posts")
async def get_facebook_posts(
    config: Dict[str, Any],
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("facebook", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Facebook integration not configured")

    posts = integration.get_posts(limit=limit)
    return {"posts": posts}


@router.post("/facebook/comments")
async def get_facebook_comments(
    post_id: str,
    config: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    integration = get_integration("facebook", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Facebook integration not configured")

    comments = integration.get_comments(post_id)
    return {"comments": comments}


@router.post("/facebook/comment")
async def post_facebook_comment(
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("facebook", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Facebook integration not configured")

    result = integration.post_comment(post_id=data.to, message=data.text)
    return result


@router.post("/whatsapp/send")
async def send_whatsapp(
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("whatsapp", config)
    if not integration:
        raise HTTPException(status_code=400, detail="WhatsApp integration not configured")

    result = integration.send_message(to=data.to, text=data.text)
    return result


@router.post("/messenger/send")
async def send_messenger(
    data: SendMessage,
    config: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user)
):
    if not config:
        raise HTTPException(status_code=400, detail="Config required")

    integration = get_integration("messenger", config)
    if not integration:
        raise HTTPException(status_code=400, detail="Messenger integration not configured")

    result = integration.send_message(recipient_id=data.to, text=data.text)
    return result
