"""
Pydantic Schemas for Request & Response Serialization
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# Document & Analysis Schemas
# ==============================================================================
class DocumentAnalysisBase(BaseModel):
    status: str = "pending"
    has_signature: bool = False
    has_stamp: bool = False
    is_handwritten: bool = False
    handwritten_percentage: float = 0.0
    detected_type: Optional[str] = None
    confidence_score: float = 0.0
    extracted_text: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)


class DocumentAnalysisOut(DocumentAnalysisBase):
    id: int
    document_id: int
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentBase(BaseModel):
    original_filename: str
    content_type: str
    file_size: int
    doc_category: str = "Other"


class DocumentOut(DocumentBase):
    id: int
    person_id: int
    project_id: int
    storage_reference: str
    blob_name: str
    storage_container: str
    created_at: datetime
    analysis: Optional[DocumentAnalysisOut] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Person Schemas
# ==============================================================================
class PersonBase(BaseModel):
    person_type: str
    full_name: str
    national_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class PersonCreate(PersonBase):
    project_id: int


class PersonUpdate(BaseModel):
    person_type: Optional[str] = None
    full_name: Optional[str] = None
    national_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class PersonOut(PersonBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    documents_count: int = 0
    documents: List[DocumentOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Project Schemas
# ==============================================================================
class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    person_types: List[str] = Field(default_factory=lambda: ["Applicant", "Employee", "Student", "Customer"])


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    person_types: Optional[List[str]] = None


class ProjectOut(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    persons_count: int = 0
    documents_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailOut(ProjectOut):
    persons: List[PersonOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# AI Agent Schemas
# ==============================================================================
class AgentChatRequest(BaseModel):
    query: str
    project_id: Optional[int] = None
    person_id: Optional[int] = None
    chat_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    answer: str
    agent_action: Optional[str] = None
    context_used: Dict[str, Any] = Field(default_factory=dict)
    suggestions: List[str] = Field(default_factory=list)


class AgentAuditFinding(BaseModel):
    category: str
    document_id: Optional[int] = None
    document_name: Optional[str] = None
    status: str  # 'OK', 'WARNING', 'FAIL'
    message: str


class AgentAuditResponse(BaseModel):
    person_id: int
    person_name: str
    person_type: str
    compliance_status: str  # 'Compliant', 'Action Required', 'Missing Information'
    score: int  # 0 to 100
    summary: str
    findings: List[AgentAuditFinding]
    verified_items: List[str]
    missing_items: List[str]


# ==============================================================================
# System Status Schema
# ==============================================================================
class ServiceStatus(BaseModel):
    name: str
    connected: bool
    status_text: str
    provider: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SystemStatusOut(BaseModel):
    database: ServiceStatus
    storage: ServiceStatus
    content_understanding: ServiceStatus
    ai_agent: ServiceStatus
