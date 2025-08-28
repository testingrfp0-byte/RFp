from fastapi import Depends,HTTPException,Response,APIRouter,status
from sqlalchemy.orm import Session
from app.schemas.schema import user_register
from app.services.llm_service import hash_password
from app.models.rfp_models import User
from app.db.database import get_db
from app.api.routes.utils import create_access_token
from app.services.llm_service import verify_password
from app.schemas.schema import ForgotPasswordRequest,ResetPasswordRequest,ChangePasswordRequest,VerifyOtpRequest,LoginRequest
from app.api.routes.utils import BackgroundTasks,generate_otp,send_email
from datetime import datetime, timedelta
from app.api.routes.utils import get_current_user
import secrets
from datetime import datetime, timedelta

SESSION_COOKIE = "session_user"
router = APIRouter()

@router.post("/register")
def register(request: user_register, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user and existing_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    existing_username = db.query(User).filter(User.username == request.username.strip()).first()
    if existing_username and (not existing_user or existing_user.id != existing_username.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    otp = generate_otp()
    expiry_time = datetime.utcnow() + timedelta(minutes=2)

    if existing_user:
        existing_user.username = request.username.strip()
        existing_user.password = hash_password(request.password)
        existing_user.role = request.role
        existing_user.reset_otp = otp
        existing_user.otp_expiry = expiry_time
        existing_user.is_verified = False
        user = existing_user
    else:
        user = User(
            username=request.username.strip(),
            password=hash_password(request.password),
            email=request.email.strip().lower(),
            role=request.role,
            reset_otp=otp,
            otp_expiry=expiry_time,
            is_verified=False
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Email Verification OTP",
        body=f"Your OTP is {otp}. It will expire in 2 minutes."
    )

    return {"message": "User registered successfully. Please verify OTP sent to your email."}

@router.post("/verify_otp")
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    provided_otp = str(request.otp).strip()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.otp_expiry < datetime.utcnow(): 
        user.reset_otp = None
        user.otp_expiry = None
        db.commit()
        raise HTTPException(status_code=400, detail="The OTP has expired. Please request a new OTP")

    stored_otp = str(user.reset_otp).strip()

    if not secrets.compare_digest(provided_otp, stored_otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.reset_otp = None
    user.otp_expiry = None

    if not user.is_verified:
        user.is_verified = True

    db.commit()

    return {"message": "OTP verified successfully."}


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.strip().lower()).first()

    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email with OTP before logging in."
        )

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

@router.post("/forgot_password")
def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=2)

    user.reset_otp = otp
    user.otp_expiry = expiry
    db.commit()

    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Password Reset OTP",
        body=f"Your OTP is {otp}. It is valid for 2 minutes."
    )

    return {"message": "OTP sent to your email"}


@router.post("/reset_password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
