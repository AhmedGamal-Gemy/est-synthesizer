from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.app.storage.sqlite import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and Qdrant
    await init_db()
    # Initialize Qdrant here too
    yield
    # Shutdown

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
