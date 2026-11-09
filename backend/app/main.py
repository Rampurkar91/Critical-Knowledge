"""KnowledgeBridge FastAPI application."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST, settings
from .db import init_db, session_scope
from .seed import bootstrap_demo

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_demo_data:
        with session_scope() as db:
            bootstrap_demo(db)
    yield


app = FastAPI(
    title="KnowledgeBridge API",
    description="Reconstruct, verify and continue: evidence-grounded, permission-aware project handovers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import auth, handovers, knowledge, projects, verification  # noqa: E402

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(knowledge.router)
app.include_router(verification.router)
app.include_router(handovers.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.is_demo_mode,
        "database": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
    }


@app.get("/api")
def api_root() -> dict[str, object]:
    return {"message": "KnowledgeBridge API", "docs": "/docs", "health": "/api/health"}


if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str, request: Request) -> object:
    if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi"):
        raise HTTPException(status_code=404, detail="Not found")
    if FRONTEND_DIST.exists():
        root = FRONTEND_DIST.resolve()
        candidate = (root / full_path).resolve()
        if candidate != root and root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        index = root / "index.html"
        if index.exists():
            return FileResponse(index)
    return JSONResponse({
        "message": "KnowledgeBridge API is running. Build the frontend with `npm run build` to serve the UI here.",
        "api_docs": "/docs",
    })
