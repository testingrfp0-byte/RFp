from fastapi import Depends, HTTPException, APIRouter
from app.db.database import get_db
from app.schemas.schema import AdminEditRequest, ChatInputRequest
from app.models.rfp_models import User
from app.api.routes.utils import get_current_user
from app.services.admin_services import (admin_filter_questions_by_status_service,analyze_overall_score_service,edit_question_by_admin_service,regenerate_answer_with_chat_service)
from sqlalchemy.ext.asyncio import AsyncSession
router = APIRouter()

@router.get("/admin/filter-questions-by-user/{status}")
async def admin_filter_questions_by_status(
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await admin_filter_questions_by_status_service(status, db, current_user)

@router.post("/admin/analyze-answers")
async def analyze_overall_score_only_if_complete(
    rfp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint.")
    
    return await analyze_overall_score_service(rfp_id, db)

@router.patch("/admin/edit-answer")
async def edit_question_by_admin(
    request: AdminEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can edit submitted questions."
        )

    try:
        return await edit_question_by_admin_service(request, db)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/questions/chat_input")
async def regenerate_answer_with_chat(
    request: ChatInputRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await regenerate_answer_with_chat_service(request, db)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
