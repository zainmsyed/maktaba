from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import AsyncIterator

from fastapi import Depends, FastAPI, File, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.db import get_session, initialize_database
from app.uploads import create_document_upload

DATA_DIR = Path(os.getenv("DATA_DIR", "/data")).resolve()
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


def ensure_data_directories() -> None:
    for name in ("pdfs", "epubs", "thumbs"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_data_directories()
    initialize_database()
    yield


app = FastAPI(title="Maktaba API", lifespan=lifespan)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Maktaba backend is running",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "backend",
        "data_dir": str(DATA_DIR),
        "storage_dirs": {
            "pdfs": str(DATA_DIR / "pdfs"),
            "epubs": str(DATA_DIR / "epubs"),
            "thumbs": str(DATA_DIR / "thumbs"),
        },
    }


@app.post("/api/documents")
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    result = await create_document_upload(session, file, DATA_DIR)
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return {
        "created": result.created,
        "document": result.document.model_dump(mode="json"),
        "jobs": [job.model_dump(mode="json") for job in result.jobs],
    }
