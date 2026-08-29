from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.engine import get_db_session
from src.models.database import User
from src.models.mcp_models import MCPServer, MCPTool
from src.middleware.auth_middleware import get_current_user
from src.services.mcp_service import mcp_manager

router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPServerCreate(BaseModel):
    name: str
    server_type: str
    command: Optional[str] = None
    args: Optional[List[str]] = []
    env: Optional[Dict[str, str]] = {}
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = {}


@router.get("/servers")
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    servers = db.query(MCPServer).filter_by(user_id=current_user.id).all()
    return [{
        "id": s.id,
        "name": s.name,
        "server_type": s.server_type,
        "command": s.command,
        "args": s.args,
        "url": s.url,
        "is_active": s.is_active,
        "status": s.status,
        "tools_count": s.tools_count,
        "error_message": s.error_message,
        "created_at": s.created_at.isoformat() if s.created_at else None
    } for s in servers]


@router.post("/servers")
async def create_server(
    data: MCPServerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    server = MCPServer(
        user_id=current_user.id,
        name=data.name,
        server_type=data.server_type,
        command=data.command,
        args=data.args,
        env=data.env,
        url=data.url,
        headers=data.headers
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return {"success": True, "id": server.id}


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    server = db.query(MCPServer).filter_by(id=server_id, user_id=current_user.id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    await mcp_manager.disconnect_server(server.name)
    db.query(MCPTool).filter_by(server_id=server.id).delete()
    db.delete(server)
    db.commit()
    return {"success": True}


@router.post("/servers/{server_id}/connect")
async def connect_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    server = db.query(MCPServer).filter_by(id=server_id, user_id=current_user.id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    result = await mcp_manager.connect_server({
        "name": server.name,
        "server_type": server.server_type,
        "command": server.command,
        "args": server.args or [],
        "env": server.env or {},
        "url": server.url,
        "headers": server.headers or {}
    })

    if result.get("success"):
        server.status = "connected"
        server.error_message = None
        server.last_connected_at = datetime.utcnow()

        db.query(MCPTool).filter_by(server_id=server.id).delete()
        for tool in result.get("tools", []):
            db.add(MCPTool(
                server_id=server.id,
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema")
            ))
        server.tools_count = len(result.get("tools", []))
    else:
        server.status = "error"
        server.error_message = result.get("error", "Connection failed")

    db.commit()
    return result


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    server = db.query(MCPServer).filter_by(id=server_id, user_id=current_user.id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    await mcp_manager.disconnect_server(server.name)
    server.status = "disconnected"
    db.commit()
    return {"success": True}


@router.post("/servers/{server_id}/toggle")
async def toggle_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    server = db.query(MCPServer).filter_by(id=server_id, user_id=current_user.id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.is_active = not server.is_active
    db.commit()
    return {"success": True, "is_active": server.is_active}


@router.get("/tools")
async def list_all_tools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    tools = mcp_manager.get_all_tools()
    return {"tools": tools, "count": len(tools)}


@router.post("/tools/call")
async def call_tool(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    server_name = data.get("server_name", "")
    tool_name = data.get("tool_name", "")
    arguments = data.get("arguments", {})

    result = await mcp_manager.call_tool(server_name, tool_name, arguments)
    return result


@router.get("/stats")
async def mcp_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    servers = db.query(MCPServer).filter_by(user_id=current_user.id).count()
    connected = db.query(MCPServer).filter_by(user_id=current_user.id, status="connected").count()
    tools = db.query(MCPTool).join(MCPServer).filter(MCPServer.user_id == current_user.id).count()
    return {
        "total_servers": servers,
        "connected_servers": connected,
        "total_tools": tools
    }
