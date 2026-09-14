from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.routers import auth, conversations, health, resources, retrieval, technologies
from src.services.ingestion.pipeline import recover_interrupted_resources


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await recover_interrupted_resources()
    yield


app = FastAPI(title="AI Tutor", lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(technologies.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(retrieval.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
