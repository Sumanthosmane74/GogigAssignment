# Intelligent Media Processing Pipeline

This project implements a production-style backend for processing vehicle images uploaded from the field. The service accepts an uploaded image, stores metadata, queues asynchronous analysis, and returns a processing ID immediately. A background worker evaluates the image for common image-quality and content issues using a mix of heuristics and realistic mock integrations.

## Architecture

### High-level flow

1. A client uploads an image through the upload endpoint.
2. The API stores the file on disk, records metadata in PostgreSQL, and returns a processing ID.
3. A Celery worker picks up the job from Redis and performs analysis asynchronously.
4. The worker updates the asset status as pending → processing → completed/failed.
5. Clients can query status, results, or failure reasons through dedicated APIs.

### Major design choices

- FastAPI for the HTTP API layer.
- SQLAlchemy with PostgreSQL for persistence.
- Celery + Redis for queue-based asynchronous work.
- OpenCV-based heuristics for blur, brightness, and screenshot-like detection.
- A simple file-based storage layout that can be swapped for object storage later.

## Processing flow

- Upload endpoint validates size and file presence.
- Metadata and file path are persisted in the database.
- A Celery task is enqueued.
- The worker loads the image, applies four checks, updates the database, and records analysis results.

## Queue strategy

- Redis is used as the message broker.
- Celery workers execute tasks independently and can be scaled horizontally.
- Each task is retried automatically on failure using Celery retry settings.

## AI / heuristics engine

The image analysis currently uses heuristics and realistic mock-style logic instead of a full ML model. The implemented checks are:

- Blur detection via Laplacian variance.
- Brightness analysis via grayscale mean intensity.
- Duplicate detection using a deterministic SHA-256 fingerprint (mocked as an identity check placeholder that can later be compared across a database of prior uploads).
- Screenshot/photo-of-photo heuristics via edge density using Canny filtering.

## Trade-offs

### Intentionally simplified

- Duplicate detection is currently a placeholder based on a hash of the current file rather than a full cross-image deduplication index.
- Storage is local disk-based instead of cloud object storage.
- OCR and advanced vision models are not integrated yet, though the architecture supports adding them later.

### What would improve with more time

- Use object storage like S3 or Azure Blob Storage.
- Add a true duplicate detector using embeddings or perceptual hashing.
- Integrate OCR, image classification, or a hosted vision API.
- Add idempotency, dead-letter queues, and more sophisticated retry policies.

### Scalability concerns

- The current local file storage approach is fine for development but not ideal at scale.
- A production deployment should use managed Redis/Postgres and move uploads to object storage.
- Celery workers should be scaled with autoscaling and health checks.

### Failure handling concerns

- The backend currently records a readable failure reason for the asset.
- A production version should also capture worker logs, retries, and dead-letter artifacts for debugging.

## AI Usage Disclosure

Use this section to describe how AI tools were used during development.

### Where AI was used

- Drafting the service structure and API contract.
- Implementing the file-processing flow and background worker orchestration.
- Generating the README and container setup.

### What AI helped with

- Boilerplate generation for FastAPI, Celery, SQLAlchemy, and Docker compose.
- Suggesting a modular project layout and realistic heuristics.

### Where AI may have been wrong

- The current analysis logic is heuristic-based and should be validated with real image samples.
- Duplicate detection is intentionally simplified and should not be treated as production-grade deduplication.

### How I validated it

- Verified the upload endpoint via local tests.
- Confirmed the project structure and runtime dependencies are consistent.
- Validated the application can be launched via Docker Compose.

## Assumptions made

- The upload is an image file, not a video or multi-part asset.
- The image analysis is heuristic-based for the assignment and not intended to replace a production ML pipeline.
- The system can use local disk storage during development.
- A processing ID is the same as the asset ID for simplicity.

## Local development

### Prerequisites

- Python 3.11+
- Optional: Docker and Docker Compose if you want the containerized path

### Run locally without Docker

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This uses SQLite by default for local development and processes uploads synchronously when Redis/Celery is not available.

### Run with Docker Compose (optional)

```bash
docker compose up --build
```

This starts:

- PostgreSQL on port 5432
- Redis on port 6379
- FastAPI on port 8000
- Celery worker

### Run tests

```bash
pytest -q
```

## API endpoints

### Upload image

```bash
curl -X POST "http://localhost:8000/uploads" \
  -F "file=@/path/to/vehicle.jpg"
```

Example response:

```json
{
  "message": "Upload accepted and processing started",
  "processing_id": "6a6d8a00-cd90-44ec-9094-b765a94f9783",
  "status": "pending"
}
```

### Get processing status

```bash
curl "http://localhost:8000/uploads/6a6d8a00-cd90-44ec-9094-b765a94f9783/status"
```

Example response:

```json
{
  "processing_id": "6a6d8a00-cd90-44ec-9094-b765a94f9783",
  "status": "processing",
  "created_at": "2026-07-20T00:00:00",
  "updated_at": "2026-07-20T00:00:00",
  "completed_at": null
}
```

### Get analysis results

```bash
curl "http://localhost:8000/uploads/6a6d8a00-cd90-44ec-9094-b765a94f9783/results"
```

Example response:

```json
{
  "processing_id": "6a6d8a00-cd90-44ec-9094-b765a94f9783",
  "status": "completed",
  "analysis_results": {
    "blur_score": 123.45,
    "brightness_score": 180.2,
    "duplicate_detected": false,
    "screenshot_like": false,
    "issues": [],
    "confidence": 0.0,
    "summary": "Image looks acceptable"
  }
}
```

### Get failure reason

```bash
curl "http://localhost:8000/uploads/6a6d8a00-cd90-44ec-9094-b765a94f9783/failure"
```

Example response:

```json
{
  "processing_id": "6a6d8a00-cd90-44ec-9094-b765a94f9783",
  "status": "failed",
  "failure_reason": "Unable to read image"
}
```

## Future enhancements

- Add authentication and authorization.
- Add webhook notifications.
- Add an audit trail for each processing attempt.
- Add metrics and dashboards.
