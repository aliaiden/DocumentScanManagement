"""
System Status Router
Reports connection and health status of Azure SQL Server, Azure Storage Account,
and Azure Content Understanding Service.
"""

from fastapi import APIRouter
from backend.database import get_db_status
from backend.services.storage_service import storage_service
from backend.services.content_understanding_service import content_understanding_service
from backend.services.ai_agent_service import ai_agent_service
from backend.schemas import SystemStatusOut, ServiceStatus

router = APIRouter(prefix="/api/system", tags=["System Status"])


@router.get("/status", response_model=SystemStatusOut)
def get_system_status():
    """Returns connectivity and configuration status for all cloud services"""
    db_stat = get_db_status()
    db_service = ServiceStatus(
        name="Azure SQL Server",
        connected=db_stat["is_azure"],
        status_text=f"Connected ({db_stat['active_type']})",
        provider=db_stat["active_type"],
        details={
            "server": db_stat["server"],
            "database": db_stat["database"],
            "configured_in_env": db_stat["configured_in_env"],
            "error": db_stat["error"]
        }
    )

    storage_stat = storage_service.get_status()
    storage_svc = ServiceStatus(
        name=storage_stat["name"],
        connected=storage_stat["connected"],
        status_text=storage_stat["status_text"],
        provider=storage_stat["provider"],
        details=storage_stat["details"]
    )

    cu_stat = content_understanding_service.get_status()
    cu_svc = ServiceStatus(
        name=cu_stat["name"],
        connected=cu_stat["connected"],
        status_text=cu_stat["status_text"],
        provider=cu_stat["provider"],
        details=cu_stat["details"]
    )

    agent_svc = ServiceStatus(
        name="AI Document Agent",
        connected=True,
        status_text="Operational & Ready",
        provider=ai_agent_service.provider_name,
        details={
            "llm_enabled": ai_agent_service.has_llm,
            "capabilities": ["Audit Dossier", "Stamp Verification", "Signature Verification", "Cross-check Form Data"]
        }
    )

    return SystemStatusOut(
        database=db_service,
        storage=storage_svc,
        content_understanding=cu_svc,
        ai_agent=agent_svc
    )
