"""
FastAPI Main Application Entrypoint
Serves REST API, AI Agent, and Modern Responsive Frontend.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db, SessionLocal
from backend.models import Project, Person, Document, DocumentAnalysis
from backend.routers import (
    projects_router,
    persons_router,
    documents_router,
    agent_router,
    system_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("document_scan_app")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def seed_demo_data_if_empty():
    """Seed initial demo project & records if database is empty for an instant preview"""
    db = SessionLocal()
    try:
        if db.query(Project).count() == 0:
            logger.info("Seeding initial demo project and documents...")
            project = Project(
                title="University Admissions & Student Verification 2026",
                description="Manages scanned admission applications, bank fee vouchers, CNIC/ID cards, and educational certificates for applicants and registered students."
            )
            project.person_types = ["Applicant", "Student", "Faculty", "Scholarship Candidate"]
            db.add(project)
            db.commit()
            db.refresh(project)

            # Sample Person 1: Student with Fee Voucher & ID
            p1 = Person(
                project_id=project.id,
                person_type="Student",
                full_name="Sarah Jenkins",
                national_id="42201-9876543-2",
                email="sarah.jenkins@admissions.edu",
                phone="+1 (555) 234-8901",
                date_of_birth="2002-09-14",
                address="742 Evergreen Terrace, Sector 4",
                notes="Candidate for Master of Science program. Submitted fee voucher and ID card."
            )
            db.add(p1)
            db.commit()
            db.refresh(p1)

            # Add sample document records for Sarah
            d1 = Document(
                person_id=p1.id,
                project_id=project.id,
                original_filename="bank_fee_deposit_challan.jpg",
                content_type="image/jpeg",
                file_size=425800,
                doc_category="Fee Voucher",
                storage_reference=f"https://{settings.AZURE_STORAGE_CONTAINER_NAME}.blob.core.windows.net/person_{p1.id}/bank_fee_deposit_challan.jpg",
                blob_name=f"person_{p1.id}/bank_fee_deposit_challan.jpg",
                storage_container=settings.AZURE_STORAGE_CONTAINER_NAME
            )
            db.add(d1)
            db.commit()
            db.refresh(d1)

            da1 = DocumentAnalysis(
                document_id=d1.id,
                status="completed",
                has_signature=True,
                has_stamp=True,
                is_handwritten=True,
                handwritten_percentage=38.5,
                detected_type="Bank Fee Deposit Voucher",
                confidence_score=0.97,
                extracted_text="BANK FEE CHALLAN / VOUCHER\nVoucher No: VCH-849102\nDepositor: Sarah Jenkins\nAmount: $450.00\nBank: National Campus Branch\n[OFFICIAL BANK CASHIER STAMP: PAID & VERIFIED]\n[CASHIER SIGNATURE: Present]"
            )
            da1.extracted_fields = {
                "Voucher Number": "VCH-849102",
                "Depositor Name": "Sarah Jenkins",
                "Amount Paid": "$450.00",
                "Deposit Date": "2026-10-18",
                "Bank Branch": "National Campus Branch (Code: 042)",
                "Official Bank Stamp": "VERIFIED & STAMPED",
                "Authorized Signature": "Present (Signed by Cashier)"
            }
            db.add(da1)

            d2 = Document(
                person_id=p1.id,
                project_id=project.id,
                original_filename="national_identity_card_front.jpg",
                content_type="image/jpeg",
                file_size=312400,
                doc_category="ID Document",
                storage_reference=f"https://{settings.AZURE_STORAGE_CONTAINER_NAME}.blob.core.windows.net/person_{p1.id}/national_identity_card_front.jpg",
                blob_name=f"person_{p1.id}/national_identity_card_front.jpg",
                storage_container=settings.AZURE_STORAGE_CONTAINER_NAME
            )
            db.add(d2)
            db.commit()
            db.refresh(d2)

            da2 = DocumentAnalysis(
                document_id=d2.id,
                status="completed",
                has_signature=True,
                has_stamp=True,
                is_handwritten=False,
                handwritten_percentage=4.0,
                detected_type="National Identification Document",
                confidence_score=0.98,
                extracted_text="IDENTITY DOCUMENT\nName: Sarah Jenkins\nNational ID: 42201-9876543-2\nDOB: 2002-09-14\n[DIGITAL CHIP & EMBOSSED LOGO DETECTED]"
            )
            da2.extracted_fields = {
                "Document Name": "National Identity Card",
                "Full Name": "Sarah Jenkins",
                "National ID Number": "42201-9876543-2",
                "Date of Birth": "2002-09-14",
                "Cardholder Signature": "Present"
            }
            db.add(da2)

            # Sample Person 2: Employee / Applicant
            p2 = Person(
                project_id=project.id,
                person_type="Applicant",
                full_name="David Miller",
                national_id="35202-1122334-5",
                email="david.miller@example.org",
                phone="+1 (555) 456-7890",
                date_of_birth="1999-11-22",
                address="108 Oak Lane, Apt 3B",
                notes="Initial application submitted. Pending fee voucher payment proof."
            )
            db.add(p2)
            db.commit()
            db.refresh(p2)

            d3 = Document(
                person_id=p2.id,
                project_id=project.id,
                original_filename="handwritten_cover_request.jpg",
                content_type="image/jpeg",
                file_size=520100,
                doc_category="Handwritten Note",
                storage_reference=f"https://{settings.AZURE_STORAGE_CONTAINER_NAME}.blob.core.windows.net/person_{p2.id}/handwritten_cover_request.jpg",
                blob_name=f"person_{p2.id}/handwritten_cover_request.jpg",
                storage_container=settings.AZURE_STORAGE_CONTAINER_NAME
            )
            db.add(d3)
            db.commit()
            db.refresh(d3)

            da3 = DocumentAnalysis(
                document_id=d3.id,
                status="completed",
                has_signature=True,
                has_stamp=False,
                is_handwritten=True,
                handwritten_percentage=92.0,
                detected_type="Handwritten Application / Letter",
                confidence_score=0.94,
                extracted_text="Dear Admissions Board,\nI am submitting my preliminary documents and request consideration for enrollment.\nSincerely, David Miller\n[HANDWRITTEN SIGNATURE]"
            )
            da3.extracted_fields = {
                "Document Type": "Handwritten Request Letter",
                "Applicant Name": "David Miller",
                "Handwriting Ratio": "92%",
                "Signature Detected": "Present at bottom"
            }
            db.add(da3)

            db.commit()
            logger.info("Demo project and documents seeded successfully.")
    except Exception as e:
        logger.warning(f"Error seeding demo data: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed demo data if appropriate
    init_db()
    seed_demo_data_if_empty()
    logger.info("Document Scan Management Service is UP and running.")
    yield
    # Shutdown
    logger.info("Document Scan Management Service is shutting down.")


app = FastAPI(
    title="Document Scan & Management AI Agent",
    description="AI Agent Web Application for Projects, Persons, Mobile Camera Document Scans, Azure Storage & Azure Content Understanding.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(projects_router)
app.include_router(persons_router)
app.include_router(documents_router)
app.include_router(agent_router)
app.include_router(system_router)

# Mount Static Assets
static_dir = FRONTEND_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the single-page web app"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Document Scan Management App - Frontend building...</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
