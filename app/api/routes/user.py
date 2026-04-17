from fastapi import APIRouter,Depends, Form
from sqlalchemy.orm import Session
from app.models.rfp_models import User
from app.db.database import get_db
from app.api.routes.utils import get_current_user
from app.schemas.schema import UpdateAnswerRequest
from app.services.user_services.user_service import UserService
from fastapi import HTTPException

router = APIRouter()

@router.get("/assigned-questions")
def get_assigned_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.get_assigned_questions(current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-answers/{question_id}")
def generate_answers(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: str = Form(...)
):
    try:
        service = UserService(db)
        return service.generate_answer(current_user, question_id, provider)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/answers/{question_id}/versions")
def get_answer_versions(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.get_answer_versions(current_user, question_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch('/update-answer/{question_id}')
def update_answer_endpoint(
    question_id: int,
    request: UpdateAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.update_answer(current_user, question_id, request.answer)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch('/submit')
def submit(
    question_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.submit_answer(current_user, question_id, status)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get_user_status')
def check(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    try:
        service = UserService(db)
        return service.check_user_status(current_user)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/filter-questions-by-user/{status}')
def filter_questions_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.filter_by_status(current_user, status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-question")
def analyze_single(
    rfp_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.analyze_question(rfp_id, question_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))