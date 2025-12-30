"""
Service layer for user-related operations
Orchestrates business logic and repository calls
"""
from sqlalchemy.orm import Session
from app.models.rfp_models import User
from fastapi import HTTPException
from typing import List, Dict, Any

from app.services.user_services.user_repository import UserRepository
from app.services.user_services.user_validator import UserValidator
from app.services.user_services.user_business_logic import UserBusinessLogic
from app.services.llm_services.llm_service import get_short_name


class UserService:
    """Service for user operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository()
        self.validator = UserValidator()
        self.business_logic = UserBusinessLogic(db)
    
    def get_assigned_questions(self, current_user: User) -> List[Dict[str, Any]]:
        """Get all assigned questions for current user"""
        try:
            assignments = self.repository.get_user_assignments(self.db, current_user.id)
            
            results = []
            for question, reviewer in assignments:
                result = self.business_logic.build_assigned_question_response(question, reviewer)
                results.append(result)
            
            return results
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def generate_answer(self, current_user: User, question_id: int) -> Dict[str, Any]:
        """Generate answer for a specific question"""
        try:
            assignment = self.repository.get_question_assignment(
                self.db, 
                current_user.id, 
                question_id
            )
            
            self.validator.validate_assignment_exists(assignment)
            
            question, reviewer = assignment
            rfp_id = question.rfp_id
            question_text = question.question_text
            
            rfp_document = self.repository.get_rfp_document(self.db, rfp_id)
            self.validator.validate_rfp_document_exists(rfp_document)
            
            short_name = get_short_name(rfp_document.filename)
            enhanced_context, sources = self.business_logic.generate_enhanced_context(
                question_text, 
                rfp_id
            )
            
            answer = self.business_logic.generate_answer_for_question(
                question_text, 
                enhanced_context, 
                short_name
            )
            
            version = self.business_logic.create_and_save_answer_version(
                current_user.id, 
                question_id, 
                answer
            )
            
            self.business_logic.update_reviewer_answer(reviewer, answer)
            self.db.commit()
            
            return {
                "question_id": question.id,
                "question_text": question_text,
                "rfp_id": rfp_id,
                "answer": answer,
                "sources": sources
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_answer_versions(self, current_user: User, question_id: int) -> Dict[str, Any]:
        """Get all answer versions for a question"""
        try:
            versions = self.repository.get_answer_versions(
                self.db, 
                current_user.id, 
                question_id
            )
            
            return {
                "question_id": question_id,
                "versions": [
                    {
                        "id": version.id,
                        "answer": version.answer,
                        "generated_at": version.generated_at
                    }
                    for version in versions
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def update_answer(self, current_user: User, question_id: int, new_answer: str) -> Dict[str, Any]:
        """Update answer for a question"""
        try:
            reviewer = self.repository.get_reviewer(self.db, current_user.id, question_id)
            self.validator.validate_reviewer_exists(reviewer)
            
            if reviewer.ans:
                version = self.business_logic.create_and_save_answer_version(
                    current_user.id,
                    reviewer.ques_id,
                    new_answer
                )
                
                self.db.commit()
                self.db.refresh(version)
            
            self.business_logic.update_reviewer_answer(reviewer, new_answer)
            
            self.db.commit()
            self.db.refresh(reviewer)
            
            return {
                "message": "Answer has been updated successfully.",
                "question_id": reviewer.ques_id,
                "current_answer": reviewer.ans
            }
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    def submit_answer(self, current_user: User, question_id: int, status: str) -> Dict[str, Any]:
        """Submit answer for a question"""
        try:
            self.validator.validate_submission_status(status)
            
            reviewer = self.repository.get_reviewer(self.db, current_user.id, question_id)
            print(status)
            
            self.validator.validate_reviewer_exists(reviewer)
            
            self.business_logic.update_submission_status(reviewer, status)
            self.db.commit()
            
            return {
                "message": "Submission successful",
                "question_id": question_id,
                "answer": reviewer.ans,
                "submit_status": status
            }
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def check_user_status(self, current_user: User) -> Dict[str, Any]:
        """Check status of all user assignments"""
        try:
            reviewers = self.repository.get_all_user_reviewers(self.db, current_user.id)
            data = self.business_logic.build_user_status_data(reviewers)
            
            return {
                "message": "user Status fetched successfully",
                "data": data
            }
        
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def filter_by_status(self, current_user: User, status: str) -> Dict[str, Any]:
        """Filter user's questions by status"""
        try:
            status = self.validator.validate_filter_status(status)
            
            reviewers = self.repository.get_all_user_reviewers(self.db, current_user.id)
            
            if not reviewers:
                return {
                    "user_id": current_user.id,
                    "status": status,
                    "count": 0,
                    "questions": []
                }
            
            filtered_questions = self.business_logic.filter_questions_by_status(reviewers, status)
            
            return {
                "user_id": current_user.id,
                "status": status,
                "count": len(filtered_questions),
                "questions": filtered_questions
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    def analyze_question(self, rfp_id: int, question_id: int, current_user: User) -> Dict[str, Any]:
        """Analyze a single question and calculate score"""
        try:
            question = self.repository.get_question_by_id(self.db, question_id, rfp_id)
            self.validator.validate_question_exists(question)
            
            reviewer_answer = self.repository.get_reviewer(self.db, current_user.id, question_id)
            answer_text = reviewer_answer.ans if reviewer_answer and reviewer_answer.ans else ""
            
            score = self.business_logic.calculate_answer_score(
                question.question_text,
                answer_text
            )
            
            return {
                "rfp_id": rfp_id,
                "question_id": question_id,
                "question_text": question.question_text,
                "user_id": current_user.id,
                "answer": answer_text,
                "score": score
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))