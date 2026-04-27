from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.rfp_models import RFPQuestion, Reviewer, User, ReviewerAnswerVersion, RFPDocument
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import selectinload

class UserRepository:
    
    @staticmethod

    async def get_user_assignments(db: AsyncSession, user_id: int):
        result = await db.execute(
            select(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .options(selectinload(RFPQuestion.rfp))  # ✅ important
            .filter(Reviewer.user_id == user_id)
            .order_by(RFPQuestion.id.asc())
        )
        return result.all()

    @staticmethod
    async def get_latest_answer_version(db: AsyncSession, user_id: int, question_id: int) -> Optional[ReviewerAnswerVersion]:
        result = await db.execute(
            select(ReviewerAnswerVersion)
            .filter_by(user_id=user_id, ques_id=question_id)
            .order_by(ReviewerAnswerVersion.generated_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def get_question_assignment(db: AsyncSession, user_id: int, question_id: int) -> Optional[Tuple[RFPQuestion, Reviewer]]:
        result = await db.execute(
            select(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .filter(
                Reviewer.user_id == user_id,
                Reviewer.ques_id == question_id
            )
        )
        return result.first()

    @staticmethod
    async def get_rfp_document(db: AsyncSession, rfp_id: int) -> Optional[RFPDocument]:
        result = await db.execute(
            select(RFPDocument).filter(RFPDocument.id == rfp_id)
        )
        return result.scalars().first()

    @staticmethod
    async def create_answer_version(db: AsyncSession, user_id: int, question_id: int, answer: str) -> ReviewerAnswerVersion:
        version = ReviewerAnswerVersion(
            user_id=user_id,
            ques_id=question_id,
            answer=answer
        )
        db.add(version)
        await db.commit()        
        await db.refresh(version)
        return version

    @staticmethod
    async def get_answer_versions(db: AsyncSession, user_id: int, question_id: int) -> List[ReviewerAnswerVersion]:
        result = await db.execute(
            select(ReviewerAnswerVersion)
            .filter_by(user_id=user_id, ques_id=question_id)
            .order_by(ReviewerAnswerVersion.generated_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_reviewer(db: AsyncSession, user_id: int, question_id: int) -> Optional[Reviewer]:
        result = await db.execute(
            select(Reviewer)
            .filter(
                Reviewer.user_id == user_id,
                Reviewer.ques_id == question_id
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_all_user_reviewers(db: AsyncSession, user_id: int) -> List[Reviewer]:
        result = await db.execute(
            select(Reviewer).filter(Reviewer.user_id == user_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_question_by_id(db: AsyncSession, question_id: int, rfp_id: int) -> Optional[RFPQuestion]:
        result = await db.execute(
            select(RFPQuestion).filter(
                RFPQuestion.id == question_id,
                RFPQuestion.rfp_id == rfp_id
            )
        )
        return result.scalars().first()