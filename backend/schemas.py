"""
Pydantic Schemas for Request & Response Serialization
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# Document & Analysis Schemas
# ==============================================================================
class ExtractedPersonOut(BaseModel):
    full_name: Optional[str] = Field(None, description="Auto-extracted person name from document")
    national_id: Optional[str] = Field(None, description="National ID / CNIC / Identifier detected in scan")
    person_type: Optional[str] = Field(None, description="Inferred or assigned person role/category")
    date_of_birth: Optional[str] = Field(None, description="Date of birth detected from document")
    email: Optional[str] = Field(None, description="Email detected on document")
    phone: Optional[str] = Field(None, description="Phone number detected on document")
    address: Optional[str] = Field(None, description="Physical address detected on document")
    confidence: Optional[float] = Field(None, description="Extraction confidence score (0 to 1)")


class DocumentAnalysisBase(BaseModel):
    status: str = "completed"
    has_signature: bool = False
    has_stamp: bool = False
    is_handwritten: bool = False
    handwritten_percentage: float = 0.0
    detected_type: Optional[str] = None
    confidence_score: float = 0.0
    extracted_text: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    extracted_person: Optional[ExtractedPersonOut] = None


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


# ==============================================================================
# OpenAPI Content Understanding API Schemas
# ==============================================================================
class ContentUnderstandingAnalyzeRequest(BaseModel):
    file_url: Optional[str] = Field(None, description="Publicly accessible HTTP URL of the document/image to analyze")
    analyzer_id: Optional[str] = Field("invoice_analyzer", description="Azure Content Understanding analyzer ID (e.g. invoice_analyzer)")
    category: Optional[str] = Field("Other", description="Document category hint (e.g. ID Document, Fee Voucher, Certificate)")


class ContentUnderstandingAnalyzeResponse(BaseModel):
    status: str = Field("completed", description="Analysis status: completed or failed")
    detected_type: str = Field("Scanned Document", description="Document category detected by Azure Content Understanding")
    has_signature: bool = Field(False, description="Whether authorized hand signature was detected")
    has_stamp: bool = Field(False, description="Whether official stamp/seal was detected")
    is_handwritten: bool = Field(False, description="Whether handwritten content was detected")
    handwritten_percentage: float = Field(0.0, description="Percentage of document containing handwriting")
    confidence_score: float = Field(0.95, description="Overall extraction confidence score (0 to 1)")
    extracted_text: str = Field("", description="Full OCR extracted text")
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, description="Key-value pairs extracted by Azure Content Understanding")
    extracted_person: ExtractedPersonOut = Field(default_factory=ExtractedPersonOut, description="Person information auto-extracted from document scan")
    analysis_raw: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw Azure Content Understanding payload metadata")
