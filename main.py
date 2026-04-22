from fastapi import FastAPI, Request
from app.api.routes import admin, auth, user
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # ✅ changed to async scheduler
from datetime import datetime, timedelta
from app.db.database import get_db, engine, Base              # ✅ import engine & Base
from app.models import RFPDocument
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy import select                                  # ✅ for async queries

app = FastAPI(title="RFP Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith(("/api", "/auth", "/admin")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(CacheControlMiddleware)


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail}
    )


# ✅ Now fully async
async def auto_delete_expired_rfps():
    async for db in get_db():
        try:
            expiry_date = datetime.utcnow() - timedelta(days=7)

            result = await db.execute(
                select(RFPDocument).filter(
                    RFPDocument.is_deleted == True,
                    RFPDocument.deleted_at <= expiry_date
                )
            )
            expired_docs = result.scalars().all()

            for rfp in expired_docs:
                if rfp.file_path and os.path.exists(rfp.file_path):
                    os.remove(rfp.file_path)
                await db.delete(rfp)

            await db.commit()

        except Exception as e:
            print("Auto-delete error:", e)
            await db.rollback()


def start_scheduler():
    scheduler = AsyncIOScheduler()   # ✅ async-compatible scheduler
    scheduler.add_job(auto_delete_expired_rfps, 'interval', days=7)
    scheduler.start()


# ✅ Changed to async startup — creates tables + starts scheduler
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # ✅ replaces create_all(engine)
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

app.include_router(auth.router, tags=["Auth"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(user.router, tags=["User"])