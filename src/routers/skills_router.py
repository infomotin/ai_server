from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import SkillCreate, SkillResponse, SkillUpdate
from src.services.skill_service import skill_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(
    skill_data: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    existing = skill_service.get_skill_by_name(db, skill_data.name, current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Skill with this name already exists")

    skill = skill_service.create_skill(db, current_user.id, skill_data)
    return SkillResponse.model_validate(skill)


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    skills = skill_service.get_user_skills(db, current_user.id, active_only)
    return [SkillResponse.model_validate(s) for s in skills]


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    skill = skill_service.get_skill(db, skill_id, current_user.id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse.model_validate(skill)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    update_data: SkillUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    skill = skill_service.get_skill(db, skill_id, current_user.id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    updated = skill_service.update_skill(db, skill, update_data)
    return SkillResponse.model_validate(updated)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = skill_service.delete_skill(db, skill_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    return None
