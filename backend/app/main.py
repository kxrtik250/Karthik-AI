"""Karthik AI — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    certifications,
    companies,
    documents,
    health,
    interview,
    placements,
    profile,
    projects,
    rag,
    resume,
    skills,
)

app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="Personal AI Assistant — Phase 4 RAG Retrieval & Answer-Generation Layer",
)

# Allow the Vite dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(certifications.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(placements.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
