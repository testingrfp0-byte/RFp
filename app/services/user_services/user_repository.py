"""
Repository layer for user-related database operations
Handles all direct database queries and data access
"""
from sqlalchemy.orm import Session
from app.models.rfp_models import RFPQuestion, Reviewer, User, ReviewerAnswerVersion, RFPDocument
from typing import Optional, List, Tuple
from datetime import datetime


class UserRepository:
    """Repository for user-related database operations"""
    
    @staticmethod
    def get_user_assignments(db: Session, user_id: int) -> List[Tuple[RFPQuestion, Reviewer]]:
        """Get all question assignments for a user"""
        return (
            db.query(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .filter(Reviewer.user_id == user_id)
            .all()
        )
    
    @staticmethod
    def get_latest_answer_version(db: Session, user_id: int, question_id: int) -> Optional[ReviewerAnswerVersion]:
        """Get the latest answer version for a specific question"""
        return (
            db.query(ReviewerAnswerVersion)
            .filter_by(user_id=user_id, ques_id=question_id)
            .order_by(ReviewerAnswerVersion.generated_at.desc())
            .first()
        )
    
    @staticmethod
    def get_question_assignment(db: Session, user_id: int, question_id: int) -> Optional[Tuple[RFPQuestion, Reviewer]]:
        """Get a specific question assignment for a user"""
        return (
            db.query(RFPQuestion, Reviewer)
            .join(Reviewer, RFPQuestion.id == Reviewer.ques_id)
            .filter(
                Reviewer.user_id == user_id,
                Reviewer.ques_id == question_id
            )
            .first()
        )
    
    @staticmethod
    def get_rfp_document(db: Session, rfp_id: int) -> Optional[RFPDocument]:
        """Get RFP document by ID"""
        return db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
    
    @staticmethod
    def create_answer_version(db: Session, user_id: int, question_id: int, answer: str) -> ReviewerAnswerVersion:
        """Create a new answer version"""
        version = ReviewerAnswerVersion(
            user_id=user_id,
            ques_id=question_id,
            answer=answer
        )
        db.add(version)
        return version
    
    @staticmethod
    def get_answer_versions(db: Session, user_id: int, question_id: int) -> List[ReviewerAnswerVersion]:
        """Get all answer versions for a question"""
        return (
            db.query(ReviewerAnswerVersion)
            .filter_by(user_id=user_id, ques_id=question_id)
            .order_by(ReviewerAnswerVersion.generated_at.desc())
            .all()
        )
    
    @staticmethod
    def get_reviewer(db: Session, user_id: int, question_id: int) -> Optional[Reviewer]:
        """Get reviewer by user and question ID"""
        return (
            db.query(Reviewer)
            .filter(
                Reviewer.user_id == user_id,
                Reviewer.ques_id == question_id
            )
            .first()
        )
    
    @staticmethod
    def get_all_user_reviewers(db: Session, user_id: int) -> List[Reviewer]:
        """Get all reviewer records for a user"""
        return db.query(Reviewer).filter(
            Reviewer.user_id == user_id
        ).all()
    
    @staticmethod
    def get_question_by_id(db: Session, question_id: int, rfp_id: int) -> Optional[RFPQuestion]:
        """Get question by ID and RFP ID"""
        return db.query(RFPQuestion).filter(
            RFPQuestion.id == question_id,
            RFPQuestion.rfp_id == rfp_id
        ).first()