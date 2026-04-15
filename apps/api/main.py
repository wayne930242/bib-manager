from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import entries, cli
from services import database as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load entries from BibTeX file
    db.init_db()
    yield
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="BibTeX Manager API",
    description="API for managing BibTeX bibliography with notes and search",
    version="0.1.0",
    lifespan=lifespan
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entries.router, prefix="/api")
app.include_router(cli.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "BibTeX Manager API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
