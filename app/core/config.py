import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(BASE_DIR / "uploads")))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./media_pipeline.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
