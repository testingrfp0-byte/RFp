from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status,Request
from app.config import oauth2_scheme,SECRET_KEY,ALGORITHM,ACCESS_TOKEN_EXPIRE_MINUTES,SENDER_EMAIL,SENDER_PASSWORD
from sqlalchemy.orm import Session
from app.models.rfp_models import User
from app.db.database import get_db
import random, string
import smtplib
from email.mime.text import MIMEText
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
import os
import re

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if not user_id or not role:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized user")
    user.role = role

    if user.role == "admin":
        user.all_admins = db.query(User).filter(User.role == "admin").all()
    else:
        user.all_admins = []

    return user

def generate_otp(length: int = 4):
    return ''.join(random.choices(string.digits, k=length))

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

def build_image_url(request: Request, image_value: str | None) -> str | None:
    """
    Returns an absolute URL for the image.
    Accepts values like:
      - "uploads/abc.jpg"
      - "abc.jpg"
      - already absolute "http://.../abc.jpg"
    """
    if not image_value:
        return None

    if image_value.startswith("http://") or image_value.startswith("https://"):
        return image_value

    filename = os.path.basename(image_value)

    base = str(request.base_url).rstrip("/")          
    return f"{base}/uploads/{filename}"           

def clean_answer(text: str) -> str:
    text = re.sub(r'[#*`]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()  
    return text

