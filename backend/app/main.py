from pathlib import Path
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.logging_config import configure_logging
from backend.app.api.feedback import router as feedback_router
from backend.app.api.generate import router as generate_router
from backend.app.api.progress import router as progress_router
from backend.app.routes.blueprints import router as blueprint_router
from backend.app.routes.scraper import router as scraper_router
from backend.app.storage.db import init_db
from backend.app.storage.qdrant import QdrantManager

# ── Configure structlog before any submodule imports ────────────────
# Submodules (routes, storage, etc.) call structlog.get_logger() at
# module level; if structlog isn't configured yet, those loggers use
# the default processors and may silently drop INFO-level messages.
configure_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_file="data/logs/est-synthesizer.log",
)

HERE = Path(__file__).resolve().parent
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Re-apply logging config after uvicorn's dictConfig ────────────
    # uvicorn's LOGGING_CONFIG runs during server startup (AFTER app
    # import when using reload) and resets the uvicorn loggers to
    # propagate=False with their own handlers.  We override that here
    # so every log line (including access logs)  uses structlog format.
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_file="data/logs/est-synthesizer.log",
    )
    global logger
    logger = structlog.get_logger(__name__)

    logger.info("Application starting", host=settings.HOST, port=settings.PORT)

    await init_db()

    qdrant = QdrantManager()
    await qdrant.init_collections()
    app.state.qdrant = qdrant
    logger.info("Qdrant collections initialized")
    yield
    await qdrant.close()
    logger.info("Application shutdown complete")


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
app.include_router(scraper_router)
app.include_router(generate_router)
app.include_router(progress_router)
app.include_router(feedback_router)

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
