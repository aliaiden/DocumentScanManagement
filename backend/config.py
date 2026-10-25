"""
Application Configuration Module
Reads configuration from environment and .env file safely.
Keeps sensitive credentials out of git and masks them in status outputs.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


class Settings:
    BASE_DIR: Path = BASE_DIR

    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-in-production")

    # 1. Azure SQL Server Configuration
    AZURE_SQL_SERVER: Optional[str] = os.getenv("AZURE_SQL_SERVER", "ai103server.database.windows.net")
    AZURE_SQL_DATABASE: Optional[str] = os.getenv("AZURE_SQL_DATABASE", "AI103")
    AZURE_SQL_USER: Optional[str] = os.getenv("AZURE_SQL_USER")
    AZURE_SQL_PASSWORD: Optional[str] = os.getenv("AZURE_SQL_PASSWORD")
    AZURE_SQL_PORT: int = int(os.getenv("AZURE_SQL_PORT", "1433"))
    AZURE_SQL_CONNECTION_STRING: Optional[str] = os.getenv("AZURE_SQL_CONNECTION_STRING")
    FALLBACK_TO_LOCAL_SQLITE: bool = os.getenv("FALLBACK_TO_LOCAL_SQLITE", "True").lower() in ("true", "1", "yes")

    # 2. Azure Account Storage Service (Blob Storage)
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    AZURE_STORAGE_CONTAINER_NAME: str = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "scanned-documents")
    FALLBACK_TO_LOCAL_STORAGE: bool = os.getenv("FALLBACK_TO_LOCAL_STORAGE", "True").lower() in ("true", "1", "yes")
    LOCAL_STORAGE_DIR: Path = BASE_DIR / "storage_local"

    # 3. Azure Content Understanding Service
    AZURE_CONTENT_UNDERSTANDING_ENDPOINT: str = os.getenv(
        "AZURE_CONTENT_UNDERSTANDING_ENDPOINT",
        "https://honan121314-1405-resource.services.ai.azure.com/"
    )
    AZURE_CONTENT_UNDERSTANDING_KEY: Optional[str] = os.getenv("AZURE_CONTENT_UNDERSTANDING_KEY")
    AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID: str = os.getenv(
        "AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID",
        "invoice_analyzer"
    )
    AZURE_CONTENT_UNDERSTANDING_API_VERSION: str = os.getenv(
        "AZURE_CONTENT_UNDERSTANDING_API_VERSION",
        "2025-11-01"
    )

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: Optional[str] = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    AZURE_DOCUMENT_INTELLIGENCE_KEY: Optional[str] = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    MOCK_ANALYZER_WHEN_UNCONFIGURED: bool = os.getenv("MOCK_ANALYZER_WHEN_UNCONFIGURED", "True").lower() in ("true", "1", "yes")

    # 4. Optional AI LLM Configuration
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

    @classmethod
    def is_azure_sql_configured(cls) -> bool:
        if cls.AZURE_SQL_CONNECTION_STRING:
            return True
        return bool(cls.AZURE_SQL_SERVER and cls.AZURE_SQL_DATABASE and cls.AZURE_SQL_USER and cls.AZURE_SQL_PASSWORD)

    @classmethod
    def is_azure_storage_configured(cls) -> bool:
        if cls.AZURE_STORAGE_CONNECTION_STRING:
            return True
        return bool(cls.AZURE_STORAGE_ACCOUNT_NAME and cls.AZURE_STORAGE_ACCOUNT_KEY)

    @classmethod
    def is_azure_content_understanding_configured(cls) -> bool:
        if cls.AZURE_CONTENT_UNDERSTANDING_ENDPOINT:
            if cls.AZURE_CONTENT_UNDERSTANDING_KEY and not cls.AZURE_CONTENT_UNDERSTANDING_KEY.startswith("{{"):
                return True
            # Even without a key, DefaultAzureCredential is supported
            return True
        if cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and cls.AZURE_DOCUMENT_INTELLIGENCE_KEY:
            return True
        return False

    @staticmethod
    def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
        if not secret:
            return "Not Configured"
        if len(secret) <= visible_chars * 2:
            return "******"
        return f"{secret[:visible_chars]}...{secret[-visible_chars:]}"


settings = Settings()
