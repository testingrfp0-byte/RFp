import os
from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from app.db.database import Base, engine
from app.services.admin_routes.rfp_routes import router as rfp_router
from app.services.admin_routes.user_routes import router as user_router
from app.services.admin_routes.reviewer_routes import router as reviewer_router
from app.services.admin_routes.document_routes import router as document_router
from app.services.admin_routes.notification_routes import router as notification_router
from app.services.admin_routes.analysis_routes import router as analysis_router
from app.services.admin_routes.dynamic_form_routes import router as dynamic_form_router

router = APIRouter()
Base.metadata.create_all(engine)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

router.include_router(rfp_router, tags=["RFP Management"])
router.include_router(user_router, tags=["User Management"])
router.include_router(reviewer_router, tags=["Reviewer Management"])
router.include_router(document_router, tags=["Document Management"])
router.include_router(notification_router, tags=["Notifications"])
router.include_router(analysis_router, tags=["Analysis"])
router.include_router(dynamic_form_router, tags=["Dynamic Forms"])
