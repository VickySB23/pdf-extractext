"""Health check endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    try:
        await request.app.state.mongo_client.admin.command("ping")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})

    return {"status": "healthy"}
