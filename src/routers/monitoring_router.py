from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import re
from bs4 import BeautifulSoup
from datetime import datetime
import asyncio

from src.models.database import User
from src.middleware.auth_middleware import get_current_user
from src.models.engine import get_db_session

router = APIRouter(prefix="/api/monitor", tags=["Monitoring"])

class MonitorCheck(BaseModel):
    type: str
    url: str
    keywords: Optional[List[str]] = []
    name: Optional[str] = None

class MonitorResult(BaseModel):
    success: bool
    changes: List[Dict[str, Any]]
    message: str
    data: Optional[Dict[str, Any]] = None

@router.post("/check", response_model=MonitorResult)
async def check_monitor(
    data: MonitorCheck,
    current_user: User = Depends(get_current_user)
):
    try:
        if data.type == "website":
            return await check_website(data)
        elif data.type == "facebook":
            return await check_facebook(data)
        elif data.type == "ecommerce":
            return await check_ecommerce(data)
        elif data.type == "rss":
            return await check_rss(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown monitor type: {data.type}")
    except Exception as e:
        return MonitorResult(success=False, changes=[], message=str(e))

async def check_website(data: MonitorCheck) -> MonitorResult:
    changes = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(data.url)
            content = response.text

            if data.keywords:
                for keyword in data.keywords:
                    if keyword.lower() in content.lower():
                        changes.append({
                            "type": "keyword_found",
                            "keyword": keyword,
                            "message": f"Found keyword '{keyword}' on page"
                        })

            changes.append({
                "type": "fetched",
                "status_code": response.status_code,
                "content_length": len(content),
                "message": f"Fetched page successfully ({len(content)} bytes)"
            })

            return MonitorResult(
                success=True,
                changes=changes,
                message=f"Website check complete. Found {len(changes)} updates.",
                data={"status_code": response.status_code, "size": len(content)}
            )
        except httpx.RequestError as e:
            return MonitorResult(success=False, changes=[], message=f"Failed to fetch website: {str(e)}")

async def check_facebook(data: MonitorCheck) -> MonitorResult:
    changes = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await client.get(data.url, headers=headers)
            content = response.text

            soup = BeautifulSoup(content, 'html.parser')
            posts = soup.find_all(['div', 'article'], string=re.compile(r'post|update|shared', re.I))

            if posts:
                changes.append({
                    "type": "activity_detected",
                    "count": len(posts),
                    "message": f"Detected {len(posts)} potential posts/updates"
                })

            changes.append({
                "type": "fetched",
                "content_length": len(content),
                "message": "Facebook page fetched successfully"
            })

            return MonitorResult(
                success=True,
                changes=changes,
                message=f"Facebook check complete. Found {len(changes)} updates.",
                data={"posts_found": len(posts)}
            )
    except Exception as e:
        return MonitorResult(success=False, changes=[], message=f"Facebook check failed: {str(e)}")

async def check_ecommerce(data: MonitorCheck) -> MonitorResult:
    changes = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await client.get(data.url, headers=headers)
            content = response.text

            keywords_found = []
            if data.keywords:
                for keyword in data.keywords:
                    if keyword.lower() in content.lower():
                        keywords_found.append(keyword)
                        changes.append({
                            "type": "keyword_found",
                            "keyword": keyword,
                            "message": f"Found '{keyword}' on product page"
                        })

            price_match = re.search(r'[\$£€]?\s*[\d,]+\.?\d*', content)
            price = price_match.group(0) if price_match else "Unknown"

            changes.append({
                "type": "price_detected",
                "price": price,
                "message": f"Current price: {price}"
            })

            return MonitorResult(
                success=True,
                changes=changes,
                message=f"E-commerce check complete. Price: {price}. Keywords found: {len(keywords_found)}",
                data={"price": price, "keywords_found": keywords_found}
            )
    except Exception as e:
        return MonitorResult(success=False, changes=[], message=f"E-commerce check failed: {str(e)}")

async def check_rss(data: MonitorCheck) -> MonitorResult:
    changes = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(data.url)
            content = response.text

            soup = BeautifulSoup(content, 'xml')
            items = soup.find_all('item')[:10]

            new_items = []
            for item in items:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')

                if title and title.string:
                    new_items.append({
                        "title": title.string,
                        "link": link.string if link else "",
                        "date": pub_date.string if pub_date else ""
                    })

                    if data.keywords:
                        for keyword in data.keywords:
                            if keyword.lower() in title.string.lower():
                                changes.append({
                                    "type": "keyword_match",
                                    "keyword": keyword,
                                    "title": title.string,
                                    "message": f"Keyword '{keyword}' found in: {title.string}"
                                })

            return MonitorResult(
                success=True,
                changes=changes,
                message=f"RSS check complete. {len(new_items)} items, {len(changes)} keyword matches.",
                data={"items": new_items[:5]}
            )
    except Exception as e:
        return MonitorResult(success=False, changes=[], message=f"RSS check failed: {str(e)}")

@router.post("/notify")
async def send_notification(
    channel: str,
    recipient: str,
    message: str,
    current_user: User = Depends(get_current_user)
):
    try:
        if channel == "whatsapp":
            return await send_whatsapp_notification(recipient, message)
        elif channel == "email":
            return {"success": True, "message": "Email notification queued (mock)"}
        elif channel == "telegram":
            return {"success": True, "message": "Telegram notification queued (mock)"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")
    except Exception as e:
        return {"success": False, "message": str(e)}

async def send_whatsapp_notification(recipient: str, message: str):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8000/api/integrations/whatsapp/send",
                json={"to": recipient, "text": message}
            )
            result = response.json()
            return {"success": result.get("success", False), "message": result.get("message", "Sent")}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/history/{monitor_id}")
async def get_monitor_history(
    monitor_id: str,
    current_user: User = Depends(get_current_user)
):
    return {"monitor_id": monitor_id, "history": []}
