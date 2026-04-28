import os
import uuid
import hashlib
import asyncio
from sqlalchemy import func
from datetime import datetime
from app.core.timer import Timer
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.models.rfp_models import RFPDocument, RFPQuestion, CompanySummary,GeneratedRFPDocument
from app.services.llm_services.llm_service import (
    extract_text_from_pdf,
    extract_company_background_from_rfp,
    # extract_questions_with_llm,
    questions_grouped_function,
    summarize_results_with_llm,
    generate_search_queries,
    parse_rfp_summary,
    clean_extracted_text,
    delete_rfp_embeddings
)
# from app.core.prompts.question_grouped_function import questions_grouped_function
from app.config import pc, index, UPLOAD_FOLDER
from app.core.serpapi.serpapi import search_with_serpapi
from app.core.llm_client.openai import OpenAIEmbeddingClient
from pathlib import Path
from app.services.file_services.file_extracter import extract_text_from_file, SUPPORTED_EXTENSIONS
from app.services.llm_services.llm_service import classification_QaI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class RFPExtractionError(Exception):
    """Raised when file reading or text extraction fails unexpectedly."""
    pass

async def process_rfp_file(
    file: UploadFile,
    project_name: str,
    db: AsyncSession,
    current_user,
    provider: str = "openai",
    custom_message: str = None
):
    timer = Timer()

    try:
        # =========================
        # FILE READ
        # =========================
        file_bytes = await file.read()
        timer.log("file_read")

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # =========================
        # DUPLICATE CHECK
        # =========================
        file_hash = hashlib.md5(file_bytes).hexdigest()
        existing_rfp = await db.execute(
            select(RFPDocument).filter(RFPDocument.file_hash == file_hash)
        )
        existing_rfp = existing_rfp.scalar()

        if existing_rfp:
            raise HTTPException(
                status_code=208,
                detail={
                    "status": "duplicate",
                    "message": "This RFP already exists.",
                    "existing_rfp_id": existing_rfp.id
                }
            )
        timer.log("duplicate_check")

        # =========================
        # SAVE FILE
        # =========================
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_original_name = os.path.basename(file.filename) if file.filename else "uploaded.pdf"
        dummy_filename = f"rfp_{timestamp}.pdf"

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_path = os.path.join(UPLOAD_FOLDER, dummy_filename)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        timer.log("file_save")

        # =========================
        # TEXT EXTRACTION
        # =========================
        rfp_text = await asyncio.to_thread(extract_text_from_pdf, file_bytes)
        timer.log("pdf_extraction\n")
        # print("\nrfp_text lenth",len(rfp_text))
        # print("\nHere is the rfp text--------------------------",rfp_text)

        if not rfp_text.strip():
            raise HTTPException(status_code=422, detail="PDF has no readable text")

        # =========================
        # CLEAN TEXT
        # =========================
        rfp_text = clean_extracted_text(rfp_text)
        timer.log("text_cleaning")

        # =========================
        # SAVE TO DB
        # =========================
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
        await db.commit()
        await db.refresh(new_rfp)

        timer.log("db_insert")


        # search_queries = generate_search_queries(rfp_text, provider)
        # timer.log("search_query_generation")

        # questions_grouped = questions_grouped_function(
        #     rfp_text, custom_message, provider
        # )
        # timer.log("question_generation")
        # company_rfp_text = extract_company_background_from_rfp(
        #     rfp_text, provider
        # )
        # timer.log("company_extraction")

        search_queries, questions_grouped, company_rfp_text = await asyncio.gather(
            asyncio.to_thread(generate_search_queries, rfp_text, provider),
            asyncio.to_thread(questions_grouped_function, rfp_text,custom_message, provider),
            asyncio.to_thread(extract_company_background_from_rfp, rfp_text,provider)
        )

        # Temporary debug
        print(type(search_queries), type(questions_grouped), type(company_rfp_text))

        timer.log("llm_parallel_process")
        

        all_snippets = []
        for query in search_queries:
            try:
                results = search_with_serpapi(query)
                for item in results:
                    snippet = item.get("snippet")
                    if snippet:
                        all_snippets.append(snippet)
            except Exception as e:
                print(f"[SERP ERROR]: {e}")

        timer.log("serp_search")


        raw_summary = await summarize_results_with_llm(
            all_snippets,
            rfp_company_text=company_rfp_text,
            provider=provider
        )
        timer.log("final_summary")

        structured_summary = parse_rfp_summary(raw_summary)
        timer.log("summary_parsing")

        new_summary = CompanySummary(
            rfp_id=new_rfp.id,
            summary_text=raw_summary,
            admin_id=current_user.id
        )
        db.add(new_summary)

        for group_number, data in questions_grouped.items():
            section_name = data.get("section", f"Section {group_number}")
            for q in data.get("questions", []):
                if q:
                    db.add(RFPQuestion(
                        rfp_id=new_rfp.id,
                        question_text=q,
                        section=section_name,
                        admin_id=current_user.id
                    ))

        await db.commit()
        timer.log("questions_save")


        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        chunks = splitter.split_text(rfp_text)

        try:
            client = OpenAIEmbeddingClient()
            
            # Single API call for ALL chunks at once
            embedding_vectors = client.embed(chunks)

            # Build all vectors
            vectors = [
                {
                    "id": str(uuid.uuid4()),
                    "values": embedding_vector,
                    "metadata": {
                        "file_id": "rfp_" +str(new_rfp.id),
                        "chunk_index": i,
                        "text": chunk
                    }
                }
                for i, (chunk, embedding_vector) in enumerate(zip(chunks, embedding_vectors))
            ]

            # Batch upsert to Pinecone (100 at a time)
            BATCH_SIZE = 100
            for i in range(0, len(vectors), BATCH_SIZE):
                index.upsert(vectors[i:i + BATCH_SIZE], namespace=f"rfp_{new_rfp.id}")

        except Exception as e:
            print(f"[Embedding Error]: {e}")

        timer.log("embedding")

        # =========================
        # PRINT TIMINGS
        # =========================
        print("\n⏱️ TIMING BREAKDOWN:")
        for k, v in timer.steps.items():
            print(f"{k}: {v} sec")

        total_time = timer.total()
        print(f"TOTAL TIME: {total_time} sec\n")

        # =========================
        # FINAL RESPONSE
        # =========================
        return {
            "status": "new",
            "rfp_id": new_rfp.id,
            "summary": structured_summary,
            "total_questions": questions_grouped,
            "embedded_chunks": len(chunks),
            "timing": {
                "steps": timer.steps,
                "total_time": total_time
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_file_details(db: AsyncSession):
    try:
        documents = await db.execute(
            select(RFPDocument)
            .filter(RFPDocument.is_deleted == False)
            .filter(RFPDocument.category.isnot(None))
            .filter(func.trim(RFPDocument.category) != '')
        )

        return documents.scalars().all()
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch documents"
        )

async def delete_rfp_document_service(rfp_id: int, db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can delete docs."
            )

        rfp = await db.execute(select(RFPDocument).filter(RFPDocument.id == rfp_id))
        rfp = rfp.scalar()
        if not rfp:
            raise HTTPException(
                status_code=404,
                detail="RFP document not found."
            )

        rfp.is_deleted = True
        rfp.deleted_at = datetime.utcnow()
        await db.commit()

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

async def view_rfp_document_service(rfp_id: int, db: Session):
    try:
        import mimetypes
        result = await db.execute(
            select(RFPDocument).where(RFPDocument.id == rfp_id)
        )
        rfp_doc = result.scalars().first()
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

async def restore_rfp_doc(rfp_id: int, db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can restore docs."
            )

        # ✅ removed .first() from inside execute()
        rfp_result = await db.execute(
            select(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
        )
        rfp = rfp_result.scalars().first()  # ✅ scalars().first()

        if rfp:
            rfp.is_deleted = False
            rfp.deleted_at = None
            await db.commit()
            return {"message": "RFP restored successfully."}

        # ✅ removed .first() from inside execute()
        gen_doc_result = await db.execute(
            select(GeneratedRFPDocument)
            .filter(
                GeneratedRFPDocument.id == rfp_id,
                GeneratedRFPDocument.is_deleted == True
            )
        )
        gen_doc = gen_doc_result.scalars().first()  # ✅ scalars().first()

        if gen_doc:
            gen_doc.is_deleted = False
            gen_doc.deleted_at = None
            await db.commit()
            return {"message": "Generated document restored successfully."}

        raise HTTPException(  # ✅ added proper 404 instead of silent success
            status_code=404,
            detail="Document not found in Trash."
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore RFP document: {str(e)}"
        )

async def permanent_delete_rfp(rfp_id: int, db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only admins can permanently delete docs."
            )

        # ✅ removed .first() from inside execute()
        rfp_result = await db.execute(
            select(RFPDocument)
            .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
        )
        rfp = rfp_result.scalars().first()  # ✅ scalars().first()

        if rfp:
            if rfp.file_path and os.path.exists(rfp.file_path):
                os.remove(rfp.file_path)

            delete_rfp_embeddings(rfp_id)

            await db.delete(rfp)   # ✅ await db.delete()
            await db.commit()

            return {"message": "RFP permanently deleted."}

        # ✅ removed .first() from inside execute()
        gen_doc_result = await db.execute(
            select(GeneratedRFPDocument)
            .filter(
                GeneratedRFPDocument.id == rfp_id,
                GeneratedRFPDocument.is_deleted == True
            )
        )
        gen_doc = gen_doc_result.scalars().first()  # ✅ scalars().first()

        if gen_doc:
            if gen_doc.file_path and os.path.exists(gen_doc.file_path):
                os.remove(gen_doc.file_path)

            await db.delete(gen_doc)  # ✅ await db.delete()
            await db.commit()

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

async def get_trash_documents(db: AsyncSession, current_user):
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=401,
                detail="Only admins can view Trash."
            )

        deleted_docs = (
            await db.execute(
                select(RFPDocument)
                .filter(RFPDocument.is_deleted == True)
            )
        )
        deleted_docs = deleted_docs.scalars().all()

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
            await db.execute(
                select(GeneratedRFPDocument)
                .filter(GeneratedRFPDocument.is_deleted == True)
                .order_by(GeneratedRFPDocument.deleted_at.desc())
            )
        )
        deleted_generated_docs = deleted_generated_docs.scalars().all()

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


# def client_permanent_delete_rfp(rfp_id: int, db: Session, current_user):
#     try:
#         if current_user.role != "admin":
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Only admins can permanently delete docs."
#             )

#         rfp = (
#             db.query(RFPDocument)
#             .filter(RFPDocument.id == rfp_id, RFPDocument.is_deleted == True)
#             .first()
#         )

#         if rfp:
#             if rfp.file_path and os.path.exists(rfp.file_path):
#                 os.remove(rfp.file_path)

#             delete_rfp_embeddings(rfp_id)

#             db.delete(rfp)
#             db.commit()

#             return {"message": "RFP permanently deleted."}
        
#         gen_doc = (
#             db.query(GeneratedRFPDocument)
#             .filter(
#                 GeneratedRFPDocument.id == rfp_id,
#                 GeneratedRFPDocument.is_deleted == True
#             )
#             .first()
#         )

#         if gen_doc:
#             if gen_doc.file_path and os.path.exists(gen_doc.file_path):
#                 os.remove(gen_doc.file_path)

#             db.delete(gen_doc)
#             db.commit()

#             return {"message": "Generated document permanently deleted."}
        
#         raise HTTPException(
#             status_code=404,
#             detail="Document not found in Trash."
#         )

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to permanently delete RFP document: {str(e)}"
#         )

def structure_classification(data):
    structured = {"I": [], "Q": [], "B": []}

    for item in data.get("classification_results", []):
        cls = item.get("classification")

        simplified = {
            "item_number": item["item_number"],
            "text": item["item_text"]
        }

        structured[cls].append(simplified)

    return structured
