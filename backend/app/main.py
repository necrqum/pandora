from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1.endpoints import media, tags, scan
from app.core.config import settings
from app.db.session import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Pandora...")
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(
    title="Pandora API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(media.router, prefix="/api/v1/media", tags=["media"])
app.include_router(tags.router, prefix="/api/v1/tags", tags=["tags"])
app.include_router(scan.router, prefix="/api/v1/scan", tags=["scan"])

@app.get("/")
async def root():
    return {"message": "Welcome to Pandora API"}