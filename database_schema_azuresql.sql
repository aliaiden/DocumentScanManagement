-- ==============================================================================
-- Document Scan Management - Azure SQL Server Database Schema
-- Run this script in Azure SQL Server / Azure Data Studio / SSMS
-- ==============================================================================

-- 1. Create Projects Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'projects')
BEGIN
    CREATE TABLE projects (
        id INT IDENTITY(1,1) PRIMARY KEY,
        title NVARCHAR(255) NOT NULL,
        description NVARCHAR(MAX) NULL,
        person_types NVARCHAR(MAX) NOT NULL DEFAULT '["Applicant", "Employee", "Student", "Customer"]',
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX idx_projects_title ON projects(title);
    PRINT 'Table [projects] created successfully.';
END
GO

-- 2. Create Persons Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'persons')
BEGIN
    CREATE TABLE persons (
        id INT IDENTITY(1,1) PRIMARY KEY,
        project_id INT NOT NULL,
        person_type NVARCHAR(100) NOT NULL,
        full_name NVARCHAR(255) NOT NULL,
        national_id NVARCHAR(100) NULL,
        email NVARCHAR(255) NULL,
        phone NVARCHAR(100) NULL,
        date_of_birth NVARCHAR(100) NULL,
        address NVARCHAR(MAX) NULL,
        notes NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_persons_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    CREATE INDEX idx_persons_project_id ON persons(project_id);
    CREATE INDEX idx_persons_national_id ON persons(national_id);
    CREATE INDEX idx_persons_full_name ON persons(full_name);
    PRINT 'Table [persons] created successfully.';
END
GO

-- 3. Create Documents Table (Stores storage reference and Azure Blob metadata)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'documents')
BEGIN
    CREATE TABLE documents (
        id INT IDENTITY(1,1) PRIMARY KEY,
        person_id INT NOT NULL,
        project_id INT NOT NULL,
        original_filename NVARCHAR(255) NOT NULL,
        content_type NVARCHAR(100) NOT NULL,
        file_size BIGINT NOT NULL,
        doc_category NVARCHAR(100) NOT NULL DEFAULT 'Other', -- e.g. Fee Voucher, ID Document, Certificate, Handwritten Note, Stamped Form
        storage_reference NVARCHAR(1024) NOT NULL,          -- Full Azure Blob URI or Storage Path
        blob_name NVARCHAR(255) NOT NULL,                   -- Azure Blob name in container
        storage_container NVARCHAR(100) NOT NULL,           -- Azure Blob Container name
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_documents_person FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE,
        CONSTRAINT fk_documents_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE NO ACTION
    );
    CREATE INDEX idx_documents_person_id ON documents(person_id);
    CREATE INDEX idx_documents_project_id ON documents(project_id);
    CREATE INDEX idx_documents_blob_name ON documents(blob_name);
    CREATE INDEX idx_documents_doc_category ON documents(doc_category);
    PRINT 'Table [documents] created successfully.';
END
GO

-- 4. Create Document Analyses Table (Stores Azure Content Understanding Results)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'document_analyses')
BEGIN
    CREATE TABLE document_analyses (
        id INT IDENTITY(1,1) PRIMARY KEY,
        document_id INT NOT NULL UNIQUE,
        status NVARCHAR(50) NOT NULL DEFAULT 'pending',     -- pending, completed, failed
        has_signature BIT NOT NULL DEFAULT 0,               -- Hand-signed detection
        has_stamp BIT NOT NULL DEFAULT 0,                   -- Official Stamp detection
        is_handwritten BIT NOT NULL DEFAULT 0,              -- Handwritten vs Printed
        handwritten_percentage FLOAT NOT NULL DEFAULT 0.0,  -- 0.0 to 100.0%
        detected_type NVARCHAR(100) NULL,                   -- e.g. 'Fee Voucher', 'CNIC / National ID'
        confidence_score FLOAT NOT NULL DEFAULT 0.0,
        extracted_text NVARCHAR(MAX) NULL,                  -- Full OCR extracted text
        extracted_fields NVARCHAR(MAX) NULL,                -- JSON key-value pairs (voucher no, amount, etc.)
        analysis_raw NVARCHAR(MAX) NULL,                    -- Raw JSON from Azure Content Understanding
        analyzed_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_analyses_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    CREATE INDEX idx_analyses_document_id ON document_analyses(document_id);
    CREATE INDEX idx_analyses_status ON document_analyses(status);
    PRINT 'Table [document_analyses] created successfully.';
END
GO

-- 5. Create AI Agent Audit Logs Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'agent_audit_logs')
BEGIN
    CREATE TABLE agent_audit_logs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        project_id INT NULL,
        person_id INT NULL,
        audit_type NVARCHAR(100) NOT NULL, -- 'person_audit', 'project_audit', 'query'
        findings NVARCHAR(MAX) NOT NULL,
        compliance_status NVARCHAR(50) NOT NULL, -- 'Compliant', 'Issues Found', 'Missing Documents'
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT fk_audit_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
        CONSTRAINT fk_audit_person FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
    );
    CREATE INDEX idx_audit_person_id ON agent_audit_logs(person_id);
    PRINT 'Table [agent_audit_logs] created successfully.';
END
GO
