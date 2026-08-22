import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import cli, entries, sync
from services import database as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup creates the canonical database. Legacy BibTeX is imported only
    # once for a brand-new DB and never overwrites an existing library.
    db.init_db()
    yield
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="Bibliography Database API",
    description="DB-first research library with on-demand BibTeX exports",
    version="0.2.0",
    lifespan=lifespan
)

cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "BIB_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(",")
    if origin.strip()
]

# CORS for the local or deployed Next.js frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entries.router, prefix="/api")
app.include_router(cli.router, prefix="/api")
app.include_router(sync.router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Bibliography Database API",
        "source_of_truth": "database",
        "database_backend": db.database_backend(),
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
