"""
Azure Content Understanding OpenAPI v3 Router
Provides standalone REST endpoints for other applications to analyze documents,
invoices, fee vouchers, certificates, and ID cards, and auto-extract person details.
"""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from backend.services.content_understanding_service import content_understanding_service
from backend.config import settings
from backend.schemas import (
    ContentUnderstandingAnalyzeRequest,
    ContentUnderstandingAnalyzeResponse,
    ExtractedPersonOut
)

router = APIRouter(prefix="/api/content-understanding", tags=["Azure Content Understanding"])


@router.post(
    "/analyze",
    response_model=ContentUnderstandingAnalyzeResponse,
    summary="Analyze Document & Extract Person Details",
    description="Direct OpenAPI v3 endpoint to analyze a scanned document (file upload or URL) using Azure Content Understanding. Returns signatures, stamps, handwriting meter, full OCR text, extracted key-values, and auto-extracted person details."
)
async def analyze_document_endpoint(
    file: Optional[UploadFile] = File(None, description="Document image file (JPEG, PNG, PDF) to analyze"),
    file_url: Optional[str] = Form(None, description="Or public HTTP URL to document image"),
    analyzer_id: Optional[str] = Form(None, description="Azure Content Understanding analyzer ID (defaults to invoice_analyzer)"),
    category: Optional[str] = Form("Other", description="Document category hint (e.g. ID Document, Fee Voucher, Certificate)")
):
    """
    OpenAPI v3 standard endpoint for external apps to analyze documents
    and auto-extract person details using Azure Content Understanding.
    """
    if not file and not file_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a document file upload or a file_url must be provided."
        )

    file_bytes = b""
    filename = "document.jpg"
    if file:
        filename = file.filename or "document.jpg"
        file_bytes = await file.read()

    active_analyzer = analyzer_id or settings.AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID
    # Temporarily set active analyzer if specified
    original_analyzer = content_understanding_service.analyzer_id
    if analyzer_id:
        content_understanding_service.analyzer_id = analyzer_id

    try:
        result = content_understanding_service.analyze_document(
            file_bytes=file_bytes,
            filename=filename,
            category=category or "Other",
            file_url=file_url
        )
    finally:
        content_understanding_service.analyzer_id = original_analyzer

    person_dict = result.get("extracted_person", {})
    extracted_person = ExtractedPersonOut(
        full_name=person_dict.get("full_name"),
        national_id=person_dict.get("national_id"),
        person_type=person_dict.get("person_type"),
        date_of_birth=person_dict.get("date_of_birth"),
        email=person_dict.get("email"),
        phone=person_dict.get("phone"),
        address=person_dict.get("address"),
        confidence=person_dict.get("confidence", 0.95)
    )

    return ContentUnderstandingAnalyzeResponse(
        status=result.get("status", "completed"),
        detected_type=result.get("detected_type", "Scanned Document"),
        has_signature=result.get("has_signature", False),
        has_stamp=result.get("has_stamp", False),
        is_handwritten=result.get("is_handwritten", False),
        handwritten_percentage=result.get("handwritten_percentage", 0.0),
        confidence_score=result.get("confidence_score", 0.95),
        extracted_text=result.get("extracted_text", ""),
        extracted_fields=result.get("extracted_fields", {}),
        extracted_person=extracted_person,
        analysis_raw=result.get("analysis_raw", {})
    )


@router.get(
    "/info",
    summary="Get Azure Content Understanding Configuration",
    description="Returns active Azure Content Understanding endpoint, analyzer ID, and API version."
)
def get_content_understanding_info():
    """Returns endpoint configuration for external consumers"""
    return {
        "endpoint": settings.AZURE_CONTENT_UNDERSTANDING_ENDPOINT,
        "analyzer_id": settings.AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID,
        "api_version": settings.AZURE_CONTENT_UNDERSTANDING_API_VERSION,
        "supported_analyzers": [
            "invoice_analyzer",
            "prebuilt-layout",
            "prebuilt-idDocument",
            "prebuilt-receipt",
            "prebuilt-document"
        ],
        "key_configured": bool(settings.AZURE_CONTENT_UNDERSTANDING_KEY and not settings.AZURE_CONTENT_UNDERSTANDING_KEY.startswith("{{"))
    }
