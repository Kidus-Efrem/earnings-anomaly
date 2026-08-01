import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app
from core.schemas import JobStatus

client = TestClient(app)

def test_ingest_transcript_validation_error():
    # Missing required ticker field
    response = client.post("/api/v1/ingest", json={
        "target_date": "2026-04-24",
        "transcript_url": "https://www.fool.com/earnings/call"
    })
    assert response.status_code == 422

@patch("api.main.execute_query")
@patch("api.main.process_transcript_task.delay")
def test_ingest_transcript_success(mock_delay, mock_execute):
    payload = {
        "ticker": "AAPL",
        "target_date": "2026-04-24",
        "transcript_url": "https://www.fool.com/earnings/call/123"
    }
    response = client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == JobStatus.PENDING
    assert mock_execute.called
    assert mock_delay.called

@patch("api.main.execute_query")
def test_get_job_status_found(mock_execute):
    mock_execute.return_value = [{"status": "COMPLETED", "error_message": None}]
    job_id = "12345678-1234-5678-1234-567812345678"
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["job_id"] == job_id

@patch("api.main.execute_query")
def test_get_job_status_not_found(mock_execute):
    mock_execute.return_value = []
    job_id = "12345678-1234-5678-1234-567812345678"
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 404
