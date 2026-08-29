from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.database import Skill
from src.models.schemas import SkillCreate, SkillUpdate


class SkillService:
    def create_skill(self, db: Session, user_id: str, skill_data: SkillCreate) -> Skill:
        skill = Skill(
            user_id=user_id,
            name=skill_data.name,
            description=skill_data.description,
            system_prompt=skill_data.system_prompt,
            parameters=skill_data.parameters
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    def get_skill(self, db: Session, skill_id: str, user_id: str) -> Optional[Skill]:
        return db.query(Skill).filter(
            Skill.id == skill_id,
            Skill.user_id == user_id
        ).first()

    def get_skill_by_name(self, db: Session, name: str, user_id: str) -> Optional[Skill]:
        return db.query(Skill).filter(
            Skill.name == name,
            Skill.user_id == user_id
        ).first()

    def get_user_skills(self, db: Session, user_id: str, active_only: bool = True) -> List[Skill]:
        query = db.query(Skill).filter(Skill.user_id == user_id)
        if active_only:
            query = query.filter(Skill.is_active == True)
        return query.order_by(Skill.created_at.desc()).all()

    def update_skill(self, db: Session, skill: Skill, update_data: SkillUpdate) -> Skill:
        if update_data.name is not None:
            skill.name = update_data.name
        if update_data.description is not None:
            skill.description = update_data.description
        if update_data.system_prompt is not None:
            skill.system_prompt = update_data.system_prompt
        if update_data.parameters is not None:
            skill.parameters = update_data.parameters
        if update_data.is_active is not None:
            skill.is_active = update_data.is_active

        skill.updated_at = datetime.now()
        db.commit()
        db.refresh(skill)
        return skill

    def delete_skill(self, db: Session, skill_id: str, user_id: str) -> bool:
        skill = self.get_skill(db, skill_id, user_id)
        if not skill:
            return False

        db.delete(skill)
        db.commit()
        return True

    def apply_skill_to_messages(self, skill: Skill, messages: List[dict]) -> List[dict]:
        if not skill or not skill.system_prompt:
            return messages

        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system_messages = [m for m in messages if m.get("role") != "system"]

        enhanced_system = skill.system_prompt
        if system_messages:
            enhanced_system = system_messages[0]["content"] + "\n\n" + skill.system_prompt

        result = [{"role": "system", "content": enhanced_system}] + non_system_messages
        return result


skill_service = SkillService()
