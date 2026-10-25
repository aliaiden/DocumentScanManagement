"""
SQLAlchemy Database Models
Stores Projects, Persons, Scanned Documents (storage references), and Azure Content Understanding Analyses.
"""

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    # Stored as JSON string or comma-separated list: e.g. ["Student", "Faculty", "Staff", "Applicant"]
    person_types_raw = Column("person_types", Text, nullable=False, default='["Applicant", "Employee", "Student", "Customer"]')
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    persons = relationship("Person", back_populates="project", cascade="all, delete-orphan", order_by="Person.created_at.desc()")

    @property
    def person_types(self) -> list[str]:
        if not self.person_types_raw:
            return ["Applicant", "Employee", "Student", "Customer"]
        try:
            parsed = json.loads(self.person_types_raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [pt.strip() for pt in self.person_types_raw.split(",") if pt.strip()]

    @person_types.setter
    def person_types(self, types_list: list[str]):
        if isinstance(types_list, list):
            self.person_types_raw = json.dumps(types_list)
        else:
            self.person_types_raw = json.dumps([types_list])


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    person_type = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=False, index=True)
    national_id = Column(String(100), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    date_of_birth = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="persons")
    documents = relationship("Document", back_populates="person", cascade="all, delete-orphan", order_by="Document.created_at.desc()")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    doc_category = Column(String(100), nullable=False, default="Other", index=True)
    # Storage reference: Full Azure Blob URL or Storage Path
    storage_reference = Column(String(1024), nullable=False)
    blob_name = Column(String(255), nullable=False, index=True)
    storage_container = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    person = relationship("Person", back_populates="documents")
    analysis = relationship("DocumentAnalysis", back_populates="document", uselist=False, cascade="all, delete-orphan")


class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    has_signature = Column(Boolean, default=False, nullable=False)
    has_stamp = Column(Boolean, default=False, nullable=False)
    is_handwritten = Column(Boolean, default=False, nullable=False)
    handwritten_percentage = Column(Float, default=0.0, nullable=False)
    detected_type = Column(String(100), nullable=True)
    confidence_score = Column(Float, default=0.0, nullable=False)
    extracted_text = Column(Text, nullable=True)
    extracted_fields_raw = Column("extracted_fields", Text, nullable=True)
    analysis_raw = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="analysis")

    @property
    def extracted_fields(self) -> dict:
        if not self.extracted_fields_raw:
            return {}
        try:
            return json.loads(self.extracted_fields_raw)
        except Exception:
            return {}

    @extracted_fields.setter
    def extracted_fields(self, data: dict):
        self.extracted_fields_raw = json.dumps(data)


class AgentAuditLog(Base):
    __tablename__ = "agent_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="NO ACTION"), nullable=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=True, index=True)
    audit_type = Column(String(100), nullable=False)
    findings = Column(Text, nullable=False)
    compliance_status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
