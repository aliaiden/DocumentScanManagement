#!/usr/bin/env python3
"""
Launcher script for Document Scan Management AI Agent Web Application.
Usage:
    python3 run.py
"""

import sys
import uvicorn
from backend.config import settings

if __name__ == "__main__":
    print("=" * 70)
    print("  🚀 Starting Document Scan & Management AI Agent Web App")
    print(f"  🌐 Listening on http://localhost:{settings.PORT}")
    print(f"  ☁️  Database Mode: {settings.AZURE_SQL_SERVER or 'Local Dev (SQLite)'}")
    print(f"  📦 Storage Mode: {settings.AZURE_STORAGE_CONTAINER_NAME} (Azure Blob / Local)")
    print(f"  🧠 AI Vision: Azure Content Understanding / Intelligent Analyzer")
    print("=" * 70)
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
