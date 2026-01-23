from sqlalchemy.orm import Session
from app.models.rfp_models import User,KeystoneFile
from app.services.llm_services.llm_service import (
    get_similar_context, 
    generate_answer_with_context,
    analyze_answer_score_only,
)
from app.api.routes.utils import clean_answer
from datetime import datetime
from typing import List, Dict, Any

from .user_repository import UserRepository
from .user_validator import UserValidator
from fastapi import HTTPException

class UserBusinessLogic:
    """Business logic for user operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository()
        self.validator = UserValidator()
    
    def build_assigned_question_response(self, question, reviewer) -> Dict[str, Any]:
        """Build response for assigned question"""
        latest_answer = self.repository.get_latest_answer_version(
            self.db, 
            reviewer.user_id, 
            reviewer.ques_id
        )
        
        return {
            "user_id": reviewer.user_id, 
            "rfp_id": question.rfp_id,
            "filename": question.rfp.filename,
            "project_name": question.rfp.project_name,
            "question_id": question.id,
            "question_text": question.question_text,
            "is_deleted": question.rfp.is_deleted,
            "section": question.section,
            "status": reviewer.status,
            "assigned_at": question.assigned_at,
            "submit_status": reviewer.submit_status,
            "is_submitted": reviewer.submit_status == "submitted" or reviewer.submitted_at is not None,
            "answer_id": latest_answer.id if latest_answer else None,
            "answer": latest_answer.answer if latest_answer else None
        }
    
    def generate_enhanced_context(
        self,
        question_text: str,
        rfp_id: int,
        admin_id: int
    ) -> tuple:
        """
        Generate enhanced context using:
        1. Keystone XLS (PRIMARY source)
        2. RFP semantic context (SECONDARY source)
        """
        rfp_context, sources = get_similar_context(
            question_text,
            rfp_id
        )

        keystone = self.db.query(KeystoneFile).filter(
            KeystoneFile.admin_id == admin_id,
            KeystoneFile.is_active == True
        ).first()

        if not keystone:
            raise HTTPException(
                status_code=400,
                detail="Keystone Data not uploaded. Please upload Keystone XLS."
            )

        enhanced_context = f"""
    KEYSTONE DATA (PRIMARY SOURCE – MUST FOLLOW):
    {keystone.extracted_text}

    ----------------------------------------

    RFP CONTEXT (REFERENCE):
    {rfp_context}
    """

        return enhanced_context, ["keystone", "rfp"]

    def generate_answer_for_question(self, question_text: str, enhanced_context: str, short_name: str) -> str:
        """Generate and clean answer"""
        answer = generate_answer_with_context(question_text, enhanced_context, short_name)
        return clean_answer(answer)
    
    def update_reviewer_answer(self, reviewer, answer: str):
        """Update reviewer answer"""
        reviewer.ans = answer
    
    def create_and_save_answer_version(self, user_id: int, question_id: int, answer: str):
        """Create and save answer version"""
        version = self.repository.create_answer_version(self.db, user_id, question_id, answer)
        self.db.commit()
        return version
    
    def update_submission_status(self, reviewer, status: str):
        """Update submission status based on current state"""
        if reviewer.submit_status == "process":
            reviewer.submit_status = status
        elif reviewer.submit_status is None:
            self.validator.validate_submit_status_exists(reviewer)
        else:
            reviewer.submit_status = status
        
        reviewer.submitted_at = datetime.utcnow()
    
    def build_user_status_data(self, reviewers: List) -> List[Dict[str, Any]]:
        """Build user status data from reviewers"""
        data = []
        for reviewer in reviewers:
            if reviewer.submit_status is None:
                continue
            
            data.append({
                "username": reviewer.user.username,
                "question": reviewer.question,
                "answer": reviewer.ans,
                "status": reviewer.submit_status,
                "submitted_at": reviewer.submitted_at
            })
        
        return data
    
    def filter_questions_by_status(self, reviewers: List, target_status: str) -> List[Dict[str, Any]]:
        """Filter questions by status"""
        filtered_questions = []
        
        for reviewer in reviewers:
            current_status = reviewer.submit_status.strip().lower() if reviewer.submit_status else "not submitted"
            
            if current_status == target_status:
                filtered_questions.append({
                    "question_id": reviewer.ques_id,
                    "question": reviewer.question,
                    "rfp_id": reviewer.file_id
                })
        
        return filtered_questions
    
    def calculate_answer_score(self, question_text: str, answer_text: str) -> float:
        """Calculate score for an answer"""
        return analyze_answer_score_only(
            question_text=question_text,
            answer_text=answer_text
        )