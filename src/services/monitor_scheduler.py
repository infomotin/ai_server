import os
import json
import time
import hashlib
import threading
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

DATA_DIR = "/www/AI_server/data"
MONITORS_FILE = os.path.join(DATA_DIR, "monitors.json")
MONITOR_HASHES_FILE = os.path.join(DATA_DIR, "monitor_hashes.json")
WHATSAPP_BRIDGE = "http://127.0.0.1:3333"
SESSION_ID = "wa_default"

scheduler = BackgroundScheduler(daemon=True)
_lock = threading.Lock()


def _load_monitors():
    if os.path.exists(MONITORS_FILE):
        with open(MONITORS_FILE, "r") as f:
            return json.load(f)
    return []


def _save_monitors(monitors):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MONITORS_FILE, "w") as f:
        json.dump(monitors, f, indent=2)


def _load_hashes():
    if os.path.exists(MONITOR_HASHES_FILE):
        with open(MONITOR_HASHES_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_hashes(hashes):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MONITOR_HASHES_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def crawl_website(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=30.0, follow_redirects=True, verify=False) as client:
            resp = client.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            full_text = soup.get_text(separator=" ", strip=True)
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")[:300]
            headings = [h.get_text(strip=True)[:100] for h in soup.find_all(["h1", "h2", "h3"])[:10]]
            import re
            prices = list(set(re.findall(r'[\$৳₹€£PKR]\s*[\d,]+\.?\d*|\d[\d,]*\.?\d*\s*(?:taka|bdt|usd|tk|rs)', full_text, re.I)))[:15]
            items = []
            for el in soup.find_all(["div", "article"], class_=lambda c: c and any(k in str(c).lower() for k in ["product", "item", "card", "post", "article", "story"]))[:5]:
                t = el.get_text(separator=" ", strip=True)[:200]
                if len(t) > 20:
                    items.append(t)
            links_count = len(soup.find_all("a", href=True))
            images_count = len(soup.find_all("img"))
            return {
                "success": True,
                "title": title,
                "meta_description": meta_desc,
                "text_length": len(full_text),
                "headings": headings[:5],
                "prices": prices,
                "items": items[:5],
                "links_count": links_count,
                "images_count": images_count,
                "content_hash": hashlib.md5(full_text.encode()).hexdigest(),
            }
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def send_whatsapp_message(to, text):
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{WHATSAPP_BRIDGE}/sessions/{SESSION_ID}/send",
                json={"to": to, "text": text},
            )
            return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def format_monitor_result(monitor, crawl_data):
    mtype = monitor.get("type", "website")
    name = monitor.get("name", "Website Monitor")
    url = monitor.get("url", "")
    keywords = monitor.get("keywords", "")

    lines = [f" *{name}*", f"URL: {url}", ""]

    if mtype == "ecommerce":
        lines.append(" E-commerce Update Detected!")
        if crawl_data.get("prices"):
            lines.append(" Prices found: " + ", ".join(crawl_data["prices"][:5]))
    elif mtype == "facebook":
        lines.append(" Facebook Page Update!")
    elif mtype == "news" or mtype == "rss":
        lines.append(" News/Feed Update!")
    else:
        lines.append(" Website Change Detected!")

    if crawl_data.get("title"):
        lines.append(f"Title: {crawl_data['title'][:80]}")
    if crawl_data.get("meta_description"):
        lines.append(f"Summary: {crawl_data['meta_description'][:150]}")
    if crawl_data.get("headings"):
        lines.append("")
        lines.append(" *Latest Headlines:*")
        for h in crawl_data["headings"][:5]:
            lines.append(f"  {h[:80]}")
    if crawl_data.get("items"):
        lines.append("")
        lines.append(" *Content:*")
        for item in crawl_data["items"][:3]:
            lines.append(f"  {item[:100]}...")
    if crawl_data.get("prices"):
        lines.append("")
        lines.append(" *Prices:* " + " | ".join(crawl_data["prices"][:5]))
    lines.append("")
    lines.append(f"Links: {crawl_data.get('links_count', 0)} | Images: {crawl_data.get('images_count', 0)}")
    lines.append(f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if keywords:
        lines.append(f"Keywords: {keywords}")

    return "\n".join(lines)


def run_monitor_check(monitor_id=None):
    with _lock:
        monitors = _load_monitors()
        hashes = {}

        if os.path.exists(MONITOR_HASHES_FILE):
            with open(MONITOR_HASHES_FILE, "r") as f:
                hashes = json.load(f)

        for m in monitors:
            if not m.get("active", False):
                continue
            if monitor_id and m.get("id") != monitor_id:
                continue

            m_id = m.get("id", "")
            m_url = m.get("url", "")
            m_phone = m.get("phone", "")
            m_type = m.get("type", "website")

            if not m_url or not m_phone:
                continue

            print(f"[Monitor] Checking {m.get('name', m_url)}...")

            crawl_data = crawl_website(m_url)

            if not crawl_data.get("success"):
                print(f"[Monitor] Crawl failed for {m_url}: {crawl_data.get('error')}")
                continue

            new_hash = crawl_data.get("content_hash", "")
            old_hash = hashes.get(m_id, "")

            if new_hash == old_hash:
                print(f"[Monitor] No change for {m.get('name', m_url)}")
                continue

            hashes[m_id] = new_hash

            msg = format_monitor_result(m, crawl_data)
            result = send_whatsapp_message(m_phone, msg)

            if result.get("success"):
                print(f"[Monitor] Sent WhatsApp to {m_phone} for {m.get('name', m_url)}")
                m["last_check"] = datetime.now().isoformat()
                m["last_change"] = datetime.now().isoformat()
                m["last_status"] = "change_detected"
            else:
                print(f"[Monitor] WhatsApp send failed: {result.get('error', 'unknown')}")
                m["last_status"] = "send_failed"

        _save_monitors(monitors)
        with open(MONITOR_HASHES_FILE, "w") as f:
            json.dump(hashes, f, indent=2)


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(
        run_monitor_check,
        "interval",
        minutes=5,
        id="monitor_check",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    print("[MonitorScheduler] Started - checking every 5 minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[MonitorScheduler] Stopped")


def add_monitor(monitor):
    monitors = _load_monitors()
    monitors.append(monitor)
    _save_monitors(monitors)
    return monitor


def update_monitor(monitor_id, updates):
    monitors = _load_monitors()
    for m in monitors:
        if m.get("id") == monitor_id:
            m.update(updates)
            _save_monitors(monitors)
            return m
    return None


def delete_monitor(monitor_id):
    monitors = _load_monitors()
    monitors = [m for m in monitors if m.get("id") != monitor_id]
    _save_monitors(monitors)


def get_monitors():
    return _load_monitors()


def get_scheduler_status():
    return {
        "running": scheduler.running,
        "jobs": len(scheduler.get_jobs()) if scheduler.running else 0,
    }
