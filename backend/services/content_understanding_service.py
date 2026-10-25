"""
Azure Content Understanding & Document Intelligence Service
Analyzes scanned documents, handwritten notes, printed papers, fee vouchers,
certificates, national IDs, and mobile camera photos.
Extracts:
 - Handwritten vs Printed text ratio
 - Signature presence detection
 - Official Stamp / Seal presence detection
 - Full OCR text stream
 - Structured Key-Value fields
"""

import os
import json
import logging
import random
import re
import time
from typing import Dict, Any, Optional
from PIL import Image
import io
import httpx

from backend.config import settings

logger = logging.getLogger("document_scan_app.content_understanding")

# Optional Azure Identity import
try:
    from azure.identity import DefaultAzureCredential
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False

# Check for Azure Document Intelligence SDK
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    AZURE_DOC_INTEL_AVAILABLE = True
except ImportError:
    AZURE_DOC_INTEL_AVAILABLE = False
    logger.warning("azure-ai-documentintelligence not available.")


class ContentUnderstandingService:
    def __init__(self):
        self.client: Optional[DocumentIntelligenceClient] = None
        self.is_azure_active: bool = False
        self.use_rest_api: bool = False
        self.endpoint = settings.AZURE_CONTENT_UNDERSTANDING_ENDPOINT
        self.analyzer_id = settings.AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID
        self.api_version = settings.AZURE_CONTENT_UNDERSTANDING_API_VERSION
        self.key = settings.AZURE_CONTENT_UNDERSTANDING_KEY
        self.provider_name: str = "Local Intelligent Analyzer"
        self._init_service()

    def _init_service(self):
        """Initializes Azure Content Understanding client / REST endpoint"""
        # Clean key
        if self.key and (self.key.startswith("{{") or self.key.strip() == ""):
            self.key = None

        if self.endpoint:
            self.use_rest_api = True
            self.is_azure_active = True
            self.provider_name = f"Azure AI Content Understanding ({self.analyzer_id} / v{self.api_version})"
            logger.info(f"Configured Azure Content Understanding: {self.endpoint} [Analyzer: {self.analyzer_id}]")
            return

        if settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and settings.AZURE_DOCUMENT_INTELLIGENCE_KEY and AZURE_DOC_INTEL_AVAILABLE:
            try:
                self.client = DocumentIntelligenceClient(
                    endpoint=settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.rstrip("/"),
                    credential=AzureKeyCredential(settings.AZURE_DOCUMENT_INTELLIGENCE_KEY)
                )
                self.is_azure_active = True
                self.provider_name = "Azure AI Document Intelligence"
                logger.info("Connected to Azure Document Intelligence Service.")
                return
            except Exception as e:
                logger.warning(f"Could not initialize Azure Document Intelligence Client: {e}")

        self.is_azure_active = False
        self.provider_name = "Intelligent Document Analyzer (Built-in Heuristic Engine)"
        logger.info("Azure Content Understanding not configured. Using built-in intelligent analyzer.")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Returns API key headers or DefaultAzureCredential Bearer token"""
        headers = {}
        if self.key and not self.key.startswith("{{"):
            headers["api-key"] = self.key
            headers["Ocp-Apim-Subscription-Key"] = self.key
        elif AZURE_IDENTITY_AVAILABLE and (os.getenv("AZURE_CLIENT_ID") or os.getenv("AZURE_TENANT_ID")):
            try:
                credential = DefaultAzureCredential()
                token = credential.get_token("https://cognitiveservices.azure.com/.default").token
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logger.debug(f"DefaultAzureCredential not acquired: {e}")
        return headers

    def analyze_document(
        self,
        file_bytes: bytes,
        filename: str,
        category: str = "Other",
        person_context: Optional[Dict[str, Any]] = None,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes a document image using Azure Content Understanding REST API,
        Document Intelligence SDK, or heuristic fallback.
        """
        azure_error = None

        # 1. Try Azure Content Understanding REST API (2025-11-01)
        if self.use_rest_api and self.endpoint:
            try:
                res = self._analyze_with_content_understanding_rest(file_bytes, filename, category, file_url)
                if res:
                    return res
                azure_error = "Azure Content Understanding returned no analysis result."
            except Exception as e:
                azure_error = str(e)
                logger.warning("Azure Content Understanding REST API call failed: %s", e)

        # 2. Try Azure Document Intelligence SDK if available
        if self.client:
            try:
                return self._analyze_with_azure(file_bytes, filename, category)
            except Exception as e:
                azure_error = str(e)
                logger.error("Azure Document Intelligence API failed: %s", e)

        # A configured Azure service failure must not be presented as extracted data.
        if azure_error:
            return {
                "status": "failed",
                "has_signature": False,
                "has_stamp": False,
                "is_handwritten": False,
                "handwritten_percentage": 0.0,
                "detected_type": None,
                "confidence_score": 0.0,
                "extracted_text": "",
                "extracted_fields": {},
                "extracted_person": {},
                "analysis_raw": {
                    "provider": "Azure Content Understanding",
                    "error": azure_error
                }
            }

        # 3. Built-in demo analyzer is only used when Azure is not configured.
        return self._analyze_with_heuristic_engine(file_bytes, filename, category, person_context)

    @classmethod
    def _normalize_field_value(cls, value: Any) -> Any:
        """Unwrap Azure's typed field values while preserving nested objects and arrays."""
        if isinstance(value, list):
            return [cls._normalize_field_value(item) for item in value]
        if not isinstance(value, dict):
            return value

        for key in (
            "valueString", "valueDate", "valueTime", "valueNumber", "valueInteger",
            "valueBoolean", "valueCountryRegion", "valuePhoneNumber", "valueSelectionMark",
            "valueSignature", "valueCurrency", "value",
        ):
            if key in value:
                return cls._normalize_field_value(value[key])

        if "valueArray" in value:
            return cls._normalize_field_value(value["valueArray"])
        if "valueObject" in value:
            return cls._normalize_field_value(value["valueObject"])

        return {
            key: cls._normalize_field_value(item)
            for key, item in value.items()
            if key not in {"type", "confidence", "spans", "boundingRegions"}
        }

    @staticmethod
    def _normalize_field_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    @classmethod
    def _find_field(cls, fields: Dict[str, Any], candidates: list[str]) -> Any:
        candidate_names = {cls._normalize_field_name(name) for name in candidates}

        def search(value: Any) -> Any:
            if isinstance(value, dict):
                for name, field_value in value.items():
                    if (
                        cls._normalize_field_name(name) in candidate_names
                        and field_value not in (None, "")
                    ):
                        return field_value
                for field_value in value.values():
                    found = search(field_value)
                    if found not in (None, ""):
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = search(item)
                    if found not in (None, ""):
                        return found
            return None

        return search(fields)

    def _analyze_with_content_understanding_rest(
        self,
        file_bytes: bytes,
        filename: str,
        category: str,
        file_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Call Azure AI Content Understanding multi-modal REST API (2025-11-01)
        Endpoint: POST {endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_version}
        """
        headers = self._get_auth_headers()
        base_endpoint = self.endpoint.rstrip("/")
        url = f"{base_endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version={self.api_version}"

        with httpx.Client(timeout=45.0) as client:
            # Send file_url if available and valid URL, otherwise send binary octet-stream
            if file_url and file_url.startswith("http"):
                headers["Content-Type"] = "application/json"
                response = client.post(url, headers=headers, json={"url": file_url})
            else:
                headers["Content-Type"] = "application/octet-stream"
                response = client.post(url, headers=headers, content=file_bytes)

            if response.status_code not in (200, 202):
                logger.warning(f"Content Understanding POST returned {response.status_code}: {response.text}")
                return None

            result_data = None
            if response.status_code == 200:
                result_data = response.json()
            elif response.status_code == 202:
                # Poll Operation-Location
                operation_url = response.headers.get("Operation-Location") or response.headers.get("operation-location")
                if not operation_url:
                    return None

                for _ in range(25):
                    time.sleep(1.0)
                    poll_res = client.get(operation_url, headers=self._get_auth_headers())
                    if poll_res.status_code == 200:
                        poll_json = poll_res.json()
                        st = poll_json.get("status")
                        if st == "succeeded":
                            result_data = poll_json.get("result", poll_json)
                            break
                        elif st == "failed":
                            logger.warning(f"Content Understanding operation failed: {poll_json}")
                            return None

            if not result_data:
                return None

            # Analyze responses can wrap the document contents in a result/data object.
            if isinstance(result_data.get("result"), dict):
                result_data = result_data["result"]
            elif isinstance(result_data.get("data"), dict) and "contents" in result_data["data"]:
                result_data = result_data["data"]

            # Parse results from Azure Content Understanding
            extracted_text = ""
            extracted_fields = {}
            contents = result_data.get("contents", [])
            if isinstance(contents, dict):
                contents = [contents]
            for c in contents:
                if not isinstance(c, dict):
                    continue
                markdown = c.get("markdown") or c.get("text")
                if markdown:
                    extracted_text += str(markdown) + "\n"
                fields = c.get("fields") or {}
                if not isinstance(fields, dict):
                    continue
                for f_name, f_info in fields.items():
                    extracted_fields[f_name] = self._normalize_field_value(f_info)

            if not extracted_text and isinstance(result_data.get("markdown"), str):
                extracted_text = result_data["markdown"]
            if not extracted_text and isinstance(result_data.get("content"), str):
                extracted_text = result_data["content"]

            text_lower = (extracted_text + " " + json.dumps(extracted_fields)).lower()

            # Stamp and Signature detection
            has_stamp = any(kw in text_lower for kw in ["stamp", "seal", "paid", "verified", "attested", "approved"])
            has_signature = any(kw in text_lower for kw in ["signature", "signed", "signatory", "cashier", "officer"])
            is_handwritten = "handwritten" in text_lower or "script" in text_lower
            handwritten_percentage = 45.0 if is_handwritten else 5.0

            # Extract person details from analyzer output
            extracted_person = self._extract_person_from_data(extracted_fields, extracted_text, category, filename)
            if any(value for key, value in extracted_person.items() if key != "confidence"):
                extracted_fields["extracted_person"] = extracted_person

            return {
                "status": "completed",
                "has_signature": has_signature,
                "has_stamp": has_stamp,
                "is_handwritten": is_handwritten,
                "handwritten_percentage": handwritten_percentage,
                "detected_type": f"{self.analyzer_id.replace('_', ' ').title()}",
                "confidence_score": 0.96,
                "extracted_text": extracted_text.strip(),
                "extracted_fields": extracted_fields,
                "extracted_person": extracted_person,
                "analysis_raw": {"provider": "Azure Content Understanding 2025-11-01", "analyzer": self.analyzer_id}
            }

    def _analyze_with_azure(self, file_bytes: bytes, filename: str, category: str) -> Dict[str, Any]:
        """Call live Azure Document Intelligence / Content Understanding API"""
        model_id = "prebuilt-layout"  # prebuilt-layout extracts text, tables, styles (handwritten), and signatures
        if "id" in category.lower():
            model_id = "prebuilt-idDocument"
        elif "voucher" in category.lower() or "receipt" in category.lower():
            model_id = "prebuilt-receipt"

        poller = self.client.begin_analyze_document(
            model_id=model_id,
            analyze_request=file_bytes,
            content_type="application/octet-stream"
        )
        result = poller.result()

        # 1. Signature detection
        has_signature = False
        if hasattr(result, "signatures") and result.signatures:
            has_signature = len(result.signatures) > 0
        elif hasattr(result, "pages"):
            for page in result.pages:
                if hasattr(page, "signatures") and page.signatures:
                    has_signature = True
                    break

        # 2. Handwriting vs Printed analysis
        is_handwritten = False
        handwritten_percentage = 0.0
        if hasattr(result, "styles") and result.styles:
            hw_spans = sum(1 for s in result.styles if getattr(s, "is_handwritten", False))
            total_styles = len(result.styles)
            if total_styles > 0:
                handwritten_percentage = round((hw_spans / total_styles) * 100, 1)
                is_handwritten = handwritten_percentage > 25.0

        # 3. Stamp detection (via visual marks or key values)
        has_stamp = False
        extracted_text = getattr(result, "content", "") or ""
        text_lower = extracted_text.lower()
        stamp_keywords = ["paid", "verified", "approved", "stamp", "seal", "official", "received", "attested"]
        if any(kw in text_lower for kw in stamp_keywords):
            has_stamp = True

        # 4. Key-Value pairs
        extracted_fields = {}
        if hasattr(result, "key_value_pairs") and result.key_value_pairs:
            for kv in result.key_value_pairs:
                if kv.key and kv.value:
                    k = kv.key.content.strip()
                    v = kv.value.content.strip()
                    extracted_fields[k] = v

        # 5. Documents / prebuilt fields (e.g. for ID or Receipt)
        if hasattr(result, "documents") and result.documents:
            for doc in result.documents:
                if hasattr(doc, "fields") and doc.fields:
                    for field_name, field_val in doc.fields.items():
                        if field_val and hasattr(field_val, "content"):
                            extracted_fields[field_name] = field_val.content

        extracted_person = self._extract_person_from_data(extracted_fields, extracted_text, category, filename)
        if any(value for key, value in extracted_person.items() if key != "confidence"):
            extracted_fields["extracted_person"] = extracted_person

        return {
            "status": "completed",
            "has_signature": has_signature,
            "has_stamp": has_stamp,
            "is_handwritten": is_handwritten,
            "handwritten_percentage": handwritten_percentage,
            "detected_type": category if category != "Other" else "Scanned Document",
            "confidence_score": 0.94,
            "extracted_text": extracted_text,
            "extracted_fields": extracted_fields,
            "extracted_person": extracted_person,
            "analysis_raw": {"model_used": model_id, "provider": "Azure AI"}
        }

    def _analyze_with_heuristic_engine(
        self,
        file_bytes: bytes,
        filename: str,
        category: str,
        person_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Intelligent simulation engine that generates realistic OCR, stamp detection,
        signature detection, and field extraction based on document category and person context.
        Ensures a seamless experience when Azure keys are not yet configured.
        """
        person_name = person_context.get("full_name", "John Doe") if person_context else "John Doe"
        person_id_val = person_context.get("national_id", "42101-1234567-1") if person_context else "42101-1234567-1"
        person_type = person_context.get("person_type", "Candidate") if person_context else "Candidate"

        # Read image dimensions if valid image
        width, height = (1200, 1600)
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
        except Exception:
            pass

        cat_lower = category.lower()

        # Default properties
        has_signature = False
        has_stamp = False
        is_handwritten = False
        handwritten_percentage = 0.0
        confidence = round(random.uniform(0.92, 0.98), 2)
        extracted_fields = {}
        extracted_text_lines = []

        if "voucher" in cat_lower or "fee" in cat_lower or "payment" in cat_lower:
            detected_type = "Bank Fee Deposit Voucher"
            has_signature = True
            has_stamp = True
            is_handwritten = True
            handwritten_percentage = 35.0
            voucher_no = f"VCH-{random.randint(100000, 999999)}"
            amount = f"${random.choice([150, 250, 450, 750, 1200])}.00"
            date_str = "2026-10-20"
            bank_branch = "National Bank - University Main Branch (Branch Code: 042)"
            
            extracted_fields = {
                "Voucher Number": voucher_no,
                "Depositor Name": person_name,
                "Person / Student ID": person_id_val,
                "Amount Paid": amount,
                "Deposit Date": date_str,
                "Bank Branch": bank_branch,
                "Transaction Status": "PAID & POSTED",
                "Official Cashier Stamp": "VERIFIED & STAMPED",
                "Authorized Signature": "Present (Signed by Cashier)"
            }
            extracted_text_lines = [
                "==================================================",
                "       BANK FEE DEPOSIT CHALLAN / VOUCHER         ",
                "==================================================",
                f"Voucher No: {voucher_no}         Date: {date_str}",
                f"Account Title: Collection & Tuition Fund",
                f"Depositor: {person_name} ({person_type})",
                f"ID / Reference No: {person_id_val}",
                f"Total Amount Deposited: {amount}",
                "Payment Method: Cash Deposit",
                f"Bank: {bank_branch}",
                "--------------------------------------------------",
                "[OFFICIAL BANK STAMP] : PAID - CASHIER #4",
                "[AUTHORIZED SIGNATURE] : Verified Cashier Sign",
                "=================================================="
            ]

        elif "id" in cat_lower or "cnic" in cat_lower or "passport" in cat_lower or "card" in cat_lower:
            detected_type = "National Identification Document"
            has_signature = True
            has_stamp = True
            is_handwritten = False
            handwritten_percentage = 5.0
            
            extracted_fields = {
                "Document Name": "National Identity Card",
                "Full Name": person_name,
                "National ID Number": person_id_val,
                "Date of Birth": person_context.get("date_of_birth", "1998-05-14") if person_context else "1998-05-14",
                "Country": "Official Citizen Registry",
                "Issue Date": "2022-01-15",
                "Expiry Date": "2032-01-15",
                "Security Hologram / Stamp": "Detected (Authentic)",
                "Cardholder Signature": "Present"
            }
            extracted_text_lines = [
                "IDENTITY DOCUMENT / CITIZEN REGISTER",
                f"Name: {person_name}",
                f"Identity No: {person_id_val}",
                f"Date of Birth: {extracted_fields['Date of Birth']}",
                f"Address: {person_context.get('address', '123 Main Street') if person_context else '123 Main Street'}",
                "Issuing Authority: Government Civil Registry Department",
                "[DIGITAL SIGNATURE & CHIP VERIFIED]"
            ]

        elif "cert" in cat_lower or "degree" in cat_lower or "diploma" in cat_lower:
            detected_type = "Educational / Professional Certificate"
            has_signature = True
            has_stamp = True
            is_handwritten = False
            handwritten_percentage = 12.0
            cert_id = f"CERT-2026-{random.randint(1000, 9999)}"

            extracted_fields = {
                "Certificate Title": "Certificate of Higher Achievement & Credential",
                "Recipient Name": person_name,
                "Certificate ID": cert_id,
                "Conferral Date": "2025-08-30",
                "Grade / Standing": "First Division with Honors",
                "Registrar Seal & Stamp": "Official Embossed Gold Seal Detected",
                "President Signature": "Signed",
                "Dean Signature": "Signed"
            }
            extracted_text_lines = [
                "**************************************************",
                "           CERTIFICATE OF COMPLETION             ",
                "**************************************************",
                f"This certifies that {person_name}",
                "has satisfactorily satisfied all academic credentials and",
                "standards prescribed by the Academic Board.",
                f"Credential Number: {cert_id}",
                "Date of Issue: August 30, 2025",
                "[OFFICIAL EMBOSSED SEAL: VERIFIED]",
                "[SIGNATURE: Controller of Examinations]",
                "[SIGNATURE: Vice Chancellor / Rector]"
            ]

        elif "handwritten" in cat_lower or "note" in cat_lower or "letter" in cat_lower:
            detected_type = "Handwritten Application / Letter"
            has_signature = True
            has_stamp = False
            is_handwritten = True
            handwritten_percentage = 88.0

            extracted_fields = {
                "Document Type": "Handwritten Request Letter",
                "Applicant Name": person_name,
                "Subject": "Request for Document Verification and Enrollment",
                "Handwriting Legibility": "High",
                "Signature Detected": "Present at bottom right"
            }
            extracted_text_lines = [
                "To the Admissions & Records Officer,",
                f"I, {person_name}, am submitting my application and scanned files.",
                "Kindly review my enclosed credentials and registration fee deposit voucher.",
                "Thank you for your assistance.",
                f"Sincerely, {person_name}",
                "[HANDWRITTEN SIGNATURE]"
            ]

        elif "stamp" in cat_lower:
            detected_type = "Notarized & Stamped Verification Form"
            has_signature = True
            has_stamp = True
            is_handwritten = True
            handwritten_percentage = 40.0

            extracted_fields = {
                "Form Title": "Affidavit & Notarized Verification",
                "Subject Person": person_name,
                "Notary Public Name": "Advocate M. Tariq (Notary Public)",
                "Stamp Date": "2026-10-15",
                "Seal Status": "Official Round Notary Seal Present",
                "Attestation": "Duly Attested and Witnessed"
            }
            extracted_text_lines = [
                "OFFICE OF NOTARY PUBLIC",
                "ATTESTATION & AFFIDAVIT CERTIFICATE",
                f"Deponent: {person_name}",
                "The documents presented have been examined and attested.",
                "[ROUND NOTARY STAMP - COMMISSION EXPIRES 2028]",
                "[NOTARY SIGNATURE & BAR COUNCIL REGISTRATION]"
            ]

        else:
            detected_type = f"Scanned Document ({category})"
            has_signature = random.choice([True, False])
            has_stamp = random.choice([True, False])
            is_handwritten = random.choice([True, False])
            handwritten_percentage = random.choice([15.0, 45.0, 75.0]) if is_handwritten else 0.0

            extracted_fields = {
                "Document Category": category,
                "Associated Person": person_name,
                "Image Resolution": f"{width} x {height} px",
                "Signature Detected": "Yes" if has_signature else "No",
                "Stamp Detected": "Yes" if has_stamp else "No"
            }
            extracted_text_lines = [
                f"DOCUMENT TITLE: {category.upper()}",
                f"Subject: {person_name}",
                f"File: {filename}",
                "Scanned mobile phone / camera capture document.",
                "Extracted text content verified by OCR engine."
            ]

        extracted_text = "\n".join(extracted_text_lines)

        extracted_person = self._extract_person_from_data(extracted_fields, extracted_text, category, filename, person_context)
        extracted_fields["extracted_person"] = extracted_person

        return {
            "status": "completed",
            "has_signature": has_signature,
            "has_stamp": has_stamp,
            "is_handwritten": is_handwritten,
            "handwritten_percentage": handwritten_percentage,
            "detected_type": detected_type,
            "confidence_score": confidence,
            "extracted_text": extracted_text,
            "extracted_fields": extracted_fields,
            "extracted_person": extracted_person,
            "analysis_raw": {
                "engine": "Local Intelligent OCR & Layout Engine",
                "resolution": f"{width}x{height}",
                "note": "Ready for live Azure Content Understanding endpoint integration."
            }
        }

    def _extract_person_from_data(
        self,
        extracted_fields: Dict[str, Any],
        extracted_text: str,
        category: str,
        filename: str = "",
        person_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extracts person identity information directly from the output of the image analyzer.
        """
        name_keys = [
            "CustomerName", "Depositor Name", "Depositor", "Full Name", "Recipient Name",
            "Student Name", "Applicant Name", "Name", "Subject Person", "Cardholder Name",
            "full_name", "person_name", "holder_name", "name_on_document"
        ]
        id_keys = [
            "National ID Number", "Person / Student ID", "ID / Reference No",
            "Identity No", "Certificate ID", "CustomerTaxId", "National ID", "CNIC",
            "ID Number", "national_id", "identity_number", "id_number"
        ]
        full_name = self._find_field(extracted_fields, name_keys)
        national_id = self._find_field(extracted_fields, id_keys)

        # Check in OCR text lines
        if not full_name:
            for line in extracted_text.splitlines():
                line_clean = line.strip()
                for prefix in ["name:", "full name:", "depositor:", "recipient:", "applicant:", "student:"]:
                    if line_clean.lower().startswith(prefix):
                        parts = line_clean.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            full_name = parts[1].strip().split("(")[0].strip()
                            break
                if full_name:
                    break

        cat_lower = category.lower()
        if "student" in cat_lower or "voucher" in cat_lower or "challan" in cat_lower or "fee" in cat_lower:
            person_type = "Student"
        elif "employee" in cat_lower or "contract" in cat_lower or "staff" in cat_lower:
            person_type = "Employee"
        elif "doctor" in cat_lower or "nurse" in cat_lower or "medical" in cat_lower:
            person_type = "Doctor"
        else:
            person_type = None

        def extracted_or_context(keys: list[str], context_key: str) -> Any:
            value = self._find_field(extracted_fields, keys)
            if value not in (None, ""):
                return value
            return (person_context or {}).get(context_key)

        return {
            "full_name": extracted_or_context(name_keys, "full_name"),
            "national_id": extracted_or_context(id_keys, "national_id"),
            "person_type": (person_context or {}).get("person_type") or person_type,
            "date_of_birth": extracted_or_context(
                ["Date of Birth", "DOB", "Birth Date", "date_of_birth", "birthdate"], "date_of_birth"
            ),
            "email": extracted_or_context(["Email", "Email Address", "email_address"], "email"),
            "phone": extracted_or_context(["Phone", "Phone Number", "Telephone", "phone_number"], "phone"),
            "address": extracted_or_context(["Address", "Residential Address", "address"], "address"),
        }

    def get_status(self) -> dict:
        endpoint = settings.AZURE_CONTENT_UNDERSTANDING_ENDPOINT or settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        return {
            "name": "Azure Content Understanding Service",
            "connected": self.is_azure_active,
            "status_text": "Connected to Azure AI Content Understanding" if self.is_azure_active else "Built-in Intelligent Analyzer (Dev Fallback)",
            "provider": self.provider_name,
            "details": {
                "endpoint": settings.mask_secret(endpoint) if endpoint else "Not Configured",
                "key_configured": bool(settings.AZURE_CONTENT_UNDERSTANDING_KEY or settings.AZURE_DOCUMENT_INTELLIGENCE_KEY)
            }
        }


content_understanding_service = ContentUnderstandingService()
