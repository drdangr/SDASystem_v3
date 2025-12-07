import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.models.entities import News
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService


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
def service(tmp_path):
    gm = GraphManager()
    gm.add_news(make_news("n1", "Tesla opens new factory in Texas"))
    gm.add_news(make_news("n2", "Elon Musk visits Austin"))

    llm = LLMService(api_key=None, use_mock=True)
    svc = ActorsExtractionService(
        gm,
        llm,
        data_dir=tmp_path,
        use_spacy=False,  # disable spaCy for tests, we mock hybrid output
        spacy_model="en_core_web_sm",
    )

    # Mock hybrid extractor for determinism
    def fake_extract(text: str, **kwargs):
        items = []
        if "Tesla" in text:
            items.append({"name": "Tesla", "type": "company", "confidence": 0.9})
            items.append({"name": "Texas", "type": "country", "confidence": 0.85})
        if "Elon" in text:
            items.append({"name": "Elon Musk", "type": "person", "confidence": 0.9})
            items.append({"name": "Austin", "type": "country", "confidence": 0.82})
        return items

    svc.hybrid.extract_actors = fake_extract  # type: ignore
    return svc


def test_extract_for_news(service: ActorsExtractionService):
    news = service.graph_manager.news["n1"]
    extracted, actor_ids = service.extract_for_news(news)

    assert len(actor_ids) == 2
    assert len(service.graph_manager.actors) == 2
    names = {a.canonical_name for a in service.graph_manager.actors.values()}
    assert "Tesla" in names
    assert "Texas" in names
    assert len(service.graph_manager.mentions_graph.edges()) == 2
    assert extracted[0]["name"] == "Tesla"


def test_extract_all_saves_files(service: ActorsExtractionService, tmp_path):
    result = service.extract_all()
    assert len(result) == 2
    assert service.actors_file.exists()
    assert service.news_file.exists()

    # news.json should contain mentioned_actors
    data = json.loads(service.news_file.read_text())
    mentioned = [n for n in data if n["id"] == "n1"][0]["mentioned_actors"]
    assert len(mentioned) >= 1


def test_clear_all_backup(service: ActorsExtractionService):
    # create actors file
    service.extract_all()
    assert service.actors_file.exists()

    service.clear_all(clear_cache=False)
    # backup should exist
    assert service.backup_file.exists()
    # actors cleared
    assert len(service.graph_manager.actors) == 0
    assert not service.actors_file.exists()

