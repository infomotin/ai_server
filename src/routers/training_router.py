"""
Training API Router
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from src.middleware.auth_middleware import get_current_user
from src.models.database import User
from src.services.training_service import training_service, JobStatus, STAGES


router = APIRouter(prefix="/training", tags=["Training"])


# ============== Schemas ==============
class StartTrainingRequest(BaseModel):
    name: str
    db_type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    tables: List[str] = []
    question_column: str = "auto"
    answer_column: str = "auto"
    text_columns: List[str] = []
    max_rows: int = 1000
    batch_size: int = 25
    model: str = "qwen2.5:0.5b"
    chunk_size: int = 500


class FeedbackRequest(BaseModel):
    question: str
    expected: str
    got: str
    is_correct: bool
    correction: str = ""


class TestQueryRequest(BaseModel):
    question: str


# ============== Endpoints ==============
@router.get("/stages")
async def get_stages(current_user: User = Depends(get_current_user)):
    return {"stages": STAGES}


@router.get("/jobs")
async def list_jobs(current_user: User = Depends(get_current_user)):
    jobs = training_service.list_jobs(user_id=current_user.id)
    return {
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "status": j.status,
                "current_stage": j.current_stage,
                "stage_idx": j.stage_idx,
                "progress": j.progress,
                "message": j.message,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "metrics": {
                    "rows_extracted": j.metrics.rows_extracted,
                    "rows_total": j.metrics.rows_total,
                    "qa_pairs_generated": j.metrics.qa_pairs_generated,
                    "chunks_created": j.metrics.chunks_created,
                    "loss": j.metrics.loss,
                    "accuracy": j.metrics.accuracy,
                    "throughput_rps": j.metrics.throughput_rps,
                    "elapsed_sec": j.metrics.elapsed_sec,
                    "eta_sec": j.metrics.eta_sec,
                    "cpu_usage": j.metrics.cpu_usage,
                    "memory_mb": j.metrics.memory_mb,
                    "loss_curve": j.metrics.loss_curve[-100:],
                    "accuracy_curve": j.metrics.accuracy_curve[-100:],
                },
                "qa_pairs_count": len(j.qa_pairs),
                "corrections_count": len(j.corrections),
                "test_results_count": len(j.test_results),
                "data_source_id": j.data_source_id,
                "knowledge_base_id": j.knowledge_base_id,
                "model_id": j.model_id,
                "error": j.error,
                "config": {
                    "db_type": j.config.get("db_type"),
                    "host": j.config.get("host"),
                    "database": j.config.get("database"),
                    "tables": j.config.get("tables"),
                },
            }
            for j in jobs
        ]
    }


@router.post("/jobs")
async def create_job(req: StartTrainingRequest, current_user: User = Depends(get_current_user)):
    job = training_service.create_job(
        user_id=current_user.id,
        name=req.name,
        config=req.model_dump(),
    )
    return {"id": job.id, "name": job.name, "status": job.status}


@router.post("/jobs/{job_id}/start")
async def start_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    if not training_service.start_training(job_id):
        raise HTTPException(400, "Job is already running or cannot be started")
    return {"success": True, "status": "started"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    if training_service.cancel_job(job_id):
        return {"success": True, "status": "cancelled"}
    return {"success": False, "message": "Job not running"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status,
        "current_stage": job.current_stage,
        "stage_idx": job.stage_idx,
        "progress": job.progress,
        "message": job.message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "metrics": {
            "rows_extracted": job.metrics.rows_extracted,
            "rows_total": job.metrics.rows_total,
            "qa_pairs_generated": job.metrics.qa_pairs_generated,
            "chunks_created": job.metrics.chunks_created,
            "loss": job.metrics.loss,
            "accuracy": job.metrics.accuracy,
            "throughput_rps": job.metrics.throughput_rps,
            "elapsed_sec": job.metrics.elapsed_sec,
            "eta_sec": job.metrics.eta_sec,
            "cpu_usage": job.metrics.cpu_usage,
            "memory_mb": job.metrics.memory_mb,
            "loss_curve": job.metrics.loss_curve[-100:],
            "accuracy_curve": job.metrics.accuracy_curve[-100:],
        },
        "logs": list(job.logs)[-200:],
        "qa_pairs": job.qa_pairs[:50],
        "corrections": job.corrections,
        "test_results": job.test_results,
        "data_source_id": job.data_source_id,
        "error": job.error,
        "config": {
            "db_type": job.config.get("db_type"),
            "host": job.config.get("host"),
            "database": job.config.get("database"),
            "tables": job.config.get("tables"),
            "question_column": job.config.get("question_column"),
            "answer_column": job.config.get("answer_column"),
            "text_columns": job.config.get("text_columns"),
            "max_rows": job.config.get("max_rows"),
            "model": job.config.get("model"),
        },
    }


@router.post("/jobs/{job_id}/test")
async def test_query(job_id: str, req: TestQueryRequest, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    return training_service.test_model(job_id, req.question)


@router.post("/jobs/{job_id}/feedback")
async def add_feedback(job_id: str, req: FeedbackRequest, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    return training_service.add_feedback(job_id, req.question, req.expected, req.got, req.is_correct, req.correction)


@router.post("/jobs/{job_id}/retrain")
async def retrain(job_id: str, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    if training_service.retrain(job_id):
        return {"success": True, "status": "retraining"}
    return {"success": False, "message": "Cannot retrain"}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = training_service.get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    training_service.delete_job(job_id)
    return {"success": True}
