from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_assistant,
    alerts,
    auth,
    catalog,
    cdm,
    conjunctions,
    dashboard,
    omm,
    orbit,
    orbit_ws,
    satellites,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(satellites.router)
api_router.include_router(catalog.router)
api_router.include_router(alerts.router)
api_router.include_router(ai_assistant.router)
api_router.include_router(omm.router)
api_router.include_router(cdm.router)
api_router.include_router(dashboard.router)
api_router.include_router(orbit.router)
api_router.include_router(users.router)
api_router.include_router(orbit_ws.router)
api_router.include_router(conjunctions.router)
