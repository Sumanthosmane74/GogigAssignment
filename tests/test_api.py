import os
import importlib

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import app.main as main


class DummyTask:
    def delay(self, asset_id):
        return {"asset_id": asset_id}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "process_media_task", DummyTask())
    with TestClient(main.app) as test_client:
        yield test_client


def test_upload_and_status_flow(client):
    response = client.post(
        "/uploads",
        files={"file": ("vehicle.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["processing_id"]
    assert body["status"] == "pending"

    status_response = client.get(f"/uploads/{body['processing_id']}/status")
    assert status_response.status_code == 200


def test_home_page_serves_upload_ui(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Upload an image" in response.text
    assert "Processing workflow" in response.text
