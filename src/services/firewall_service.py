import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import ModelFirewallProfile, ModelFirewallRule, ModelFirewallLog


PROTECTION_MODES = {
    "lockdown": {
        "name": "Lockdown",
        "description": "Maximum security - blocks everything except explicitly allowed",
        "icon": "fas fa-shield-halved",
        "color": "red",
        "default_action": "deny",
        "require_approval": True,
        "max_tokens": 500,
        "rate_limit": 10,
        "rules": [
            {"name": "Block All by Default", "category": "content", "pattern": ".*", "action": "deny", "response": "Access denied. This model is in Lockdown mode."},
            {"name": "Allow System Queries Only", "category": "topic", "pattern": "^(status|help|version|info)$", "action": "allow"},
            {"name": "Human Approval for All", "category": "action", "pattern": ".*", "action": "human_review", "response": "This request requires human approval."},
        ]
    },
    "over_protection": {
        "name": "Over Protection",
        "description": "High security - blocks risky content, reviews sensitive topics",
        "icon": "fas fa-shield",
        "color": "amber",
        "default_action": "allow",
        "require_approval": True,
        "max_tokens": 1000,
        "rate_limit": 20,
        "rules": [
            {"name": "Block PII Exposure", "category": "content", "pattern": "(ssn|social security|credit card|password|api.?key|secret)", "action": "deny", "response": "I cannot share personal or sensitive information."},
            {"name": "Block Harmful Content", "category": "content", "pattern": "(hack|exploit|malware|phishing|bomb|weapon|drug.?making)", "action": "deny", "response": "I cannot assist with harmful or illegal activities."},
            {"name": "Review Financial Topics", "category": "topic", "pattern": "(invest|stock|crypto|transfer|wire|payment)", "action": "human_review", "response": "Financial topics require human review."},
            {"name": "Review Code Execution", "category": "action", "pattern": "(execute|run|eval|exec|system|shell|terminal)", "action": "human_review", "response": "Code execution requires human approval."},
            {"name": "Block Competitor Info", "category": "topic", "pattern": "(competitor|rival|confidential|internal.?only)", "action": "deny", "response": "I cannot share competitor or confidential information."},
        ]
    },
    "standard": {
        "name": "Standard",
        "description": "Balanced security - basic protections with sensible defaults",
        "icon": "fas fa-check-shield",
        "color": "blue",
        "default_action": "allow",
        "require_approval": False,
        "max_tokens": 2000,
        "rate_limit": 30,
        "rules": [
            {"name": "Block Profanity", "category": "content", "pattern": "(damn|hell|shit|fuck|ass)", "action": "deny", "response": "Please keep your language professional."},
            {"name": "Block PII", "category": "content", "pattern": "(\\d{3}-\\d{2}-\\d{4}|\\d{16}|password\\s*[:=])", "action": "deny", "response": "I cannot process personal identification information."},
            {"name": "Allow General Topics", "category": "topic", "pattern": ".*", "action": "allow"},
        ]
    },
    "open": {
        "name": "Open",
        "description": "Minimal security - only blocks clearly harmful content",
        "icon": "fas fa-lock-open",
        "color": "green",
        "default_action": "allow",
        "require_approval": False,
        "max_tokens": 4000,
        "rate_limit": 60,
        "rules": [
            {"name": "Block Illegal Content", "category": "content", "pattern": "(how to (make|build|create).*(bomb|weapon|drug|poison))", "action": "deny", "response": "I cannot assist with illegal activities."},
            {"name": "Allow Everything Else", "category": "topic", "pattern": ".*", "action": "allow"},
        ]
    },
    "custom": {
        "name": "Custom",
        "description": "Your own rules - fully customizable firewall",
        "icon": "fas fa-cog",
        "color": "purple",
        "default_action": "allow",
        "require_approval": False,
        "max_tokens": 2000,
        "rate_limit": 30,
        "rules": []
    }
}

CATEGORIES = {
    "content": {"name": "Content Filter", "icon": "fas fa-filter", "description": "Filter based on message content"},
    "topic": {"name": "Topic Restriction", "icon": "fas fa-folder-tree", "description": "Allow/block specific topics"},
    "action": {"name": "Action Control", "icon": "fas fa-bolt", "description": "Control what the model can do"},
    "user": {"name": "User Restriction", "icon": "fas fa-user-shield", "description": "Restrict by user or role"},
    "token": {"name": "Token Limit", "icon": "fas fa-coins", "description": "Limit token usage"},
    "time": {"name": "Time-based", "icon": "fas fa-clock", "description": "Time-based access rules"},
}

ACTIONS = {
    "allow": {"name": "Allow", "icon": "fas fa-check-circle", "color": "green"},
    "deny": {"name": "Deny", "icon": "fas fa-ban", "color": "red"},
    "human_review": {"name": "Human Review", "icon": "fas fa-user-check", "color": "amber"},
    "log": {"name": "Log Only", "icon": "fas fa-file-alt", "color": "blue"},
}


class ModelFirewallService:
    def get_modes(self) -> Dict[str, Any]:
        return PROTECTION_MODES

    def get_categories(self) -> Dict[str, Any]:
        return CATEGORIES

    def get_actions(self) -> Dict[str, Any]:
        return ACTIONS

    def get_profiles(self, db: Session, user_id: str) -> List[ModelFirewallProfile]:
        return db.query(ModelFirewallProfile).filter(
            ModelFirewallProfile.user_id == user_id
        ).order_by(ModelFirewallProfile.created_at.desc()).all()

    def get_profile(self, db: Session, profile_id: str, user_id: str) -> Optional[ModelFirewallProfile]:
        return db.query(ModelFirewallProfile).filter(
            ModelFirewallProfile.id == profile_id,
            ModelFirewallProfile.user_id == user_id
        ).first()

    def create_profile(self, db: Session, user_id: str, name: str, description: str = None,
                       model_id: str = None, protection_mode: str = "standard") -> ModelFirewallProfile:
        mode_config = PROTECTION_MODES.get(protection_mode, PROTECTION_MODES["standard"])

        profile = ModelFirewallProfile(
            user_id=user_id,
            name=name,
            description=description or f"{mode_config['name']} firewall profile",
            model_id=model_id,
            protection_mode=protection_mode,
            max_tokens_per_request=mode_config["max_tokens"],
            rate_limit_per_minute=mode_config["rate_limit"],
            require_human_approval_above=500,
            log_all_requests=True,
            is_active=False
        )
        db.add(profile)
        db.flush()

        for rule_data in mode_config.get("rules", []):
            rule = ModelFirewallRule(
                profile_id=profile.id,
                name=rule_data["name"],
                rule_type="auto",
                category=rule_data["category"],
                pattern=rule_data["pattern"],
                action=rule_data["action"],
                response_message=rule_data.get("response"),
                priority=0,
                is_active=True
            )
            db.add(rule)

        db.commit()
        db.refresh(profile)
        return profile

    def update_profile(self, db: Session, profile_id: str, user_id: str, **kwargs) -> Optional[ModelFirewallProfile]:
        profile = self.get_profile(db, profile_id, user_id)
        if not profile:
            return None

        for key, value in kwargs.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        db.commit()
        db.refresh(profile)
        return profile

    def delete_profile(self, db: Session, profile_id: str, user_id: str) -> bool:
        profile = self.get_profile(db, profile_id, user_id)
        if not profile:
            return False
        db.delete(profile)
        db.commit()
        return True

    def activate_profile(self, db: Session, profile_id: str, user_id: str) -> Optional[ModelFirewallProfile]:
        db.query(ModelFirewallProfile).filter(
            ModelFirewallProfile.user_id == user_id
        ).update({"is_active": False})

        profile = self.get_profile(db, profile_id, user_id)
        if profile:
            profile.is_active = True
            db.commit()
            db.refresh(profile)
        return profile

    def get_rules(self, db: Session, profile_id: str) -> List[ModelFirewallRule]:
        return db.query(ModelFirewallRule).filter(
            ModelFirewallRule.profile_id == profile_id
        ).order_by(ModelFirewallRule.priority.desc(), ModelFirewallRule.created_at.desc()).all()

    def add_rule(self, db: Session, profile_id: str, name: str, category: str,
                 pattern: str, action: str, response_message: str = None, priority: int = 0) -> Optional[ModelFirewallRule]:
        profile = db.query(ModelFirewallProfile).filter(ModelFirewallProfile.id == profile_id).first()
        if not profile:
            return None

        rule = ModelFirewallRule(
            profile_id=profile_id,
            name=name,
            rule_type="custom",
            category=category,
            pattern=pattern,
            action=action,
            response_message=response_message,
            priority=priority,
            is_active=True
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def update_rule(self, db: Session, rule_id: str, **kwargs) -> Optional[ModelFirewallRule]:
        rule = db.query(ModelFirewallRule).filter(ModelFirewallRule.id == rule_id).first()
        if not rule:
            return None

        for key, value in kwargs.items():
            if hasattr(rule, key) and value is not None:
                setattr(rule, key, value)

        db.commit()
        db.refresh(rule)
        return rule

    def delete_rule(self, db: Session, rule_id: str) -> bool:
        rule = db.query(ModelFirewallRule).filter(ModelFirewallRule.id == rule_id).first()
        if not rule:
            return False
        db.delete(rule)
        db.commit()
        return True

    def check_request(self, db: Session, profile_id: str, request_text: str,
                      ip_address: str = None) -> Dict[str, Any]:
        profile = db.query(ModelFirewallProfile).filter(
            ModelFirewallProfile.id == profile_id,
            ModelFirewallProfile.is_active == True
        ).first()

        if not profile:
            return {"action": "allow", "reason": "No active firewall", "matched_rule": None}

        if profile.log_all_requests:
            tokens_used = len(request_text.split()) * 2
            if tokens_used > profile.max_tokens_per_request:
                log = ModelFirewallLog(
                    profile_id=profile_id,
                    request_text=request_text[:500],
                    action_taken="deny",
                    matched_pattern="token_limit",
                    ip_address=ip_address,
                    tokens_used=tokens_used
                )
                db.add(log)
                db.commit()
                return {"action": "deny", "reason": "Token limit exceeded", "matched_rule": None}

        rules = self.get_rules(db, profile_id)
        for rule in rules:
            if not rule.is_active:
                continue

            try:
                if re.search(rule.pattern, request_text, re.IGNORECASE):
                    rule.hit_count += 1

                    log = ModelFirewallLog(
                        profile_id=profile_id,
                        rule_id=rule.id,
                        request_text=request_text[:500],
                        action_taken=rule.action,
                        matched_pattern=rule.pattern,
                        ip_address=ip_address,
                        tokens_used=len(request_text.split()) * 2
                    )
                    db.add(log)
                    db.commit()

                    return {
                        "action": rule.action,
                        "reason": rule.response_message or f"Matched rule: {rule.name}",
                        "matched_rule": rule.name
                    }
            except re.error:
                continue

        default_action = PROTECTION_MODES.get(profile.protection_mode, {}).get("default_action", "allow")
        return {"action": default_action, "reason": "No rules matched", "matched_rule": None}

    def get_logs(self, db: Session, profile_id: str, limit: int = 50) -> List[ModelFirewallLog]:
        return db.query(ModelFirewallLog).filter(
            ModelFirewallLog.profile_id == profile_id
        ).order_by(ModelFirewallLog.created_at.desc()).limit(limit).all()

    def get_stats(self, db: Session, user_id: str) -> Dict[str, Any]:
        profiles = self.get_profiles(db, user_id)
        active = [p for p in profiles if p.is_active]
        total_rules = sum(len(self.get_rules(db, p.id)) for p in profiles)

        total_logs = 0
        blocked = 0
        reviewed = 0
        for p in profiles:
            logs = self.get_logs(db, p.id, limit=1000)
            total_logs += len(logs)
            blocked += sum(1 for l in logs if l.action_taken == "deny")
            reviewed += sum(1 for l in logs if l.action_taken == "human_review")

        return {
            "total_profiles": len(profiles),
            "active_profiles": len(active),
            "total_rules": total_rules,
            "total_requests": total_logs,
            "blocked_requests": blocked,
            "pending_reviews": reviewed,
            "block_rate": f"{(blocked / total_logs * 100):.1f}%" if total_logs > 0 else "0%"
        }

    def get_profile_with_rules(self, db: Session, profile_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        profile = self.get_profile(db, profile_id, user_id)
        if not profile:
            return None

        rules = self.get_rules(db, profile_id)
        logs = self.get_logs(db, profile_id, limit=20)

        return {
            "profile": profile,
            "rules": rules,
            "recent_logs": logs,
            "mode_config": PROTECTION_MODES.get(profile.protection_mode, {}),
        }


firewall_service = ModelFirewallService()
