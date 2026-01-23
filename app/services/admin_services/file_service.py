import os
import shutil
import hashlib
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.config import UPLOAD_FOLDER, index
from app.models.rfp_models import RFPDocument
from app.services.llm_services.llm_service import (
    extract_text_from_file,
    generate_summary,
    get_embedding
)
from langchain.text_splitter import RecursiveCharacterTextSplitter

def upload_documents(files, project_name, category, current_user, db: Session):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    uploaded_docs = []

    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".pdf", ".docx", ".pptx", ".xlsx", ".xls"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file.filename}"
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        saved_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, saved_filename)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()

        new_doc = RFPDocument(
            filename=file.filename,
            file_path=file_path,
            category=category,
            project_name=project_name,
            admin_id=current_user.id,
            uploaded_at=datetime.utcnow(),
            file_hash=file_hash
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        text = extract_text_from_file(file_path)
        if not text:
            continue

        summary = generate_summary(text)
        summary_vector = get_embedding(summary)
        index.upsert(
            vectors=[(
                f"summary_{new_doc.id}",
                summary_vector,
                {
                    "document_id": str(new_doc.id),
                    "filename": new_doc.filename,
                    "category": new_doc.category,
                    "project_name": new_doc.project_name,
                    "type": "summary",
                    "text": summary
                }
            )],
            namespace="summaries"
        )

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(text)
        vectors = []
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            vectors.append((
                f"{new_doc.id}_{i}",
                vector,
                {
                    "document_id": str(new_doc.id),
                    "filename": new_doc.filename,
                    "category": new_doc.category,
                    "project_name": new_doc.project_name,
                    "type": "chunk",
                    "chunk_id": i,
                    "text": chunk
                }
            ))

        if vectors:
            index.upsert(vectors=vectors, namespace=f"rfp_{new_doc.id}")

        uploaded_docs.append({
            "document_id": new_doc.id,
            "filename": new_doc.filename,
            "category": new_doc.category,
            "project_name": new_doc.project_name
        })

    return uploaded_docs