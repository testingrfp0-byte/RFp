"""
Main entry point for user-related operations
This file stays OUTSIDE the user folder and imports everything from inside
Location: app/services/user_function.py (NOT in app/services/user/)
"""
from sqlalchemy.orm import Session
from app.models.rfp_models import User
from typing import Dict, Any, List
from fastapi import HTTPException
from app.services.user_services.user_service import UserService
from app.services.user_services.user_repository import UserRepository
from app.services.user_services.user_validator import UserValidator
from app.services.user_services.user_business_logic import UserBusinessLogic

def assigned_questions(db: Session, current_user: User) -> List[Dict[str, Any]]:
    """
    Get all assigned questions for the current user
    
    Args:
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        List of assigned questions with their details
    """
    try:
        service = UserService(db)
        return service.get_assigned_questions(current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def generate_answers_service(db: Session, current_user: User, question_id: int) -> Dict[str, Any]:
    """
    Generate AI-powered answer for a specific question
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        question_id: ID of the question to generate answer for
    
    Returns:
        Generated answer with metadata and sources
    """
    try:
        service = UserService(db)
        return service.generate_answer(current_user, question_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def answer_versions(db: Session, current_user: User, question_id: int) -> Dict[str, Any]:
    """
    Get all answer versions for a specific question
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        question_id: ID of the question
    
    Returns:
        All versions of answers for the question with timestamps
    """
    try:
        service = UserService(db)
        return service.get_answer_versions(current_user, question_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def update_answer_service(db: Session, current_user: User, question_id: int, new_answer: str) -> Dict[str, Any]:
    """
    Update the answer for a specific question
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        question_id: ID of the question
        new_answer: New answer text
    
    Returns:
        Updated answer details with confirmation message
    """
    try:
        service = UserService(db)
        return service.update_answer(current_user, question_id, new_answer)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def submit_service(db: Session, current_user: User, question_id: int, status: str) -> Dict[str, Any]:
    """
    Submit answer for a specific question
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        question_id: ID of the question
        status: Submission status ('submitted' or 'not submitted')
    
    Returns:
        Submission confirmation details
    """
    try:
        service = UserService(db)
        return service.submit_answer(current_user, question_id, status)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def chech_service(db: Session, current_user: User) -> Dict[str, Any]:
    """
    Check status of all user assignments
    
    Args:
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        Status of all user assignments with submission details
    """
    try:
        service = UserService(db)
        return service.check_user_status(current_user)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def filter_service(db: Session, current_user: User, status: str) -> Dict[str, Any]:
    """
    Filter user's questions by submission status
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        status: Filter status ('submitted', 'not submitted', or 'process')
    
    Returns:
        Filtered questions matching the status
    """
    try:
        service = UserService(db)
        return service.filter_by_status(current_user, status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def analyze_single_question(rfp_id: int, question_id: int, db: Session, current_user: User) -> Dict[str, Any]:
    """
    Analyze a single question and calculate its quality score
    
    Args:
        rfp_id: ID of the RFP document
        question_id: ID of the question
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        Analysis results including quality score
    """
    try:
        service = UserService(db)
        return service.analyze_question(rfp_id, question_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))