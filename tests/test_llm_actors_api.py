import os
from fastapi.testclient import TestClient

from backend.api.routes import app

client = TestClient(app)


def test_refresh_news_actors_mock(monkeypatch):
    # force mock mode
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # pick first news
    news_list = client.get("/api/news").json()
    assert news_list, "news list should not be empty"
    news_id = news_list[0]["id"]

    resp = client.post(f"/api/news/{news_id}/actors/refresh", json={"news_id": news_id})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("actors"), list)
    assert len(data["actors"]) > 0
    assert isinstance(data.get("actor_ids"), list)
    assert len(data["actor_ids"]) > 0

    # verify news now has mentioned actors
    refreshed_news = client.get(f"/api/news/{news_id}").json()
    assert refreshed_news.get("mentioned_actors")

    # restore env
    if original_key:
        os.environ["GEMINI_API_KEY"] = original_key

