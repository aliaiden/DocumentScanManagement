# DocuScan AI — Document Scan Management

An AI-powered web application that organizes document scanning by project. Upload batches of scanned documents (mobile camera photos, fee vouchers, certificates, handwritten notes, ID cards, stamped forms) and **Azure Content Understanding automatically extracts person identity details** — name, national ID, date of birth, address, phone — directly from the document images. No manual person-info form is required. All data is persisted in **Azure SQL Server** and images are stored in **Azure Blob Storage**.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **ORM / Database** | SQLAlchemy 2, Azure SQL Server (MSSQL via pyodbc / pymssql) |
| **AI / Document Analysis** | Azure Content Understanding REST API (2025-11-01) |
| **Cloud Storage** | Azure Account Storage Service (Blob Storage) |
| **Frontend** | Vanilla JS, Tailwind CSS (CDN), Lucide Icons |
| **API Standard** | OpenAPI v3 (auto-generated Swagger UI at `/docs`) |
| **Configuration** | python-dotenv, `.env` file (git-ignored) |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/aliaiden/DocumentScanManagement.git
cd DocumentScanManagement
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
# Azure SQL Server
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=YourDatabase
AZURE_SQL_USER=your_sql_user
AZURE_SQL_PASSWORD=your_sql_password

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=documents

# Azure Content Understanding
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_CONTENT_UNDERSTANDING_KEY=your_api_key
AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID=invoice_analyzer
AZURE_CONTENT_UNDERSTANDING_API_VERSION=2025-11-01
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** MSSQL connectivity requires the ODBC Driver for SQL Server. On macOS: `brew install msodbcsql18`

### 4. Run the application

```bash
python3 run.py
```

The app starts at **http://localhost:8000**

- **Web UI** → http://localhost:8000
- **Swagger UI (OpenAPI v3)** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc

---

## API Endpoints

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/projects` | List all projects |
| `POST` | `/api/projects` | Create a new project |
| `GET` | `/api/projects/{id}` | Get project with persons |
| `PUT` | `/api/projects/{id}` | Update project |
| `DELETE` | `/api/projects/{id}` | Delete project and all data |

### Persons & Document Scanning

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects/{id}/scan` | **Upload scans → auto-extract person via Azure AI** |
| `POST` | `/api/projects/{id}/persons` | Same as `/scan` (backward-compat alias) |
| `GET` | `/api/projects/{id}/persons` | List persons in project |
| `GET` | `/api/persons/{id}` | Get person dossier with all scans |
| `PUT` | `/api/persons/{id}` | Update person details |
| `DELETE` | `/api/persons/{id}` | Delete person and all scans |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/batch/{person_id}` | Upload additional scans to existing person |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `GET` | `/api/documents/{id}/file` | Stream document image from Azure Storage |
| `POST` | `/api/documents/{id}/reanalyze` | Re-analyze with Azure Content Understanding |
| `DELETE` | `/api/documents/{id}` | Delete document from SQL and Azure Storage |

### Azure Content Understanding (OpenAPI v3 — for external integrations)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/content-understanding/analyze` | Analyze a document file or URL; returns extracted person details, OCR text, stamps, signatures |
| `GET` | `/api/content-understanding/info` | Returns active analyzer endpoint, ID, API version, and supported analyzers |

#### `POST /api/content-understanding/analyze`

**Request** (multipart/form-data):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | One of | Document image (JPEG, PNG, PDF) |
| `file_url` | string | One of | Public URL to a document image |
| `analyzer_id` | string | No | Override analyzer (default: `invoice_analyzer`) |
| `category` | string | No | Category hint (e.g. `ID Document`, `Fee Voucher`) |

**Response** (`application/json`):

```json
{
  "status": "completed",
  "detected_type": "National Identification Document",
  "has_signature": true,
  "has_stamp": false,
  "is_handwritten": false,
  "handwritten_percentage": 3.5,
  "confidence_score": 0.97,
  "extracted_text": "IDENTITY DOCUMENT\nName: Sarah Jenkins\nNational ID: 42201-...",
  "extracted_fields": {
    "Full Name": "Sarah Jenkins",
    "National ID Number": "42201-9876543-2",
    "Date of Birth": "2002-09-14"
  },
  "extracted_person": {
    "full_name": "Sarah Jenkins",
    "national_id": "42201-9876543-2",
    "person_type": "Applicant",
    "date_of_birth": "2002-09-14",
    "email": null,
    "phone": null,
    "address": null,
    "confidence": 0.97
  },
  "analysis_raw": {}
}
```

#### `GET /api/content-understanding/info`

**Response**:

```json
{
  "endpoint": "https://honan121314-1405-resource.services.ai.azure.com/",
  "analyzer_id": "invoice_analyzer",
  "api_version": "2025-11-01",
  "supported_analyzers": [
    "invoice_analyzer",
    "prebuilt-layout",
    "prebuilt-idDocument",
    "prebuilt-receipt",
    "prebuilt-document"
  ],
  "key_configured": true
}
```

### AI Agent

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/agent/chat` | Chat with the AI document audit agent |
| `GET` | `/api/agent/audit/person/{id}` | AI compliance audit for a person |
| `GET` | `/api/agent/audit/project/{id}` | AI health audit for a project |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/system/status` | Azure cloud connectivity status (SQL, Storage, Content Understanding) |
| `GET` | `/api/system/health` | Basic health check |
