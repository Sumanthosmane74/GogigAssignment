import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_SIZE_MB, UPLOAD_ROOT
from app.db.database import Base, engine, get_db
from app.db.models import MediaAsset
from app.worker.celery_app import process_media_task
from app.worker.tasks import process_asset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Intelligent Media Processing Pipeline", version="1.0.0")

Base.metadata.create_all(bind=engine)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# Setup static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def root():
    """Serve the frontend HTML"""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return {"message": "Welcome to Media Processing Pipeline"}


@app.post("/api/uploads", status_code=202)
def upload_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    contents = file.file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds max upload size")

    checksum = hashlib.sha256(contents).hexdigest()
    asset_id = str(uuid.uuid4())
    storage_dir = UPLOAD_ROOT / asset_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / file.filename
    with open(storage_path, "wb") as destination:
        destination.write(contents)

    asset = MediaAsset(
        id=asset_id,
        filename=file.filename,
        original_filename=file.filename,
        storage_path=str(storage_path),
        mime_type=file.content_type,
        size_bytes=len(contents),
        checksum=checksum,
        status="pending",
        asset_metadata={"content_type": file.content_type},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    try:
        process_media_task.delay(asset.id)
    except Exception as exc:
        logger.warning("Falling back to synchronous processing: %s", exc)
        process_asset(asset.id)

    return JSONResponse(
        status_code=202,
        content={
            "message": "Upload accepted and processing started",
            "processing_id": asset.id,
            "status": asset.status,
        },
    )


@app.get("/api/uploads/{processing_id}/status")
def get_status(processing_id: str, db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == processing_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Processing ID not found")
    return {
        "processing_id": asset.id,
        "status": asset.status,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
        "completed_at": asset.completed_at.isoformat() if asset.completed_at else None,
    }


@app.get("/api/uploads/{processing_id}/results")
def get_results(processing_id: str, db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == processing_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Processing ID not found")
    if asset.status != "completed":
        raise HTTPException(status_code=409, detail="Processing is not completed yet")
    return {
        "processing_id": asset.id,
        "status": asset.status,
        "analysis_results": asset.analysis_results,
    }


@app.get("/api/uploads/{processing_id}/failure")
def get_failure(processing_id: str, db: Session = Depends(get_db)):
    asset = db.query(MediaAsset).filter(MediaAsset.id == processing_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Processing ID not found")
    if asset.status != "failed":
        raise HTTPException(status_code=404, detail="No failure recorded")
    return {
        "processing_id": asset.id,
        "status": asset.status,
        "failure_reason": asset.failure_reason,
    }
