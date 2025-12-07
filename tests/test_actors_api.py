from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.models.entities import News, Story
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService
from backend.api import routes


def make_news(news_id: str, title: str) -> News:
    return News(
        id=news_id,
        title=title,
        summary=title,
        full_text=title,
        source="test",
        published_at=datetime.utcnow(),
    )


@pytest.fixture
def client(tmp_path):
    # Save originals
    orig_gm = routes.graph_manager
    orig_service = routes.actors_extraction_service

    gm = GraphManager()
    gm.add_news(make_news("n1", "Tesla opens factory in Texas"))
    gm.add_news(make_news("n2", "Elon Musk visits Austin"))
    story = Story(
        id="s1",
        title="Tesla expansion",
        summary="",
        news_ids=["n1", "n2"],
        core_news_ids=["n1"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        primary_domain=None,
        domains=[],
        top_actors=[],
        size=2,
        relevance=0.5,
        cohesion=0.5,
        freshness=0.5,
        last_activity=datetime.utcnow(),
    )
    gm.add_story(story)

    llm = LLMService(api_key=None, use_mock=True)
    svc = ActorsExtractionService(
        gm, llm, data_dir=tmp_path, use_spacy=False, spacy_model="en_core_web_sm"
    )

    def fake_extract(text: str, **kwargs):
        items = []
        if "Tesla" in text:
            items.append({"name": "Tesla", "type": "company", "confidence": 0.9})
        if "Elon" in text:
            items.append({"name": "Elon Musk", "type": "person", "confidence": 0.9})
        return items

    svc.hybrid.extract_actors = fake_extract  # type: ignore
    routes.graph_manager = gm
    routes.actors_extraction_service = svc

    client = TestClient(routes.app)
    yield client

    # Restore
    routes.graph_manager = orig_gm
    routes.actors_extraction_service = orig_service


def test_api_extract_all_actors(client):
    resp = client.post("/api/actors/extract/all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 2
    status = data["status"]
    assert status["actors_count"] >= 2


def test_api_extract_news(client):
    resp = client.post("/api/actors/extract/news/n1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["news_id"] == "n1"
    assert len(data["actors"]) >= 1


def test_api_extract_story(client):
    resp = client.post("/api/actors/extract/story/s1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["story_id"] == "s1"
    assert data["updated"] == 2


def test_api_init_status_and_start(client):
    # status before start
    resp = client.get("/api/system/init/status")
    assert resp.status_code == 200
    status = resp.json()

    resp2 = client.post("/api/system/init/start")
    assert resp2.status_code == 200
    status_after = resp2.json()
    assert status_after["actors_count"] >= status.get("actors_count", 0)

