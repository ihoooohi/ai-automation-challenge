from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import time
from models import ModerationRequest, ModerationResponse
from moderation_service import ModerationService
import os


_service: ModerationService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize service on startup"""
    global _service
    _service = ModerationService(
        openai_key=os.getenv("OPENAI_API_KEY", "mock-key"),
        anthropic_key=os.getenv("ANTHROPIC_API_KEY", "mock-key")
    )
    print("Moderation service initialized")
    yield
    print("Shutting down")


app = FastAPI(title="Content Moderation API", lifespan=lifespan)


@app.post("/moderate", response_model=ModerationResponse)
async def moderate_content(request: ModerationRequest):
    """Moderate content for policy violations."""
    start_time = time.time()

    try:
        result = await _service.moderate_content(request)
        processing_time = (time.time() - start_time) * 1000

        return ModerationResponse(
            video_id=request.video_id,
            moderation=result,
            processing_time_ms=round(processing_time, 2)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}
