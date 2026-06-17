from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.routes.blueprints import router as blueprint_router
from backend.app.storage.db import init_db

HERE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan, title="EST Synthesizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── routes ───────────────────────────────────────────
app.include_router(blueprint_router)

# ── static files (UI) ────────────────────────────────
app.mount("/ui", StaticFiles(directory=str(HERE / "static")), name="ui")


@app.get("/api/config")
async def app_config():
    return {
        "host": settings.HOST,
        "port": settings.PORT,
        "api_base": f"http://{settings.HOST}:{settings.PORT}",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
