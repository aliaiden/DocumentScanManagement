"""
Projects Router
CRUD operations for Projects with custom Person Types.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Project, Person, Document
from backend.schemas import ProjectCreate, ProjectUpdate, ProjectOut, ProjectDetailOut
from backend.services.storage_service import storage_service

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    """List all projects with counts of people and documents"""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    results = []
    for proj in projects:
        p_count = db.query(Person).filter(Person.project_id == proj.id).count()
        d_count = db.query(Document).filter(Document.project_id == proj.id).count()
        results.append(
            ProjectOut(
                id=proj.id,
                title=proj.title,
                description=proj.description,
                person_types=proj.person_types,
                created_at=proj.created_at,
                updated_at=proj.updated_at,
                persons_count=p_count,
                documents_count=d_count,
            )
        )
    return results


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project with title, description, and allowed types of people"""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Project title is required.")

    types = payload.person_types or ["Applicant", "Employee", "Student", "Customer"]
    # Clean types
    types = [t.strip() for t in types if t.strip()]
    if not types:
        types = ["General"]

    project = Project(
        title=payload.title.strip(),
        description=payload.description,
    )
    project.person_types = types

    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        person_types=project.person_types,
        created_at=project.created_at,
        updated_at=project.updated_at,
        persons_count=0,
        documents_count=0,
    )


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project details and its list of persons"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    p_count = len(project.persons)
    d_count = db.query(Document).filter(Document.project_id == project.id).count()

    return ProjectDetailOut(
        id=project.id,
        title=project.title,
        description=project.description,
        person_types=project.person_types,
        created_at=project.created_at,
        updated_at=project.updated_at,
        persons_count=p_count,
        documents_count=d_count,
        persons=[
            {
                "id": p.id,
                "project_id": p.project_id,
                "person_type": p.person_type,
                "full_name": p.full_name,
                "national_id": p.national_id,
                "email": p.email,
                "phone": p.phone,
                "date_of_birth": p.date_of_birth,
                "address": p.address,
                "notes": p.notes,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "documents_count": len(p.documents),
                "documents": []
            }
            for p in project.persons
        ]
    )


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    """Update project title, description, or allowed person types"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    if payload.title is not None:
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty.")
        project.title = payload.title.strip()

    if payload.description is not None:
        project.description = payload.description

    if payload.person_types is not None:
        cleaned_types = [t.strip() for t in payload.person_types if t.strip()]
        if cleaned_types:
            project.person_types = cleaned_types

    db.commit()
    db.refresh(project)

    p_count = db.query(Person).filter(Person.project_id == project.id).count()
    d_count = db.query(Document).filter(Document.project_id == project.id).count()

    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        person_types=project.person_types,
        created_at=project.created_at,
        updated_at=project.updated_at,
        persons_count=p_count,
        documents_count=d_count,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and its associated persons, documents, and storage blobs"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Clean up associated files in Azure Storage
    documents = db.query(Document).filter(Document.project_id == project.id).all()
    for doc in documents:
        try:
            storage_service.delete_file(doc.blob_name)
        except Exception:
            pass

    db.delete(project)
    db.commit()
    return None
