from fastapi import Depends,HTTPException,Response,APIRouter
from sqlalchemy.orm import Session
from app.schemas.schema import Login,user_register
from app.services.llm_service import get_user_by_email,hash_password
from app.models.rfp_models import User
from app.db.database import get_db
from app.api.routes.utils import create_access_token
from app.services.llm_service import verify_password


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

# @router.post("/login")
# def login(request: Login, db: Session = Depends(get_db)):
#     user = get_user_by_email(db, request.email)
    
#     if not user or not verify_password(request.password, user.password):
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     token_data = {"sub": str(user.id), "role": user.role}
#     access_token = create_access_token(data=token_data)

#     return {
#         "access_token": access_token,
#         "user_id": user.id,
#         "role": user.role,
#     }



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
        "role": user.role
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logout successful"}
