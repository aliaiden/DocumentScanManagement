"""
Documents Router
Handles batch image uploads, streaming saved images from Azure Storage,
re-analyzing documents via Azure Content Understanding, and deletion.
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Person, Document, DocumentAnalysis
from backend.schemas import DocumentOut, DocumentAnalysisOut
from backend.services.storage_service import storage_service
from backend.services.content_understanding_service import content_understanding_service

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/batch/{person_id}", response_model=List[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_batch_documents(
    person_id: int,
    categories_json: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an additional batch of pictures of scanned documents for an existing person.
    Saves to Azure Storage, inserts records into Azure SQL Server,
    and runs Azure Content Understanding.
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    parsed_categories = []
    if categories_json:
        try:
            parsed_categories = json.loads(categories_json)
        except Exception:
            parsed_categories = []

    person_context = {
        "full_name": person.full_name,
        "person_type": person.person_type,
        "national_id": person.national_id,
        "date_of_birth": person.date_of_birth,
        "address": person.address
    }

    created_documents = []

    for idx, file in enumerate(files):
        if not file.filename:
            continue

        file_bytes = await file.read()
        if len(file_bytes) == 0:
            continue

        category = "Other"
        if idx < len(parsed_categories) and parsed_categories[idx]:
            category = parsed_categories[idx]

        # Upload to Azure Account Storage Service
        blob_name, storage_ref, container = storage_service.upload_file(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type or "image/jpeg",
            person_id=person.id
        )

        # Record in Azure SQL Server
        document = Document(
            person_id=person.id,
            project_id=person.project_id,
            original_filename=file.filename,
            content_type=file.content_type or "image/jpeg",
            file_size=len(file_bytes),
            doc_category=category,
            storage_reference=storage_ref,
            blob_name=blob_name,
            storage_container=container,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Analyze with Azure Content Understanding
        analysis_data = content_understanding_service.analyze_document(
            file_bytes=file_bytes,
            filename=file.filename,
            category=category,
            person_context=person_context,
            file_url=storage_ref if storage_ref.startswith("http") else None
        )

        doc_analysis = DocumentAnalysis(
            document_id=document.id,
            status=analysis_data.get("status", "completed"),
            has_signature=analysis_data.get("has_signature", False),
            has_stamp=analysis_data.get("has_stamp", False),
            is_handwritten=analysis_data.get("is_handwritten", False),
            handwritten_percentage=analysis_data.get("handwritten_percentage", 0.0),
            detected_type=analysis_data.get("detected_type"),
            confidence_score=analysis_data.get("confidence_score", 0.95),
            extracted_text=analysis_data.get("extracted_text"),
            analysis_raw=json.dumps(analysis_data.get("analysis_raw", {}))
        )
        doc_analysis.extracted_fields = analysis_data.get("extracted_fields", {})
        db.add(doc_analysis)
        db.commit()
        db.refresh(document)

        analysis_out = DocumentAnalysisOut(
            id=doc_analysis.id,
            document_id=doc_analysis.document_id,
            status=doc_analysis.status,
            has_signature=doc_analysis.has_signature,
            has_stamp=doc_analysis.has_stamp,
            is_handwritten=doc_analysis.is_handwritten,
            handwritten_percentage=doc_analysis.handwritten_percentage,
            detected_type=doc_analysis.detected_type,
            confidence_score=doc_analysis.confidence_score,
            extracted_text=doc_analysis.extracted_text,
            extracted_fields=doc_analysis.extracted_fields,
            analyzed_at=doc_analysis.analyzed_at
        )

        created_documents.append(
            DocumentOut(
                id=document.id,
                person_id=document.person_id,
                project_id=document.project_id,
                original_filename=document.original_filename,
                content_type=document.content_type,
                file_size=document.file_size,
                doc_category=document.doc_category,
                storage_reference=document.storage_reference,
                blob_name=document.blob_name,
                storage_container=document.storage_container,
                created_at=document.created_at,
                analysis=analysis_out
            )
        )

    return created_documents


@router.get("/{document_id}/file")
def fetch_document_file(document_id: int, db: Session = Depends(get_db)):
    """
    Fetches saved batch image from Azure Storage Service (or local fallback)
    and streams it back to the client.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        data, content_type = storage_service.get_file_bytes(document.blob_name)
        return Response(content=data, media_type=content_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document file not found in storage.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file from storage: {e}")


@router.get("/{document_id}/analysis", response_model=DocumentAnalysisOut)
def get_document_analysis(document_id: int, db: Session = Depends(get_db)):
    """Get the Azure Content Understanding analysis for a document"""
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return DocumentAnalysisOut(
        id=analysis.id,
        document_id=analysis.document_id,
        status=analysis.status,
        has_signature=analysis.has_signature,
        has_stamp=analysis.has_stamp,
        is_handwritten=analysis.is_handwritten,
        handwritten_percentage=analysis.handwritten_percentage,
        detected_type=analysis.detected_type,
        confidence_score=analysis.confidence_score,
        extracted_text=analysis.extracted_text,
        extracted_fields=analysis.extracted_fields,
        analyzed_at=analysis.analyzed_at
    )


@router.post("/{document_id}/reanalyze", response_model=DocumentAnalysisOut)
def reanalyze_document(document_id: int, db: Session = Depends(get_db)):
    """Re-run Azure Content Understanding on an existing document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        file_bytes, _ = storage_service.get_file_bytes(document.blob_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot fetch document from storage: {e}")

    person_context = {
        "full_name": document.person.full_name if document.person else "Unknown",
        "person_type": document.person.person_type if document.person else "Unknown",
        "national_id": document.person.national_id if document.person else "",
    }

    analysis_data = content_understanding_service.analyze_document(
        file_bytes=file_bytes,
        filename=document.original_filename,
        category=document.doc_category,
        person_context=person_context,
        file_url=document.storage_reference if document.storage_reference.startswith("http") else None
    )

    doc_analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document.id).first()
    if not doc_analysis:
        doc_analysis = DocumentAnalysis(document_id=document.id)
        db.add(doc_analysis)

    doc_analysis.status = analysis_data.get("status", "completed")
    doc_analysis.has_signature = analysis_data.get("has_signature", False)
    doc_analysis.has_stamp = analysis_data.get("has_stamp", False)
    doc_analysis.is_handwritten = analysis_data.get("is_handwritten", False)
    doc_analysis.handwritten_percentage = analysis_data.get("handwritten_percentage", 0.0)
    doc_analysis.detected_type = analysis_data.get("detected_type")
    doc_analysis.confidence_score = analysis_data.get("confidence_score", 0.95)
    doc_analysis.extracted_text = analysis_data.get("extracted_text")
    doc_analysis.extracted_fields = analysis_data.get("extracted_fields", {})
    doc_analysis.analysis_raw = json.dumps(analysis_data.get("analysis_raw", {}))

    db.commit()
    db.refresh(doc_analysis)

    return DocumentAnalysisOut(
        id=doc_analysis.id,
        document_id=doc_analysis.document_id,
        status=doc_analysis.status,
        has_signature=doc_analysis.has_signature,
        has_stamp=doc_analysis.has_stamp,
        is_handwritten=doc_analysis.is_handwritten,
        handwritten_percentage=doc_analysis.handwritten_percentage,
        detected_type=doc_analysis.detected_type,
        confidence_score=doc_analysis.confidence_score,
        extracted_text=doc_analysis.extracted_text,
        extracted_fields=doc_analysis.extracted_fields,
        analyzed_at=doc_analysis.analyzed_at
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document from Azure SQL Server and delete the blob from Azure Storage"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    storage_service.delete_file(document.blob_name)
    db.delete(document)
    db.commit()
    return None
