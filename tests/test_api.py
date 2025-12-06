import pytest
from fastapi.testclient import TestClient

from backend.api.routes import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def test_stories_list_not_empty(client):
    resp = client.get("/api/stories")
    assert resp.status_code == 200
    stories = resp.json()
    assert isinstance(stories, list)
    assert len(stories) > 0


def test_story_events_exist(client):
    stories = client.get("/api/stories").json()
    story_id = stories[0]["id"]

    resp = client.get(f"/api/stories/{story_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)
    # With fallback date extraction, each news sentence should yield at least one event
    assert len(events) > 0
    # Validate required fields
    first = events[0]
    for key in ["id", "news_id", "event_type", "title", "event_date"]:
        assert key in first


def test_news_list_not_empty(client):
    resp = client.get("/api/news")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0


def test_actors_list_not_empty(client):
    resp = client.get("/api/actors")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0


def test_graph_news_endpoint(client):
    resp = client.get("/api/graph/news")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "links" in data and "stories" in data
    assert len(data["nodes"]) > 0


def test_graph_actors_endpoint(client):
    resp = client.get("/api/graph/actors")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "links" in data and "mentions" in data

