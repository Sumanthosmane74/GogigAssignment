import hashlib
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_ROOT
from app.db.database import SessionLocal
from app.db.models import AnalysisResult, MediaAsset

logger = logging.getLogger(__name__)


def _load_image(path: str):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Unable to read image")
    return img


def _detect_blur(image: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
    return {"blur_score": float(fm), "is_blurry": fm < 100.0}


def _detect_brightness(image: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray.mean())
    return {"brightness_score": mean_brightness, "is_too_dark": mean_brightness < 80.0, "is_too_bright": mean_brightness > 220.0}


def _detect_duplicate(path: str) -> Dict[str, Any]:
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    return {"sha256": digest, "duplicate_detected": False}


def _detect_screenshot_like(image: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    return {"screenshot_like": edge_density > 0.08}


def analyze_image(asset: MediaAsset, db: Session) -> Dict[str, Any]:
    image_path = asset.storage_path
    image = _load_image(image_path)
    blur = _detect_blur(image)
    brightness = _detect_brightness(image)
    duplicate = _detect_duplicate(image_path)
    screenshot = _detect_screenshot_like(image)

    issues: List[str] = []
    if blur["is_blurry"]:
        issues.append("Image appears blurry")
    if brightness["is_too_dark"]:
        issues.append("Image is too dark")
    if brightness["is_too_bright"]:
        issues.append("Image is too bright")
    if screenshot["screenshot_like"]:
        issues.append("Image may be a screenshot or photo of a screen")

    confidence = 0.0
    if blur["is_blurry"]:
        confidence += 0.3
    if brightness["is_too_dark"] or brightness["is_too_bright"]:
        confidence += 0.2
    if screenshot["screenshot_like"]:
        confidence += 0.25
    if duplicate["duplicate_detected"]:
        confidence += 0.25

    summary = "Image looks acceptable" if not issues else "; ".join(issues)
    result = AnalysisResult(
        asset_id=asset.id,
        blur_score=blur["blur_score"],
        brightness_score=brightness["brightness_score"],
        duplicate_detected=duplicate["duplicate_detected"],
        screenshot_like=screenshot["screenshot_like"],
        issues=issues,
        confidence=min(confidence, 1.0),
        summary=summary,
    )
    db.add(result)
    asset.analysis_results = {
        "blur_score": blur["blur_score"],
        "brightness_score": brightness["brightness_score"],
        "duplicate_detected": duplicate["duplicate_detected"],
        "screenshot_like": screenshot["screenshot_like"],
        "issues": issues,
        "confidence": min(confidence, 1.0),
        "summary": summary,
    }
    asset.status = "completed"
    asset.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return asset.analysis_results


def process_asset(asset_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        asset.status = "processing"
        asset.failure_reason = None
        db.commit()
        logger.info("Processing asset %s", asset_id)
        result = analyze_image(asset, db)
        logger.info("Completed processing asset %s", asset_id)
        return {"asset_id": asset_id, "status": "completed", "result": result}
    except Exception as exc:
        asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
        if asset is not None:
            asset.status = "failed"
            asset.failure_reason = str(exc)
            db.commit()
        logger.exception("Processing failed for asset %s", asset_id)
        raise
    finally:
        db.close()
