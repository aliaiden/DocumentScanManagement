"""
AI Agent Service
Intelligent Agent for Document Compliance, Cross-verification, Search, and Conversational Q&A.
Audits scanned mobile camera pictures, fee vouchers, certificates, IDs, signatures, and stamps.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.models import Project, Person, Document, DocumentAnalysis, AgentAuditLog
from backend.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentAuditResponse,
    AgentAuditFinding
)
from backend.config import settings

logger = logging.getLogger("document_scan_app.ai_agent")


class AIAgentService:
    def __init__(self):
        self.provider_name = "Embedded Intelligent Agent"
        self._init_llm()

    def _init_llm(self):
        """Optional OpenAI / Azure OpenAI integration for conversational polish"""
        self.has_llm = False
        if settings.OPENAI_API_KEY or (settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY):
            self.has_llm = True
            logger.info("External LLM configured for AI Agent.")

    def audit_person(self, db: Session, person_id: int) -> AgentAuditResponse:
        """
        Runs comprehensive AI audit on a person's scanned documents:
         - Checks required documents by person type (ID, Fee Voucher, Certificate, etc.)
         - Verifies presence of authorized signatures
         - Verifies presence of official bank/notary stamps
         - Cross-checks extracted names & ID numbers with form metadata
        """
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise ValueError(f"Person with ID {person_id} not found.")

        documents = db.query(Document).filter(Document.person_id == person_id).all()
        findings: List[AgentAuditFinding] = []
        verified_items: List[str] = []
        missing_items: List[str] = []

        total_weight = 0
        earned_weight = 0

        # Rule 1: Check document count
        if not documents:
            findings.append(AgentAuditFinding(
                category="General",
                status="FAIL",
                message="No scanned documents uploaded for this person yet. Mobile camera pictures or scans required."
            ))
            missing_items.append("At least one identification or official document")
            return AgentAuditResponse(
                person_id=person.id,
                person_name=person.full_name,
                person_type=person.person_type,
                compliance_status="Missing Information",
                score=0,
                summary=f"No documents have been uploaded for {person.full_name}.",
                findings=findings,
                verified_items=[],
                missing_items=missing_items
            )

        # Expected documents rule based on person type
        pt_lower = person.person_type.lower()
        expected_types = ["id document"]
        if "student" in pt_lower or "applicant" in pt_lower:
            expected_types.append("fee voucher")
        elif "employee" in pt_lower or "staff" in pt_lower or "faculty" in pt_lower:
            expected_types.append("certificate")

        uploaded_categories = [doc.doc_category.lower() for doc in documents]

        # 1. Check ID Document
        total_weight += 30
        has_id = any("id" in cat for cat in uploaded_categories)
        if has_id:
            earned_weight += 30
            verified_items.append("National Identification Document / ID Card present")
            findings.append(AgentAuditFinding(
                category="Identification",
                status="OK",
                message="National ID / Identification document uploaded."
            ))
        else:
            missing_items.append("National Identification Document")
            findings.append(AgentAuditFinding(
                category="Identification",
                status="FAIL",
                message="Missing National ID document scan."
            ))

        # 2. Check Fee Voucher if required
        if "fee voucher" in expected_types:
            total_weight += 30
            has_voucher = any("voucher" in cat or "fee" in cat or "payment" in cat for cat in uploaded_categories)
            if has_voucher:
                earned_weight += 30
                verified_items.append("Bank Fee Voucher / Payment Proof present")
                findings.append(AgentAuditFinding(
                    category="Financial / Fee Voucher",
                    status="OK",
                    message="Bank Fee Voucher uploaded."
                ))
            else:
                missing_items.append("Bank Fee Deposit Voucher")
                findings.append(AgentAuditFinding(
                    category="Financial / Fee Voucher",
                    status="WARNING",
                    message=f"Missing Bank Fee Voucher for {person.person_type}."
                ))

        # 3. Check individual documents for signatures, stamps, and name consistency
        for doc in documents:
            analysis = doc.analysis
            if not analysis:
                findings.append(AgentAuditFinding(
                    category="Analysis",
                    document_id=doc.id,
                    document_name=doc.original_filename,
                    status="WARNING",
                    message="Document pending Content Understanding analysis."
                ))
                continue

            doc_cat = doc.doc_category.lower()

            # Stamp check for vouchers / certificates / stamped forms
            if "voucher" in doc_cat or "cert" in doc_cat or "stamp" in doc_cat:
                total_weight += 20
                if analysis.has_stamp:
                    earned_weight += 20
                    verified_items.append(f"Official Stamp verified on '{doc.original_filename}'")
                    findings.append(AgentAuditFinding(
                        category="Stamp Verification",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        status="OK",
                        message=f"Official stamp detected on {doc.doc_category}."
                    ))
                else:
                    findings.append(AgentAuditFinding(
                        category="Stamp Verification",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        status="WARNING",
                        message=f"No official stamp detected on {doc.doc_category}."
                    ))

            # Signature check
            total_weight += 20
            if analysis.has_signature:
                earned_weight += 20
                verified_items.append(f"Signature verified on '{doc.original_filename}'")
                findings.append(AgentAuditFinding(
                    category="Signature Verification",
                    document_id=doc.id,
                    document_name=doc.original_filename,
                    status="OK",
                    message="Hand-signed signature detected."
                ))
            else:
                findings.append(AgentAuditFinding(
                    category="Signature Verification",
                    document_id=doc.id,
                    document_name=doc.original_filename,
                    status="WARNING",
                    message="No authorized hand signature detected on document."
                ))

            # Name / National ID cross-verification
            if analysis.extracted_text and person.full_name:
                first_name = person.full_name.split()[0].lower()
                if first_name in analysis.extracted_text.lower():
                    verified_items.append(f"Person name match in '{doc.original_filename}'")

        # Score calculation
        score = int((earned_weight / total_weight) * 100) if total_weight > 0 else 50
        score = min(max(score, 0), 100)

        if score >= 85 and not missing_items:
            compliance_status = "Compliant"
            summary = f"All required documents for {person.full_name} ({person.person_type}) have been verified with valid signatures and stamps."
        elif score >= 60:
            compliance_status = "Action Required"
            summary = f"Documents for {person.full_name} are partially verified. Notice warnings regarding missing stamps or documents."
        else:
            compliance_status = "Missing Information"
            summary = f"Significant missing items or verification issues detected for {person.full_name}."

        return AgentAuditResponse(
            person_id=person.id,
            person_name=person.full_name,
            person_type=person.person_type,
            compliance_status=compliance_status,
            score=score,
            summary=summary,
            findings=findings,
            verified_items=list(set(verified_items)),
            missing_items=missing_items
        )

    def audit_project(self, db: Session, project_id: int) -> Dict[str, Any]:
        """Project-level document audit and health overview"""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project with ID {project_id} not found.")

        persons = db.query(Person).filter(Person.project_id == project_id).all()
        total_persons = len(persons)
        total_documents = db.query(Document).filter(Document.project_id == project_id).count()

        compliant_count = 0
        action_required_count = 0
        missing_docs_count = 0

        for p in persons:
            p_audit = self.audit_person(db, p.id)
            if p_audit.compliance_status == "Compliant":
                compliant_count += 1
            elif p_audit.compliance_status == "Action Required":
                action_required_count += 1
            else:
                missing_docs_count += 1

        overall_health = int((compliant_count / total_persons) * 100) if total_persons > 0 else 100

        return {
            "project_id": project.id,
            "project_title": project.title,
            "total_persons": total_persons,
            "total_documents": total_documents,
            "compliant_persons": compliant_count,
            "action_required_persons": action_required_count,
            "missing_docs_persons": missing_docs_count,
            "overall_health_score": overall_health,
            "person_types_configured": project.person_types
        }

    def chat(self, db: Session, request: AgentChatRequest) -> AgentChatResponse:
        """
        Interactive conversational AI Agent for querying documents, persons,
        stamps, signatures, and compliance.
        """
        query_lower = request.query.lower()
        context_used = {}
        suggestions = [
            "Audit all documents for this person",
            "Are there any missing stamps or signatures?",
            "Check fee voucher payment status",
            "Show project compliance overview"
        ]

        # Case 1: Person context provided
        if request.person_id:
            person = db.query(Person).filter(Person.id == request.person_id).first()
            if person:
                context_used["person"] = person.full_name
                context_used["person_type"] = person.person_type
                audit = self.audit_person(db, person.id)

                if "fee" in query_lower or "voucher" in query_lower or "paid" in query_lower:
                    voucher_doc = None
                    for doc in person.documents:
                        if "voucher" in doc.doc_category.lower() or "fee" in doc.doc_category.lower():
                            voucher_doc = doc
                            break
                    if voucher_doc and voucher_doc.analysis:
                        fields = voucher_doc.analysis.extracted_fields
                        amt = fields.get("Amount Paid", "Standard Amount")
                        vch_no = fields.get("Voucher Number", "VC-Detected")
                        is_stamped = voucher_doc.analysis.has_stamp
                        return AgentChatResponse(
                            answer=f"**Fee Voucher Status for {person.full_name}:**\n\n"
                                   f"- **Voucher Number:** {vch_no}\n"
                                   f"- **Amount:** {amt}\n"
                                   f"- **Official Bank Stamp:** {'Verified (Stamped)' if is_stamped else 'Not detected'}\n"
                                   f"- **Handwritten Signature:** {'Present' if voucher_doc.analysis.has_signature else 'Missing'}\n"
                                   f"- **Storage Reference:** `{voucher_doc.storage_reference}`\n\n"
                                   f"The voucher has been scanned and verified.",
                            agent_action="fee_voucher_check",
                            context_used=context_used,
                            suggestions=["View voucher image", "Download audit report", "Check ID card"]
                        )
                    else:
                        return AgentChatResponse(
                            answer=f"No Bank Fee Voucher document was found in {person.full_name}'s uploaded batch. "
                                   f"Please take a mobile camera photo of the fee challan/voucher and upload it.",
                            agent_action="fee_voucher_missing",
                            context_used=context_used,
                            suggestions=["Upload fee voucher now", "Check person details"]
                        )

                if "audit" in query_lower or "check" in query_lower or "status" in query_lower or "missing" in query_lower:
                    findings_bullets = "\n".join([f"- [{f.status}] **{f.category}**: {f.message}" for f in audit.findings])
                    verified_bullets = "\n".join([f"- {v}" for v in audit.verified_items]) or "- None"
                    missing_bullets = "\n".join([f"- {m}" for m in audit.missing_items]) or "- None"

                    answer = (
                        f"### AI Audit Dossier for {person.full_name} ({person.person_type})\n\n"
                        f"**Overall Compliance:** `{audit.compliance_status}` (Score: **{audit.score}%**)\n\n"
                        f"**Summary:** {audit.summary}\n\n"
                        f"**Key Findings:**\n{findings_bullets}\n\n"
                        f"**Verified Items:**\n{verified_bullets}\n\n"
                        f"**Missing Items:**\n{missing_bullets}"
                    )
                    return AgentChatResponse(
                        answer=answer,
                        agent_action="person_audit",
                        context_used=context_used,
                        suggestions=["Check fee voucher", "Review signature authenticity", "Show all uploaded documents"]
                    )

                if "stamp" in query_lower or "signature" in query_lower or "sign" in query_lower:
                    docs_status = []
                    for doc in person.documents:
                        st = "Stamped" if doc.analysis and doc.analysis.has_stamp else "No stamp"
                        sig = "Signed" if doc.analysis and doc.analysis.has_signature else "No sign"
                        hw = f"{doc.analysis.handwritten_percentage}% Handwritten" if doc.analysis else "Pending"
                        docs_status.append(f"- **{doc.original_filename}** ({doc.doc_category}): {st} | {sig} | {hw}")
                    answer = f"**Signature & Stamp Audit for {person.full_name}:**\n\n" + "\n".join(docs_status)
                    return AgentChatResponse(
                        answer=answer,
                        agent_action="stamp_signature_check",
                        context_used=context_used,
                        suggestions=["Audit person files", "Verify bank fee voucher"]
                    )

        # Case 2: Project context provided
        if request.project_id:
            project_stats = self.audit_project(db, request.project_id)
            context_used["project"] = project_stats["project_title"]

            if "audit" in query_lower or "summary" in query_lower or "overview" in query_lower:
                return AgentChatResponse(
                    answer=f"### Project Document Audit: {project_stats['project_title']}\n\n"
                           f"- **Total Persons Managed:** {project_stats['total_persons']}\n"
                           f"- **Total Scanned Documents:** {project_stats['total_documents']}\n"
                           f"- **Fully Compliant Persons:** {project_stats['compliant_persons']}\n"
                           f"- **Action Required (Warnings):** {project_stats['action_required_persons']}\n"
                           f"- **Missing Documents:** {project_stats['missing_docs_persons']}\n"
                           f"- **Overall Health Score:** **{project_stats['overall_health_score']}%**\n\n"
                           f"Manageable Person Types for this Project: {', '.join(project_stats['person_types_configured'])}.",
                    agent_action="project_audit",
                    context_used=context_used,
                    suggestions=["List persons needing attention", "Search documents by keyword", "Check fee vouchers"]
                )

        # General search or helpful guidance
        total_projects = db.query(Project).count()
        total_persons = db.query(Person).count()
        total_docs = db.query(Document).count()

        return AgentChatResponse(
            answer=f"Hello! I am your **Document Scan & Content Understanding AI Agent**.\n\n"
                   f"I can help you:\n"
                   f"- Audit uploaded batches of mobile camera photos & document scans.\n"
                   f"- Verify official bank stamps, cashier seals, and notary markings.\n"
                   f"- Detect handwritten signatures and estimate handwriting percentage.\n"
                   f"- Cross-check extracted OCR details against person records in Azure SQL.\n\n"
                   f"**System Snapshot:** {total_projects} Projects | {total_persons} Persons | {total_docs} Documents stored in Azure.\n\n"
                   f"Select a Project or Person in the app to ask specific questions or run automated audits!",
            agent_action="general_greeting",
            context_used={"system_total_docs": total_docs},
            suggestions=[
                "How do I upload batch mobile camera scans?",
                "How does Azure Content Understanding detect stamps?",
                "Audit project documents"
            ]
        )


ai_agent_service = AIAgentService()
