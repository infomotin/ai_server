from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import UsageLog, APIKey


class UsageService:
    def log_usage(
        self,
        db: Session,
        api_key_id: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None
    ) -> UsageLog:
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

        usage_log = UsageLog(
            api_key_id=api_key_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms
        )

        db.add(usage_log)
        db.commit()
        db.refresh(usage_log)
        return usage_log

    def get_key_usage(
        self,
        db: Session,
        api_key_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        query = db.query(UsageLog).filter(UsageLog.api_key_id == api_key_id)

        if start_date:
            query = query.filter(UsageLog.created_at >= start_date)
        if end_date:
            query = query.filter(UsageLog.created_at <= end_date)

        logs = query.all()

        total_requests = len(logs)
        total_tokens = sum(log.total_tokens or 0 for log in logs)
        total_prompt = sum(log.prompt_tokens or 0 for log in logs)
        total_completion = sum(log.completion_tokens or 0 for log in logs)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "period_start": start_date or logs[0].created_at if logs else None,
            "period_end": end_date or datetime.now(timezone.utc)
        }

    def get_user_usage(
        self,
        db: Session,
        user_id: str,
        days: int = 30
    ) -> dict:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        api_keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
        key_ids = [key.id for key in api_keys]

        if not key_ids:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "period_start": start_date,
                "period_end": datetime.now(timezone.utc)
            }

        logs = db.query(UsageLog).filter(
            UsageLog.api_key_id.in_(key_ids),
            UsageLog.created_at >= start_date
        ).all()

        total_requests = len(logs)
        total_tokens = sum(log.total_tokens or 0 for log in logs)
        total_prompt = sum(log.prompt_tokens or 0 for log in logs)
        total_completion = sum(log.completion_tokens or 0 for log in logs)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "period_start": start_date,
            "period_end": datetime.now(timezone.utc)
        }

    def get_recent_usage(
        self,
        db: Session,
        api_key_id: str,
        limit: int = 100
    ) -> List[UsageLog]:
        return db.query(UsageLog).filter(
            UsageLog.api_key_id == api_key_id
        ).order_by(UsageLog.created_at.desc()).limit(limit).all()

    def get_usage_stats_by_model(
        self,
        db: Session,
        user_id: str,
        days: int = 30
    ) -> dict:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        api_keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
        key_ids = [key.id for key in api_keys]

        if not key_ids:
            return {}

        logs = db.query(UsageLog).filter(
            UsageLog.api_key_id.in_(key_ids),
            UsageLog.created_at >= start_date
        ).all()

        model_stats = {}
        for log in logs:
            if log.model not in model_stats:
                model_stats[log.model] = {
                    "requests": 0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0
                }
            model_stats[log.model]["requests"] += 1
            model_stats[log.model]["total_tokens"] += log.total_tokens or 0
            model_stats[log.model]["prompt_tokens"] += log.prompt_tokens or 0
            model_stats[log.model]["completion_tokens"] += log.completion_tokens or 0

        return model_stats


usage_service = UsageService()
