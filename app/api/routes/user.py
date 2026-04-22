from fastapi import APIRouter,Depends, Form
from sqlalchemy.orm import Session
from app.models.rfp_models import User
from app.db.database import get_db
from app.api.routes.utils import get_current_user
from app.schemas.schema import UpdateAnswerRequest
from app.services.user_services.user_service import UserService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
router = APIRouter()

@router.get("/assigned-questions")
async def get_assigned_questions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return await service.get_assigned_questions(current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-answers/{question_id}")
async def generate_answers(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: str = "openai"
):
    try:
        service = UserService(db)
        return await service.generate_answer(current_user, question_id, provider)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/answers/{question_id}/versions")
async def get_answer_versions(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.get_answer_versions(current_user, question_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch('/update-answer/{question_id}')
async def update_answer_endpoint(
    question_id: int,
    request: UpdateAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return await service.update_answer(current_user, question_id, request.answer)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch('/submit')
async def submit(
    question_id: int,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return await service.submit_answer(current_user, question_id, status)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get_user_status')
async def check(db: AsyncSession = Depends(get_db),current_user: User = Depends(get_current_user)):
    try:
        service = UserService(db)
        return await service.check_user_status(current_user)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/filter-questions-by-user/{status}')
async def filter_questions_by_status(
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return await service.filter_by_status(current_user, status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-question")
async def analyze_single(
    rfp_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = UserService(db)
        return service.analyze_question(rfp_id, question_id, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))