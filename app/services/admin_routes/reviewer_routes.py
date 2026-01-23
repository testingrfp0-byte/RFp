from app.db.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, APIRouter, status
from app.schemas.schema import (
    AssignReviewer, ReviewerOut, reviwerdelete, ReassignReviewerRequest)
from app.models.rfp_models import User
from app.api.routes.utils import get_current_user
from app.utils.admin_function import (
    assign_multiple_review, get_reviewers_by_file_service,
    remove_user_service, delete_reviewer_service,
    reassign_reviewer_service)

router = APIRouter()

@router.post("/assign-reviewer")
def assign_multiple_reviewers(
    request: AssignReviewer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return assign_multiple_review(request, db, current_user)

@router.get("/assigned-reviewers/{file_id}", response_model=list[ReviewerOut])
def get_reviewers_by_file(file_id: int, db: Session = Depends(get_db)):
    return get_reviewers_by_file_service(file_id, db)

@router.delete("/reviewer-remove")
async def remove_user(
    ques_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await remove_user_service(ques_id, user_id, db, current_user)

@router.delete("/delete-reviewer_user")
async def delete_reviewer(
    request: reviwerdelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can remove reviewers."
        )

    if request.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot be deleted"
        )

    return await delete_reviewer_service(request, db)

@router.post("/reassign")
async def reassign_reviewer(
    request: ReassignReviewerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only admins can reassign reviewers."
        )

    try:
        return await reassign_reviewer_service(request, db, current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))