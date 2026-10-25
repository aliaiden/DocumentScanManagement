# DocuScan AI - Document Scan & Verification AI Agent Web App

An intelligent AI Agent web application for managing document-intensive projects, persons, and batch picture uploads of scanned documents (handwritten or printed, hand-signed, stamped, fee vouchers, certificates, ID documents, and mobile phone camera photos).

Built with **FastAPI**, **Azure SQL Server**, **Azure Account Storage Service (Blob Storage)**, and **Azure Content Understanding / Document Intelligence**, complete with an embedded conversational verification agent.

---

## 🌟 Key Features

### 1. Projects Management (CRUD)
- **Create, Read, Edit, and Delete Projects**:
  - Each project has a **Title**, **Description**, and custom **Types of People** it manages (e.g. *Student*, *Applicant*, *Employee*, *Doctor*, *Vendor*, *Patient*).
  - Configurable person categories define the forms and verification rules per project.
  - Cascade deletion cleans up associated person records, database references, and Azure storage blobs.

### 2. Person Registration with Batch Document Pictures / Scans
- **Combined Registration Form**:
  - Person basic info: Full Name, National ID / CNIC / Passport, Email, Phone, Date of Birth, Address, and Notes.
  - **Batch Scanned Documents Uploader**:
    - Direct **Mobile Phone Camera Capture** support (`capture="environment"` attribute opens the native mobile camera instantly on smartphones).
    - Multi-file drag-and-drop or gallery browse.
    - Automatic classification tagging (Fee Voucher, ID Document, Certificate, Handwritten Note, Stamped Form, Receipt, Other).
    - Staged preview thumbnails with category selection and file sizes.

### 3. Azure Account Storage Service (Blob Storage)
- Securely uploads batch pictures/scans to an Azure Blob container (`scanned-documents`).
- Generates and stores **storage references** in the database.
- Streams and fetches saved batch images on demand with high-resolution viewing.
- Automatic fallback to local disk storage (`storage_local/`) when developing offline or before Azure credentials are provided.

### 4. Azure Content Understanding & Document Intelligence
- Analyzes each uploaded picture or mobile camera scan:
  - **Signature Detection**: Identifies whether the document is signed or unsigned.
  - **Official Stamp & Seal Detection**: Detects official bank stamps, cashier stamps, and notary seals.
  - **Handwritten vs Printed Analysis**: Computes the percentage of handwriting (e.g., 85% handwritten letter vs printed voucher).
  - **Structured Key-Value Extraction**: Extracts field pairs (e.g. Voucher Number, Amount Paid, Bank Branch, Attestation Status, National ID, Issue Date).
  - **Full OCR Stream**: Clean extracted text with one-click copy.
  - **90° Image Rotation**: Easily rotate phone photos taken in landscape or upside down.
  - Built-in intelligent heuristic engine provides instant realistic analysis when Azure keys are being provisioned.

### 5. Azure SQL Server Database
- Relational schema with foreign keys, indexes, and cascade integrity:
  - `projects`: Title, description, allowed person types, timestamps.
  - `persons`: Profile metadata, project association, contact details.
  - `documents`: File metadata, original filename, category, Azure blob name, and **storage reference**.
  - `document_analyses`: Azure Content Understanding extraction results, stamps, signatures, and OCR text.
  - `agent_audit_logs`: Audit trail and compliance findings.
- Standalone DDL script provided in `database_schema_azuresql.sql`.
- Transparent fallback to SQLite for local development when Azure SQL Server is unconfigured or unreachable.

### 6. Embedded AI Agent Assistant
- Floating slide-over assistant drawer in the web app:
  - **Dossier Audit**: Audits a person's documents against expected types for their role, verifies stamps & signatures, and flags missing files.
  - **Cross-check Verification**: Cross-references names and ID numbers from OCR text with form records in Azure SQL.
  - **Conversational Q&A**: Ask natural language questions like:
    - *"Did Sarah Jenkins pay her fee voucher?"*
    - *"Are there any missing stamps or signatures in this project?"*
    - *"Show project compliance score"*

---

## 🔒 Security & Sensitive Values Management

All database credentials, endpoints, keys, and connection strings are **strictly kept out of git tracking**:
- `.gitignore` explicitly excludes `.env`, `storage_local/`, `app_data.db`, and all secret configuration files.
- `.env.example` is provided with clean placeholder templates and guidance.
- System status APIs and UI modals mask sensitive keys (e.g., `DefaultEndpoints...==` displays as `Defa...ey==`).

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- (Optional) Azure Subscription for Azure SQL, Blob Storage, and Content Understanding.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd DocumentScanManagement

# Optional: Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the `.env.example` template to `.env`:
```bash
cp .env.example .env
```
Fill in your Azure credentials in `.env` (or leave as defaults to run in local development mode):
```env
# Azure SQL Server
AZURE_SQL_SERVER=your-azure-sql.database.windows.net
AZURE_SQL_DATABASE=docscan_db
AZURE_SQL_USER=sqladmin
AZURE_SQL_PASSWORD=YourSecurePassword123!

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=yourstorage;AccountKey=yourkey==;EndpointSuffix=core.windows.net
AZURE_STORAGE_CONTAINER_NAME=scanned-documents

# Azure Content Understanding / Document Intelligence
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CONTENT_UNDERSTANDING_KEY=your_key_here
```

### 4. Run the Web Application
```bash
python3 run.py
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## ☁️ Azure Cloud Services Setup

### A. Azure SQL Server
1. Create an **Azure SQL Database** in the Azure Portal.
2. In **Networking**, ensure "Allow Azure services and resources to access this server" is enabled, and add your client IP address to the firewall rules.
3. (Optional) Run `database_schema_azuresql.sql` in Azure Query Editor or Azure Data Studio to pre-create tables with custom indexes.

### B. Azure Account Storage (Blob)
1. Create a **Storage Account** (Standard General-purpose v2).
2. Create a container named `scanned-documents` with Blob access level.
3. Under **Access keys**, copy the Connection String and set `AZURE_STORAGE_CONNECTION_STRING` in `.env`.

### C. Azure Content Understanding / Document Intelligence
1. Create an **Azure AI Document Intelligence** or **Azure AI Content Understanding** resource.
2. Under **Keys and Endpoint**, copy the Endpoint URL and Key 1 into `AZURE_CONTENT_UNDERSTANDING_ENDPOINT` and `AZURE_CONTENT_UNDERSTANDING_KEY`.

---

## 🧪 Running Automated Tests

Run the test suite with Python's built-in `unittest`:
```bash
python3 -m unittest discover tests
```
All CRUD operations, multipart batch document uploads, Azure storage references, and AI agent endpoints are tested automatically.

---

## 📁 Project Architecture

```
DocumentScanManagement/
├── .gitignore                          # Excludes .env, local storage, DB, caches
├── .env.example                        # Template for Azure credentials
├── database_schema_azuresql.sql        # Azure SQL Server T-SQL DDL script
├── requirements.txt                    # Python dependencies
├── run.py                              # Web application launcher
│
├── backend/
│   ├── config.py                       # Safe settings loader with secret masking
│   ├── database.py                     # Azure SQL & SQLite connection manager
│   ├── models.py                       # SQLAlchemy models (Project, Person, Document, Analysis)
│   ├── schemas.py                      # Pydantic schemas for serialization
│   ├── main.py                         # FastAPI application entrypoint & static mount
│   │
│   ├── services/
│   │   ├── storage_service.py          # Azure Blob Storage client + local fallback
│   │   ├── content_understanding_service.py # Azure Content Understanding & OCR engine
│   │   └── ai_agent_service.py         # AI Agent reasoning, audits & conversational Q&A
│   │
│   └── routers/
│       ├── projects.py                 # Project CRUD endpoints
│       ├── persons.py                  # Person + batch scan uploader endpoints
│       ├── documents.py                # Batch image streaming, re-analysis & deletion
│       ├── agent.py                    # AI chat and audit endpoints
│       └── system.py                   # Cloud status & connectivity healthcheck
│
├── frontend/
│   ├── index.html                      # Single-page modern UI with camera capture
│   └── static/
│       ├── css/style.css               # Custom responsive styles & animations
│       └── js/app.js                   # Client state, modals, batch uploader, AI drawer
│
└── tests/
    └── test_api.py                     # Full end-to-end automated test suite
```
