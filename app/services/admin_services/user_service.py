import base64
from fastapi import  HTTPException,status
from sqlalchemy.orm import Session
from app.models.rfp_models import User, RFPQuestion, Reviewer, ReviewerAnswerVersion
from app.schemas.schema import UserOut, reviwerdelete
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, select, delete
from sqlalchemy.ext.asyncio import AsyncSession


async def get_all_users(db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can access User details."
            )

        users = await db.execute(select(User).order_by(desc((User.id))))
        users = users.scalars().all()

        return [
            UserOut(
                user_id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_verified=user.is_verified
            )
            for user in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_assigned_users(db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can access assigned user details."
            )
        assigned_user_ids = await db.execute(
            select(RFPQuestion.assigned_user_id)
            .filter(RFPQuestion.assigned_user_id != None)
            .distinct()
        )

        user_ids = [uid[0] for uid in assigned_user_ids]

        if not user_ids:
            return {"message": "No users assigned to any question", "users": []}

        users = await db.execute(select(User).filter(User.id.in_(user_ids)))
        users = users.scalars().all()

        return [
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_assigned": True
            }
            for user in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_user_by_id_service(user_id: int, db: AsyncSession):
    try:
        user = await db.execute(select(User).filter(User.id == user_id))
        user = user.scalar()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        image_base64 = None
        if user.image_bytea:
            image_base64 = base64.b64encode(user.image_bytea).decode("utf-8")

        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "image_name": user.image,
            "image_base64": image_base64
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

async def update_profile_service(
    db: AsyncSession,
    current_user,
    username: str | None = None,
    email: str | None = None,
    image_base64: str | None = None,
    image_name: str | None = None,
):
    user = await db.execute(select(User).filter(User.id == current_user.id))
    user = user.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if username and username != user.username:
        existing_user = await db.execute(
            select(User).filter(
                User.username == username,
                User.id != current_user.id
            )
        )
        existing_user = existing_user.scalar()
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="Username already exists. Please choose a different username."
            )
        user.username = username

    if email and email != user.email:
        existing_email = await db.execute(
            select(User).filter(
                User.email == email,
                User.id != current_user.id
            )
        )
        existing_email = existing_email.scalar()
        if existing_email:
            raise HTTPException(
                status_code=400, 
                detail="Email already exists. Please use a different email."
            )
        user.email = email

    if image_base64:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]

        try:
            user.image_bytea = base64.b64decode(image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image")

        user.image = image_name

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        if "username" in str(e.orig):
            raise HTTPException(status_code=400, detail="Username already exists")
        elif "email" in str(e.orig):
            raise HTTPException(status_code=400, detail="Email already exists")
        else:
            raise HTTPException(status_code=400, detail="Database constraint violation")
    
    return {
        "message": "Profile updated successfully",
        "username": user.username,
        "email": user.email,
        "image_name": user.image
    }

async def delete_reviewer_service(request: reviwerdelete, db: AsyncSession):
    user = await db.execute(select(User).filter(User.id == request.user_id))
    user = user.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.role != request.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User role mismatch. Expected '{request.role}', found '{user.role}'."
        )

    if user.role != request.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User role mismatch. Expected '{request.role}', found '{user.role}'."
        )


    await db.execute(
        delete(ReviewerAnswerVersion).where(
            ReviewerAnswerVersion.user_id == request.user_id
        )
    )

    await db.execute(
        delete(Reviewer).where(
            Reviewer.user_id == request.user_id
        )
    )


    await db.delete(user)
    await db.commit()


    return {
        "message": f"User (id={request.user_id}, role={user.role}) "
                   f"and all related reviewer data deleted successfully"
    }

