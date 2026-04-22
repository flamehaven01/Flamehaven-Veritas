"""FastAPI endpoint tests."""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_version(client):
    res = client.get("/version")
    assert res.json()["version"] == "3.2.0"


def test_critique_text_endpoint(client, sample_text):
    res = client.post("/api/v1/critique/text", json={"report_text": sample_text})
    assert res.status_code == 200
    data = res.json()
    assert "precheck" in data
    assert "omega_score" in data
    assert 0.0 <= data["omega_score"] <= 1.0
    assert "steps" in data
    assert len(data["steps"]) == 6  # STEP 0-5


def test_precheck_endpoint(client, sample_text):
    res = client.post("/api/v1/precheck", json={"report_text": sample_text})
    assert res.status_code == 200
    data = res.json()
    assert "mode" in data
    assert "line1" in data


def test_upload_txt_file(client, sample_text):
    content = sample_text.encode("utf-8")
    res = client.post(
        "/api/v1/critique/upload",
        data={"template": "bmj", "round_number": "1"},
        files={"file": ("test_report.txt", io.BytesIO(content), "text/plain")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "precheck" in data


def test_upload_unsupported_ext(client):
    res = client.post(
        "/api/v1/critique/upload",
        data={"template": "bmj", "round_number": "1"},
        files={"file": ("report.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert res.status_code == 400


def test_download_md(client, sample_text):
    content = sample_text.encode("utf-8")
    res = client.post(
        "/api/v1/critique/download",
        data={"template": "bmj", "round_number": "1", "format": "md"},
        files={"file": ("report.txt", io.BytesIO(content), "text/plain")},
    )
    assert res.status_code == 200
    assert "text/markdown" in res.headers.get("content-type", "")


def test_invalid_format_download(client, sample_text):
    content = sample_text.encode("utf-8")
    res = client.post(
        "/api/v1/critique/download",
        data={"template": "bmj", "round_number": "1", "format": "pptx"},
        files={"file": ("report.txt", io.BytesIO(content), "text/plain")},
    )
    assert res.status_code == 400
