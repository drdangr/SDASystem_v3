"""
Интеграционный тест: RU/UK новости в истории Ukraine Conflict Updates.

Запуск:
  GEMINI_API_KEY=... pytest -q tests/test_multilang_ukraine_conflict_ner_integration.py -s

Требования:
  - Реальный Gemini (не mock)
  - Wikidata включён (WIKIDATA_ENABLED=true по умолчанию)
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import pytest

from backend.models.entities import Actor, News
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService


NEWS_IDS = ["news_c4f2a1b3d4e5", "news_8a7b6c5d4e3f"]
STORY_ID = "story_757e40e08c49"


def _has_cyrillic(s: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", s or ""))


def _load_news_items() -> list[dict]:
    data_path = Path(__file__).parent.parent / "data" / "news.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    by_id = {x.get("id"): x for x in data if isinstance(x, dict)}
    missing = [nid for nid in NEWS_IDS if nid not in by_id]
    if missing:
        raise AssertionError(f"Missing news in data/news.json: {missing}")
    return [by_id[nid] for nid in NEWS_IDS]


def _load_actors() -> list[Actor]:
    actors_path = Path(__file__).parent.parent / "data" / "actors.json"
    if not actors_path.exists():
        return []
    with open(actors_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    actors: list[Actor] = []
    for item in data:
        actors.append(Actor(**item))
    return actors


@pytest.mark.integration
def test_ukraine_conflict_ru_uk_news_real_ner_and_canonicalization(tmp_path):
    # Подхватываем .env (как в приложении)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set; integration test requires real Gemini")

    if os.getenv("WIKIDATA_ENABLED", "true").lower() != "true":
        pytest.skip("WIKIDATA_ENABLED is not true; test expects Wikidata enrichment")

    llm = LLMService(api_key=api_key, use_mock=False)
    gm = GraphManager()

    # Load existing actors into gazetteer base (helps dedup/alias)
    for actor in _load_actors():
        gm.add_actor(actor)

    service = ActorsExtractionService(
        graph_manager=gm,
        llm_service=llm,
        data_dir=str(tmp_path),
        use_spacy=False,
    )

    # Load and add the two new news items
    raw_items = _load_news_items()
    news_objs: list[News] = []
    for item in raw_items:
        assert item.get("story_id") == STORY_ID
        news = News(**item)
        # ensure created_at is present (pydantic will parse), fallback if not
        if not getattr(news, "created_at", None):
            news.created_at = datetime.utcnow()
        gm.add_news(news)
        news_objs.append(news)

    # Run extraction for both news items, then deduplicate across them
    for news in news_objs:
        extracted, actor_ids = service.extract_for_news(news)
        assert isinstance(extracted, list)
        assert len(actor_ids) >= 3, "Expected at least 3 actors for RU/UK news"

    service.deduplicate_actors()
    # Ensure our late latinization pass runs after merges too
    service._late_latinize_actor_names()

    # Collect actors we care about
    all_actors = list(gm.actors.values())

    def find_by_substr(substr: str) -> list[Actor]:
        out = []
        for a in all_actors:
            if substr.lower() in (a.canonical_name or "").lower():
                out.append(a)
                continue
            for al in a.aliases or []:
                if substr.lower() in (al.get("name", "") or "").lower():
                    out.append(a)
                    break
        return out

    zel = find_by_substr("Zelensky")
    put = find_by_substr("Putin")
    bid = find_by_substr("Biden")

    assert zel, "Expected Zelensky/Zelenskyy to be extracted"
    assert put, "Expected Putin to be extracted"
    assert bid, "Expected Biden to be extracted"

    # Canonical names should be Latin (for these well-known entities)
    for group, label in [(zel, "Zelensky"), (put, "Putin"), (bid, "Biden")]:
        # prefer the first match; after dedup it should be 1 anyway
        a = group[0]
        assert a.canonical_name, f"{label}: missing canonical_name"
        assert not _has_cyrillic(a.canonical_name), f"{label}: canonical_name contains Cyrillic: {a.canonical_name}"

    # Dedup expectation: for Zelensky we should end up with <=1 actor per QID (ideally exactly one)
    zel_qids = {a.wikidata_qid for a in zel if a.wikidata_qid}
    assert len(zel_qids) <= 1
    if zel_qids:
        qid = list(zel_qids)[0]
        zel_by_qid = [a for a in all_actors if a.wikidata_qid == qid]
        assert len(zel_by_qid) == 1, "Expected single canonical actor per Wikidata QID after dedup"

    # Metadata expectation: at least one of the key actors should have enrichment
    enriched = [
        a for a in (zel + put + bid)
        if a.wikidata_qid and isinstance(a.metadata, dict) and (a.metadata.get("description") or a.metadata.get("positions") or a.metadata.get("country"))
    ]
    assert enriched, "Expected Wikidata metadata enrichment for at least one key actor"


