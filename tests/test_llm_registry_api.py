import json
import os
import tempfile
import importlib

from fastapi.testclient import TestClient


def make_temp_config(tmp_path):
    data = {
        "profiles": [
            {
                "id": "p1",
                "label": "Profile1",
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40,
                "max_tokens": 256,
                "timeout": 10,
            },
            {
                "id": "p2",
                "label": "Profile2",
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "temperature": 0.4,
                "top_p": 0.9,
                "top_k": 40,
                "max_tokens": 512,
                "timeout": 15,
            },
        ],
        "services": [
            {
                "id": "summary_bullets",
                "label": "Summary+Bullets",
                "description": "test svc",
                "impl": "backend.services.llm_tasks.summary_bullets_service:SummaryBulletsService",
                "default_profile_id": "p1",
                "params": {"max_points": 3},
            }
        ],
    }
    cfg_path = tmp_path / "llm_services.json"
    cfg_path.write_text(json.dumps(data))
    return cfg_path


def test_registry_endpoints_reload_and_update(tmp_path, monkeypatch):
    cfg_path = make_temp_config(tmp_path)
    monkeypatch.setenv("LLM_SERVICES_CONFIG", str(cfg_path))

    # Reload module to re-init registry with temp config
    from backend.api import routes

    importlib.reload(routes)
    client = TestClient(routes.app)

    resp = client.get("/api/llm/services")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["services"]) == 1
    assert data["profiles"][0]["id"] == "p1"

    # Update service default profile
    resp_upd = client.put("/api/llm/services/summary_bullets", json={"profile_id": "p2"})
    assert resp_upd.status_code == 200
    assert resp_upd.json()["default_profile_id"] == "p2"

    # Invoke service (uses mock LLM if no key)
    payload = {"profile_id": "p2", "payload": {"title": "t", "text": "demo text"}}
    resp_inv = client.post("/api/llm/services/summary_bullets/invoke", json=payload)
    assert resp_inv.status_code == 200
    result = resp_inv.json()["result"]
    assert "summary" in result and "bullets" in result

