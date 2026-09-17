from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.communication import router as communication_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.attachments import router as attachments_router
from app.api.v1.ai import router as ai_router
from app.api.v1.sla import router as sla_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.resolution import router as resolution_router
from app.api.v1.dashboard import router as dashboard_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(communication_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(attachments_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(sla_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(resolution_router)
api_v1_router.include_router(dashboard_router)

__all__ = ["api_v1_router"]



