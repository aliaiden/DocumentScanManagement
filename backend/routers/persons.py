"""
Persons & Batch Document Scan Router
Enables uploading a batch of scanned documents without manual person forms.
The Azure Content Understanding image analyzer automatically extracts the person details
(Name, ID, DOB, Role, Contact) from the document scans and records them in Azure SQL Server.
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

router = APIRouter(tags=["Persons & Document Scans"])


@router.get("/api/projects/{project_id}/persons", response_model=List[PersonOut], summary="List Persons in Project")
def list_project_persons(project_id: int, db: Session = Depends(get_db)):
    """List all persons auto-identified or registered in a project"""
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


@router.post(
    "/api/projects/{project_id}/scan",
    response_model=PersonOut,
    status_code=status.HTTP_201_CREATED,
    summary="Batch Upload Scans & Auto-Extract Person Details",
    description="Upload a batch of scanned documents / camera photos without manual person form input. Azure Content Understanding automatically extracts the person details (Name, ID, DOB, Contact, Role) from the document images and saves them in Azure SQL."
)
@router.post(
    "/api/projects/{project_id}/persons",
    response_model=PersonOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add Scanned Batch to Project",
    description="Streamlined batch scan endpoint: manual person form fields are removed; person details are extracted directly from the output of the image analyzer."
)
async def scan_and_auto_extract_person(
    project_id: int,
    files: List[UploadFile] = File(..., description="Batch pictures of scanned documents from mobile camera or computer"),
    categories_json: Optional[str] = Form(None, description="Optional JSON array of document categories"),
    person_type: Optional[str] = Form(None, description="Optional preferred person category/role from project"),
    person_id: Optional[int] = Form(None, description="Optional: ID of existing person if adding to an existing dossier"),
    # Optional legacy fields for backward compatibility
    full_name: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    date_of_birth: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Takes a batch of pictures of scanned documents.
    Azure Content Understanding analyzes the scans, detects signatures, stamps, and handwriting,
    and extracts the person details (Name, ID, DOB, etc.) directly from the document output.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Please upload at least one document scan image.")

    # Parse categories mapping if provided
    parsed_categories = []
    if categories_json:
        try:
            parsed_categories = json.loads(categories_json)
        except Exception:
            parsed_categories = []

    # Temporary staging of uploaded files to memory
    staged_items = []
    for idx, f in enumerate(files):
        if not f.filename:
            continue
        data = await f.read()
        if len(data) == 0:
            continue
        cat = parsed_categories[idx] if idx < len(parsed_categories) and parsed_categories[idx] else "Other"
        staged_items.append({
            "filename": f.filename,
            "content_type": f.content_type or "image/jpeg",
            "bytes": data,
            "category": cat
        })

    if not staged_items:
        raise HTTPException(status_code=400, detail="No valid file bytes received.")

    # 1. Run Azure Content Understanding on first/primary document to auto-extract person details
    primary_doc = staged_items[0]
    initial_analysis = content_understanding_service.analyze_document(
        file_bytes=primary_doc["bytes"],
        filename=primary_doc["filename"],
        category=primary_doc["category"],
        person_context={
            "full_name": full_name,
            "national_id": national_id,
            "person_type": person_type or project.person_types[0] if project.person_types else "Applicant",
            "date_of_birth": date_of_birth,
            "email": email,
            "phone": phone,
            "address": address
        } if full_name else None
    )

    extracted_person = initial_analysis.get("extracted_person", {})
    auto_name = full_name or extracted_person.get("full_name")
    auto_id = national_id or extracted_person.get("national_id")
    if not auto_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The document analysis did not identify a person's name. "
                "Upload a clearer image or provide full_name and retry."
            )
        )

    auto_type = person_type or extracted_person.get("person_type")
    if not auto_type or auto_type not in (project.person_types or []):
        auto_type = project.person_types[0] if project.person_types else "Applicant"
    auto_dob = date_of_birth or extracted_person.get("date_of_birth")
    auto_email = email or extracted_person.get("email")
    auto_phone = phone or extracted_person.get("phone")
    auto_address = address or extracted_person.get("address")

    # 2. Get or create Person record in Azure SQL Server
    person = None
    if person_id:
        person = db.query(Person).filter(Person.id == person_id, Person.project_id == project_id).first()

    if not person:
        # Check if person with same national_id already exists in this project
        if auto_id:
            person = db.query(Person).filter(Person.project_id == project_id, Person.national_id == auto_id).first()

    if not person:
        person = Person(
            project_id=project_id,
            person_type=auto_type,
            full_name=auto_name,
            national_id=auto_id,
            email=auto_email,
            phone=auto_phone,
            date_of_birth=auto_dob,
            address=auto_address,
            notes=notes or f"Person profile created from an uploaded {primary_doc['category']} document."
        )
        db.add(person)
        db.commit()
        db.refresh(person)

    # 3. Process and upload each scanned document in batch to Azure Account Storage Service
    for idx, item in enumerate(staged_items):
        blob_name, storage_ref, container = storage_service.upload_file(
            file_bytes=item["bytes"],
            filename=item["filename"],
            content_type=item["content_type"],
            person_id=person.id
        )

        document = Document(
            person_id=person.id,
            project_id=project.id,
            original_filename=item["filename"],
            content_type=item["content_type"],
            file_size=len(item["bytes"]),
            doc_category=item["category"],
            storage_reference=storage_ref,
            blob_name=blob_name,
            storage_container=container,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Analyze with Azure Content Understanding
        analysis_data = initial_analysis if idx == 0 else content_understanding_service.analyze_document(
            file_bytes=item["bytes"],
            filename=item["filename"],
            category=item["category"],
            person_context={
                "full_name": person.full_name,
                "national_id": person.national_id,
                "person_type": person.person_type,
                "date_of_birth": person.date_of_birth,
                "address": person.address
            },
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
        # Store structured fields and auto-extracted person in analysis
        fields = analysis_data.get("extracted_fields", {})
        fields["extracted_person"] = analysis_data.get("extracted_person", extracted_person)
        doc_analysis.extracted_fields = fields

        db.add(doc_analysis)
        db.commit()

    db.refresh(person)
    return get_person_dossier(person.id, db)


@router.get("/api/persons/{person_id}", response_model=PersonOut, summary="Get Person Dossier & Scans")
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
                "extracted_person": d.analysis.extracted_person,
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


@router.put("/api/persons/{person_id}", response_model=PersonOut, summary="Update Person Details")
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)):
    """Update person details"""
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


@router.delete("/api/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Person & Scans")
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
