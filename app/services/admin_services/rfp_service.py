import os
import uuid
import hashlib
import asyncio
from sqlalchemy import func
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.models.rfp_models import RFPDocument, RFPQuestion, CompanySummary,GeneratedRFPDocument
from app.services.llm_services.llm_service import (
    extract_text_from_pdf,
    extract_company_background_from_rfp,
    extract_questions_with_llm,
    summarize_results_with_llm,
    generate_search_queries,
    search_with_serpapi,
    client,
    parse_rfp_summary,
    clean_extracted_text,
    delete_rfp_embeddings
)
from app.config import pc, index, UPLOAD_FOLDER

async def process_rfp_file(
    file: UploadFile,
    project_name: str,
    db: Session,
    current_user
):
    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty."
            )
        file_hash = hashlib.md5(file_bytes).hexdigest()
        existing_rfp = (
            db.query(RFPDocument)
            .filter(RFPDocument.file_hash == file_hash)
            .first()
        )
        if existing_rfp:
            raise HTTPException(
                status_code=208,
                detail={
                    "status": "duplicate",
                    "message": "This RFP already exists.",
                    "existing_rfp_id": existing_rfp.id
                }
            )
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_original_name = os.path.basename(file.filename) if file.filename else "uploaded.pdf"
        dummy_filename = f"rfp_{timestamp}.pdf"
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_path = os.path.join(UPLOAD_FOLDER, dummy_filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        rfp_text = await asyncio.to_thread(extract_text_from_pdf, file_bytes)

        if not rfp_text or not rfp_text.strip():
            return {"error": "PDF text is empty or not readable after extraction."}

        rfp_text = clean_extracted_text(rfp_text)

        if not rfp_text.strip():
            return {"error": "PDF text became empty after cleaning (likely non-text document)."}

        if not rfp_text or not rfp_text.strip():
            raise HTTPException(status_code=422, detail="PDF has no readable text")
        
        if not rfp_text.strip():
            raise HTTPException(status_code=422, detail="PDF became empty after cleaning")

        new_rfp = RFPDocument(
            filename=safe_original_name,
            file_path=file_path,
            file_hash=file_hash,
            extracted_text=rfp_text,
            admin_id=current_user.id,
            category="history",
            project_name=project_name
        )
        db.add(new_rfp)
        db.commit()
        db.refresh(new_rfp)

        search_queries = generate_search_queries(rfp_text)
        questions_grouped = extract_questions_with_llm(rfp_text)
        company_rfp_text = extract_company_background_from_rfp(rfp_text)

        all_snippets = []
        for query in search_queries:
            try:
                results = search_with_serpapi(query)
                for item in results:
                    snippet = item.get("snippet")
                    if snippet:
                        all_snippets.append(snippet)
            except Exception as search_err:
                print(f"[SERP Error] Query '{query}': {search_err}")

        raw_summary = summarize_results_with_llm(
            all_snippets,
            rfp_company_text=company_rfp_text
        )
        structured_summary = parse_rfp_summary(raw_summary)

        new_summary = CompanySummary(
            rfp_id=new_rfp.id,
            summary_text=raw_summary,
            admin_id=current_user.id
        )
        db.add(new_summary)

        for group_number, data in questions_grouped.items():
            section_name = data.get("section", f"Section {group_number}")
            for q in data.get("questions", []):
                if not q:
                    continue
                db.add(RFPQuestion(
                    rfp_id=new_rfp.id,
                    question_text=q,
                    section=section_name,
                    admin_id=current_user.id
                ))

        db.commit()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        chunks = splitter.split_text(rfp_text)

        for i, chunk in enumerate(chunks):
            try:
                embedding_response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=chunk
                )
                embedding_vector = embedding_response.data[0].embedding

                index.upsert([
                    {
                        "id": str(uuid.uuid4()),
                        "values": embedding_vector,
                        "metadata": {
                            "file_id": str(new_rfp.id),
                            "chunk_index": i,
                            "text": chunk
                        }
                    }
                ])
            except Exception as embed_err:
                print(f"[Embedding Error] Chunk {i}: {embed_err}")

        return {
            "status": "new",
            "rfp_id": new_rfp.id,
            "saved_file": file_path,
            "category": new_rfp.category,
            "project_name": project_name,
            "summary": structured_summary,
            "total_questions": questions_grouped,
            "embedded_chunks": len(chunks)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def fetch_file_details(db: Session):
    try:
        documents = (
            db.query(RFPDocument)
            .filter(RFPDocument.is_deleted == False)
            .filter(RFPDocument.category.isnot(None))
            .filter(func.trim(RFPDocument.category) != '')
            .all()
        )
        return documents
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch documents"
        )

def delete_rfp_document_service(rfp_id: int, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can delete docs."
            )

        rfp = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
        if not rfp:
            raise HTTPException(
                status_code=404,
                detail="RFP document not found."
            )

        rfp.is_deleted = True
        rfp.deleted_at = datetime.utcnow()
        db.commit()

        return {
            "message": "RFP moved to trash. Work-in-progress is safely retained."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move RFP to trash: {str(e)}"
        )

def view_rfp_document_service(rfp_id: int, db: Session):
    try:
        import mimetypes
        rfp_doc = db.query(RFPDocument).filter(RFPDocument.id == rfp_id).first()
        if not rfp_doc:
            raise HTTPException(status_code=404, detail="RFP document not found")

        if not rfp_doc.file_path or not os.path.exists(rfp_doc.file_path):
            raise HTTPException(status_code=404, detail="File not found on server")

        media_type, _ = mimetypes.guess_type(rfp_doc.file_path)
        if not media_type:
            media_type = "application/octet-stream"

        return FileResponse(
            path=rfp_doc.file_path,
            filename=rfp_doc.filename,
            media_type=media_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def restore_rfp_doc(rfp_id: int, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can restore docs."
            )

        rfp = (
            db.query(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
            .first()
        )

        if rfp:
            rfp.is_deleted = False
            rfp.deleted_at = None
            db.commit()
            return {"message": "RFP restored successfully."}

        gen_doc = (
            db.query(GeneratedRFPDocument)
            .filter(
                GeneratedRFPDocument.id == rfp_id,
                GeneratedRFPDocument.is_deleted == True
            )
            .first()
        )

        if gen_doc:
            gen_doc.is_deleted = False
            gen_doc.deleted_at = None
            db.commit()
            return {"message": "Generated document restored successfully."}



        # rfp.is_deleted = False
        # rfp.deleted_at = None
        # db.commit()

        return {"message": "RFP restored successfully."}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore RFP document: {str(e)}"
        )

def permanent_delete_rfp(rfp_id: int, db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can permanently delete docs."
            )

        rfp = (
            db.query(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
            .first()
        )

        if rfp:
            if rfp.file_path and os.path.exists(rfp.file_path):
                os.remove(rfp.file_path)

            delete_rfp_embeddings(rfp_id)

            db.delete(rfp)
            db.commit()

            return {"message": "RFP permanently deleted."}
        
        gen_doc = (
            db.query(GeneratedRFPDocument)
            .filter(
                GeneratedRFPDocument.id == rfp_id,
                GeneratedRFPDocument.is_deleted == True
            )
            .first()
        )

        if gen_doc:
            if gen_doc.file_path and os.path.exists(gen_doc.file_path):
                os.remove(gen_doc.file_path)

            db.delete(gen_doc)
            db.commit()

            return {"message": "Generated document permanently deleted."}
        
        raise HTTPException(
            status_code=404,
            detail="Document not found in Trash."
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete RFP document: {str(e)}"
        )

def get_trash_documents(db: Session, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=401,
                detail="Only admins can view Trash."
            )

        deleted_docs = (
            db.query(RFPDocument)
            .filter(RFPDocument.is_deleted == True).filter()
            .order_by(RFPDocument.deleted_at.desc())
            .all()
        )

        rfp_list = [
            {
                "type": "rfp",
                "id": doc.id,
                "filename": doc.filename,
                "project_name": doc.project_name,
                "category": doc.category,
                "uploaded_at": doc.uploaded_at,
                "deleted_at": doc.deleted_at,
                "days_left": (
                    7 - (datetime.utcnow() - doc.deleted_at).days
                    if doc.deleted_at else None
                )
            }
            for doc in deleted_docs
        ]

        deleted_generated_docs = (
            db.query(GeneratedRFPDocument)
            .filter(GeneratedRFPDocument.is_deleted == True)
            .order_by(GeneratedRFPDocument.deleted_at.desc())
            .all()
        )

        generated_docs_list = [
            {
                "type": "generated_doc",
                "id": doc.id,
                "rfp_id": doc.rfp_id,
                "file_name": doc.file_name,
                "version": doc.version,
                "generated_at": doc.generated_at,
                "deleted_at": doc.deleted_at,
                "days_left": (
                    7 - (datetime.utcnow() - doc.deleted_at).days
                    if doc.deleted_at else None
                )
            }
            for doc in deleted_generated_docs
        ]
        return rfp_list + generated_docs_list

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch trash list: {str(e)}"
        )
    