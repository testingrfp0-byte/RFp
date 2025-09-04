from fastapi import HTTPException,APIRouter,Depends
from sqlalchemy.orm import Session
from app.models.rfp_models import User,Reviewer,RFPQuestion,ReviewerAnswerVersion
from datetime import datetime
from app.utils.dependencies import get_db
from app.api.routes.utils import get_current_user
from app.services.llm_service import get_similar_context,generate_answer_with_context
from app.utils.user_function import answer_versions,assigned_questions,generate_answers_service,update_answer_service,submit_service,chech_service,filter_service

from app.schemas.schema import UpdateAnswerRequest

router = APIRouter()

@router.get("/assigned-questions")
def get_assigned_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return assigned_questions(db, current_user)

@router.get("/generate-answers/{question_id}")
def generate_answers(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return generate_answers_service(db, current_user, question_id)

@router.get("/answers/{question_id}/versions")
def get_answer_versions(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return answer_versions(db, current_user, question_id)

@router.patch('/update-answer/{question_id}')
def update_answer_endpoint(
    question_id: int,
    request: UpdateAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return update_answer_service(db, current_user, question_id, request.answer)

@router.patch('/submit')
def submit(
    question_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return submit_service(db, current_user, question_id,status)

@router.get('/get_user_status')
def check(db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    return chech_service(db,current_user)

@router.get('/filter-questions-by-user/{status}')
def filter_questions_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return filter_service(db, current_user,status)