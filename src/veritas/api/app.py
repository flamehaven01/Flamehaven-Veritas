"""FastAPI application — VERITAS — AI Critique Experimental Report Analysis Framework Backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .routes import router

app = FastAPI(
    title="VERITAS API",
    version="2.1.0",
    description="Experimental Report Analysis Engine — upload a document, get a structured critique.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# Serve frontend static files
_FRONTEND = Path(__file__).parents[4] / "frontend"
if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(_FRONTEND / "index.html"))


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "2.1.0"}


@app.get("/version", tags=["system"])
async def version():
    return {"version": "2.1.0", "protocol": "VERITAS — AI Critique Experimental Report Analysis Framework"}


def main():
    import uvicorn
    uvicorn.run("veritas.api.app:app", host="0.0.0.0", port=8400, reload=True)


if __name__ == "__main__":
    main()
