"""
AI Agent Router
Endpoints for conversational document Q&A, dossier compliance audits,
and project health analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import AgentChatRequest, AgentChatResponse, AgentAuditResponse
from backend.services.ai_agent_service import ai_agent_service

router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


@router.post("/chat", response_model=AgentChatResponse)
def chat_with_agent(payload: AgentChatRequest, db: Session = Depends(get_db)):
    """Chat with the AI Agent about projects, persons, and document scans"""
    try:
        return ai_agent_service.chat(db, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@router.get("/audit/person/{person_id}", response_model=AgentAuditResponse)
def audit_person_documents(person_id: int, db: Session = Depends(get_db)):
    """Run comprehensive AI audit on a person's scanned documents"""
    try:
        return ai_agent_service.audit_person(db, person_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}")


@router.get("/audit/project/{project_id}")
def audit_project_documents(project_id: int, db: Session = Depends(get_db)):
    """Run health check and compliance audit on an entire project"""
    try:
        return ai_agent_service.audit_project(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Project audit failed: {e}")
