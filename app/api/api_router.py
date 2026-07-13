from fastapi import APIRouter

from app.api.endpoints import analysis, procurevision, sse, locationrisk

api_router = APIRouter()
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(locationrisk.router, tags=["locationrisk"])
api_router.include_router(procurevision.router, tags=["procurevision"])
api_router.include_router(sse.router, prefix="/status", tags=["status"])
