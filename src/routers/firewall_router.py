from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.middleware.auth_middleware import get_current_user
from src.services.firewall_service import firewall_service

router = APIRouter(prefix="/firewall", tags=["Model Firewall"])


class FirewallProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    model_id: Optional[str] = None
    protection_mode: str = Field(default="standard", pattern="^(lockdown|over_protection|standard|open|custom)$")


class FirewallProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_id: Optional[str] = None
    protection_mode: Optional[str] = None
    max_tokens_per_request: Optional[int] = None
    rate_limit_per_minute: Optional[int] = None
    require_human_approval_above: Optional[int] = None
    log_all_requests: Optional[bool] = None


class FirewallRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., pattern="^(content|topic|action|user|token|time)$")
    pattern: str = Field(..., min_length=1)
    action: str = Field(..., pattern="^(allow|deny|human_review|log)$")
    response_message: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=1000)


class FirewallRuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    pattern: Optional[str] = None
    action: Optional[str] = None
    response_message: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class FirewallCheckRequest(BaseModel):
    request_text: str = Field(..., min_length=1)


@router.get("/modes")
async def get_firewall_modes(current_user: User = Depends(get_current_user)):
    return firewall_service.get_modes()


@router.get("/categories")
async def get_firewall_categories(current_user: User = Depends(get_current_user)):
    return firewall_service.get_categories()


@router.get("/actions")
async def get_firewall_actions(current_user: User = Depends(get_current_user)):
    return firewall_service.get_actions()


@router.get("/profiles")
async def list_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profiles = firewall_service.get_profiles(db, current_user.id)
    return [{"id": p.id, "name": p.name, "description": p.description,
             "protection_mode": p.protection_mode, "model_id": p.model_id,
             "is_active": p.is_active, "created_at": str(p.created_at)}
            for p in profiles]


@router.post("/profiles")
async def create_profile(
    data: FirewallProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profile = firewall_service.create_profile(
        db=db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        model_id=data.model_id,
        protection_mode=data.protection_mode
    )
    return {"id": profile.id, "name": profile.name, "protection_mode": profile.protection_mode}


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    data = firewall_service.get_profile_with_rules(db, profile_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = data["profile"]
    rules = data["rules"]
    logs = data["recent_logs"]

    return {
        "profile": {
            "id": profile.id, "name": profile.name, "description": profile.description,
            "protection_mode": profile.protection_mode, "model_id": profile.model_id,
            "max_tokens_per_request": profile.max_tokens_per_request,
            "rate_limit_per_minute": profile.rate_limit_per_minute,
            "require_human_approval_above": profile.require_human_approval_above,
            "log_all_requests": profile.log_all_requests,
            "is_active": profile.is_active, "created_at": str(profile.created_at)
        },
        "rules": [{"id": r.id, "name": r.name, "rule_type": r.rule_type,
                   "category": r.category, "pattern": r.pattern, "action": r.action,
                   "response_message": r.response_message, "priority": r.priority,
                   "is_active": r.is_active, "hit_count": r.hit_count}
                  for r in rules],
        "recent_logs": [{"id": l.id, "request_text": l.request_text[:200],
                         "action_taken": l.action_taken, "matched_pattern": l.matched_pattern,
                         "tokens_used": l.tokens_used, "created_at": str(l.created_at)}
                        for l in logs],
        "mode_config": data["mode_config"]
    }


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    data: FirewallProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    profile = firewall_service.update_profile(db, profile_id, current_user.id, **update_data)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"id": profile.id, "name": profile.name}


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = firewall_service.delete_profile(db, profile_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"message": "Profile deleted"}


@router.post("/profiles/{profile_id}/activate")
async def activate_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profile = firewall_service.activate_profile(db, profile_id, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"message": "Profile activated", "id": profile.id}


@router.post("/profiles/{profile_id}/rules")
async def add_rule(
    profile_id: str,
    data: FirewallRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    rule = firewall_service.add_rule(
        db=db,
        profile_id=profile_id,
        name=data.name,
        category=data.category,
        pattern=data.pattern,
        action=data.action,
        response_message=data.response_message,
        priority=data.priority
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"id": rule.id, "name": rule.name, "action": rule.action}


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    data: FirewallRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    rule = firewall_service.update_rule(db, rule_id, **update_data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"id": rule.id, "name": rule.name}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = firewall_service.delete_rule(db, rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted"}


@router.post("/check/{profile_id}")
async def check_request(
    profile_id: str,
    data: FirewallCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    result = firewall_service.check_request(db, profile_id, data.request_text)
    return result


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return firewall_service.get_stats(db, current_user.id)
