from fastapi import Depends,HTTPException,Response,APIRouter,status
from sqlalchemy.orm import Session
from app.schemas.schema import Login,user_register
from app.services.llm_service import get_user_by_email,hash_password
from app.models.rfp_models import User
from app.db.database import get_db
from app.api.routes.utils import create_access_token
from app.services.llm_service import verify_password
from app.schemas.schema import ForgotPasswordRequest,ResetPasswordRequest,ChangePasswordRequest
from app.api.routes.utils import BackgroundTasks,generate_otp,send_email
from datetime import datetime, timedelta
from app.api.routes.utils import get_current_user


SESSION_COOKIE = "session_user"
router = APIRouter()

@router.post("/register")
def register(
    request:user_register,
    db: Session = Depends(get_db)):
    if get_user_by_email(db, request.email):
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=request.username, password=hash_password(request.password),email=request.email,role=request.role)
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}


@router.post("/login")
def login(request: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {
        "sub": str(user.id),
        "role": user.role  
    }
    access_token = create_access_token(data=token_data)

    return {
        "access_token": access_token,
        "user_id": user.id,
        "role": user.role,
        "username": user.username,
        "email": user.email,
        "image_url": f"uploads/{user.image}" if user.image else None
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logout successful"}

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    user.reset_otp = otp
    user.otp_expiry = expiry
    db.commit()

    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Password Reset OTP",
        body=f"Your OTP is {otp}. It is valid for 5 minutes."
    )

    return {"message": "OTP sent to your email"}

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or user.reset_otp != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if datetime.utcnow() > user.otp_expiry:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    user.password = hash_password(request.new_password)
    user.reset_otp = None
    user.otp_expiry = None
    db.commit()

    return {"message": "Password reset successful"}


@router.put("/change-password")
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )
    
    if not verify_password(request.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect"
        )

    if verify_password(request.new_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as old password"
        )

    current_user.password = hash_password(request.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {"message": "Password changed successfully"}
