from backend.routers.projects import router as projects_router
from backend.routers.persons import router as persons_router
from backend.routers.documents import router as documents_router
from backend.routers.agent import router as agent_router
from backend.routers.system import router as system_router
from backend.routers.content_understanding import router as content_understanding_router

__all__ = [
    "projects_router",
    "persons_router",
    "documents_router",
    "agent_router",
    "system_router",
    "content_understanding_router"
]
