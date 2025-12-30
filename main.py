from fastapi import FastAPI,Request
from app.api.routes import admin,auth,user
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models import RFPDocument
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException


app = FastAPI(title="RFP Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(
    request: Request,
    exc: FastAPIHTTPException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail
        }
    )

def auto_delete_expired_rfps():
    db_gen = get_db()
    db = next(db_gen)

    try:
        expiry_date = datetime.utcnow() - timedelta(days=7)

        expired_docs = db.query(RFPDocument).filter(
            RFPDocument.is_deleted == True,
            RFPDocument.deleted_at <= expiry_date
        ).all()

        for rfp in expired_docs:
            if rfp.file_path and os.path.exists(rfp.file_path):
                os.remove(rfp.file_path)
            db.delete(rfp)

        db.commit()

    except Exception as e:
        print("Auto-delete error:", e)

    finally:
        try:
            db_gen.close()
        except:
            pass

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_delete_expired_rfps, 'interval', days=7)
    scheduler.start()

@app.on_event("startup")
def startup_event():
    start_scheduler()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
GENERATED_FOLDER = os.path.join(BASE_DIR, "generated_docs")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

if not os.path.exists(GENERATED_FOLDER): 
    os.makedirs(GENERATED_FOLDER)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/download", StaticFiles(directory=GENERATED_FOLDER), name="download")

app.include_router(auth.router,tags=["Auth"])
app.include_router(admin.router,tags=["Admin"])
app.include_router(user.router,tags=["User"])
