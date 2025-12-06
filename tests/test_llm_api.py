from fastapi.testclient import TestClient

from backend.api.routes import app


client = TestClient(app)


def test_llm_summary_mock():
    payload = {
        "task": "summary",
        "title": "Test title",
        "text": "Some long text about AI and testing."
    }
    resp = client.post("/api/llm/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert isinstance(data["result"], str)
    assert len(data["result"]) > 0


def test_llm_bullets_mock():
    payload = {
        "task": "bullets",
        "title": "Bullets title",
        "text": "Line1. Line2. Line3.",
        "max_tokens": 128
    }
    resp = client.post("/api/llm/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("result"), list)
    assert len(data["result"]) > 0


def test_llm_domains_mock():
    payload = {
        "task": "domains",
        "text": "Artificial intelligence and machine learning regulation in the EU."
    }
    resp = client.post("/api/llm/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("result"), list)
    assert len(data["result"]) > 0


def test_llm_events_mock():
    payload = {
        "task": "events",
        "text": "On Nov 20, company A announced a new AI product. Critics said it was risky."
    }
    resp = client.post("/api/llm/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    result = data.get("result")
    assert isinstance(result, list)
    assert len(result) > 0
    assert "title" in result[0]


def test_llm_with_params_override():
    payload = {
        "task": "summary",
        "title": "Params override",
        "text": "Testing overrides for model and sampling params.",
        "model": "gemini-2.5-flash",
        "temperature": 0.4,
        "top_p": 0.8,
        "top_k": 20,
        "max_tokens": 256
    }
    resp = client.post("/api/llm/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data

