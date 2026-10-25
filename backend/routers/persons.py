"""
Persons Router
Handles adding persons via basic info form + batch pictures/scans of documents.
Uploads to Azure Storage, stores storage references in Azure SQL Server,
and runs Azure Content Understanding.
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Project, Person, Document, DocumentAnalysis
from backend.schemas import PersonOut, PersonUpdate
from backend.services.storage_service import storage_service
from backend.services.content_understanding_service import content_understanding_service

router = APIRouter(tags=["Persons"])


@router.get("/api/projects/{project_id}/persons", response_model=List[PersonOut])
def list_project_persons(project_id: int, db: Session = Depends(get_db)):
    """List all persons registered in a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    persons = db.query(Person).filter(Person.project_id == project_id).order_by(Person.created_at.desc()).all()
    results = []
    for p in persons:
        results.append(
            PersonOut(
                id=p.id,
                project_id=p.project_id,
                person_type=p.person_type,
                full_name=p.full_name,
                national_id=p.national_id,
                email=p.email,
                phone=p.phone,
                date_of_birth=p.date_of_birth,
                address=p.address,
                notes=p.notes,
                created_at=p.created_at,
                updated_at=p.updated_at,
                documents_count=len(p.documents),
                documents=[]
            )
        )
    return results


@router.post("/api/projects/{project_id}/persons", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person_with_batch_documents(
    project_id: int,
    full_name: str = Form(...),
    person_type: str = Form(...),
    national_id: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    date_of_birth: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    categories_json: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """
    Registers a person with basic info and takes a batch of pictures/scans of documents.
    Images are saved to Azure Storage Service; references & metadata stored in Azure SQL Server;
    Azure Content Understanding analyzes handwritten/print text, signatures, stamps, and fields.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required.")

    # Validate or default person_type
    allowed_types = project.person_types
    if person_type not in allowed_types and allowed_types:
        # Default to first allowed type if invalid
        person_type = allowed_types[0]

    # 1. Save Person to Azure SQL Server
    person = Person(
        project_id=project_id,
        person_type=person_type.strip(),
        full_name=full_name.strip(),
        national_id=national_id.strip() if national_id else None,
        email=email.strip() if email else None,
        phone=phone.strip() if phone else None,
        date_of_birth=date_of_birth.strip() if date_of_birth else None,
        address=address.strip() if address else None,
        notes=notes.strip() if notes else None,
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    # Parse categories mapping if provided
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

    # 2. Process batch of scanned pictures/documents
    for idx, file in enumerate(files):
        if not file.filename:
            continue

        file_bytes = await file.read()
        if len(file_bytes) == 0:
            continue

        category = "Other"
        if idx < len(parsed_categories) and parsed_categories[idx]:
            category = parsed_categories[idx]

        # Upload image to Azure Account Storage Service
        blob_name, storage_ref, container = storage_service.upload_file(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=file.content_type or "image/jpeg",
            person_id=person.id
        )

        # Store Document storage reference in Azure SQL Server
        document = Document(
            person_id=person.id,
            project_id=project.id,
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

        # 3. Analyze document with Azure Content Understanding
        analysis_data = content_understanding_service.analyze_document(
            file_bytes=file_bytes,
            filename=file.filename,
            category=category,
            person_context=person_context
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

    db.refresh(person)

    return get_person_dossier(person.id, db)


@router.get("/api/persons/{person_id}", response_model=PersonOut)
def get_person_dossier(person_id: int, db: Session = Depends(get_db)):
    """Fetch person dossier with all batch documents and Azure Content Understanding analysis"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    docs = []
    for d in person.documents:
        analysis_out = None
        if d.analysis:
            analysis_out = {
                "id": d.analysis.id,
                "document_id": d.analysis.document_id,
                "status": d.analysis.status,
                "has_signature": d.analysis.has_signature,
                "has_stamp": d.analysis.has_stamp,
                "is_handwritten": d.analysis.is_handwritten,
                "handwritten_percentage": d.analysis.handwritten_percentage,
                "detected_type": d.analysis.detected_type,
                "confidence_score": d.analysis.confidence_score,
                "extracted_text": d.analysis.extracted_text,
                "extracted_fields": d.analysis.extracted_fields,
                "analyzed_at": d.analysis.analyzed_at
            }
        docs.append({
            "id": d.id,
            "person_id": d.person_id,
            "project_id": d.project_id,
            "original_filename": d.original_filename,
            "content_type": d.content_type,
            "file_size": d.file_size,
            "doc_category": d.doc_category,
            "storage_reference": d.storage_reference,
            "blob_name": d.blob_name,
            "storage_container": d.storage_container,
            "created_at": d.created_at,
            "analysis": analysis_out
        })

    return PersonOut(
        id=person.id,
        project_id=person.project_id,
        person_type=person.person_type,
        full_name=person.full_name,
        national_id=person.national_id,
        email=person.email,
        phone=person.phone,
        date_of_birth=person.date_of_birth,
        address=person.address,
        notes=person.notes,
        created_at=person.created_at,
        updated_at=person.updated_at,
        documents_count=len(docs),
        documents=docs
    )


@router.put("/api/persons/{person_id}", response_model=PersonOut)
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)):
    """Update person's basic info"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    if payload.full_name is not None:
        if not payload.full_name.strip():
            raise HTTPException(status_code=400, detail="Full name cannot be empty.")
        person.full_name = payload.full_name.strip()

    if payload.person_type is not None:
        person.person_type = payload.person_type.strip()
    if payload.national_id is not None:
        person.national_id = payload.national_id.strip() if payload.national_id else None
    if payload.email is not None:
        person.email = payload.email.strip() if payload.email else None
    if payload.phone is not None:
        person.phone = payload.phone.strip() if payload.phone else None
    if payload.date_of_birth is not None:
        person.date_of_birth = payload.date_of_birth.strip() if payload.date_of_birth else None
    if payload.address is not None:
        person.address = payload.address.strip() if payload.address else None
    if payload.notes is not None:
        person.notes = payload.notes.strip() if payload.notes else None

    db.commit()
    return get_person_dossier(person_id, db)


@router.delete("/api/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete a person and all their scanned documents from Azure SQL and Azure Storage"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    for doc in person.documents:
        try:
            storage_service.delete_file(doc.blob_name)
        except Exception:
            pass

    db.delete(person)
    db.commit()
    return None
