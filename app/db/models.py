import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    asset_metadata = Column(JSON, default=dict)
    analysis_results = Column(JSON, default=dict)
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    analysis_result = relationship("AnalysisResult", back_populates="asset", uselist=False)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String, ForeignKey("media_assets.id"), nullable=False, unique=True)
    blur_score = Column(Float, nullable=False)
    brightness_score = Column(Float, nullable=False)
    duplicate_detected = Column(Boolean, nullable=False, default=False)
    screenshot_like = Column(Boolean, nullable=False, default=False)
    issues = Column(JSON, default=list)
    confidence = Column(Float, nullable=False, default=0.0)
    summary = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("MediaAsset", back_populates="analysis_result")
