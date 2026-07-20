import os

from celery import Celery

from app.core.config import REDIS_URL

celery_app = Celery("media_pipeline", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() in {"1", "true", "yes"}
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 5})
def process_media_task(self, asset_id: str):
    from app.worker.tasks import process_asset

    return process_asset(asset_id)
