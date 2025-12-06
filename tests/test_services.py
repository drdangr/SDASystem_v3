from datetime import datetime

from backend.services.embedding_service import EmbeddingService
from backend.services.ner_service import NERService
from backend.services.clustering_service import ClusteringService

from backend.services.event_extraction_service import EventExtractionService
from backend.services.graph_manager import GraphManager
from backend.models.entities import News, Story, Event, EventType


def test_event_extraction_uses_published_date_when_no_explicit_date():
    svc = EventExtractionService()
    published_at = datetime(2025, 11, 20, 10, 0, 0)
    news = News(
        id="news_test",
        title="Sample story without explicit date",
        summary="This sentence has no date markers but should produce an event.",
        full_text="Another sentence also without explicit date markers to trigger extraction.",
        source="test",
        published_at=published_at,
        mentioned_actors=[],
        domains=[],
    )

    events = svc.extract_events_from_news(news)

    assert len(events) > 0
    assert all(event.event_date == published_at for event in events)


def test_graph_manager_add_event_links_story():
    gm = GraphManager()
    # prepare story and news
    story = Story(
        id="story_test",
        title="Test story",
        summary="Summary",
        bullets=[],
        news_ids=["news1"],
        core_news_ids=[],
        top_actors=[],
        event_ids=[],
        domains=[],
        primary_domain=None,
        relevance=0.5,
        cohesion=0.5,
        size=1,
        freshness=1.0,
    )
    gm.add_story(story)

    news = News(
        id="news1",
        title="Some news",
        summary="short",
        full_text="text",
        source="src",
        published_at=datetime.utcnow(),
        mentioned_actors=[],
        domains=[],
        story_id=story.id,
    )
    gm.add_news(news)

    event = Event(
        id="event1",
        news_id=news.id,
        story_id=story.id,
        event_type=EventType.FACT,
        title="evt",
        description="desc",
        event_date=datetime.utcnow(),
        actors=[],
    )

    gm.add_event(event)

    assert "event1" in gm.events
    assert "event1" in gm.stories[story.id].event_ids
    events = gm.get_story_events(story.id)
    assert len(events) == 1
    assert events[0].id == "event1"


def test_embedding_service_mock_shape_and_similarity():
    svc = EmbeddingService(use_mock=True)
    emb = svc.encode("hello world")
    assert emb.shape == (1, 384)

    a = svc.encode("climate change policy")[0]
    sim_self = svc.compute_similarity(a, a)
    c = svc.encode("football match sports")[0]
    sim_other = svc.compute_similarity(a, c)
    assert sim_self > sim_other
    assert sim_self >= 0.9


def test_ner_service_extracts_known_and_new_actor():
    ner = NERService()
    # Load gazetteer with one actor
    known_actor_id = "actor_known"
    ner.gazetteer[known_actor_id] = None
    ner.canonical_map["joe biden"] = known_actor_id

    text = "President Joe Biden met with OpenAI leaders in Washington"
    known_ids, new_actors = ner.extract_actors_from_text(text)

    assert known_actor_id in known_ids
    assert len(new_actors) > 0


def test_clustering_service_clusters_by_graph_components():
    gm = GraphManager()
    emb = EmbeddingService(use_mock=True)

    # Two similar news in same component
    n1 = News(
        id="n1",
        title="AI regulation advances",
        summary="EU advances AI regulation",
        full_text="text",
        source="s",
        published_at=datetime.utcnow(),
        mentioned_actors=[],
        domains=["domain_ai"],
        embedding=emb.encode("AI regulation advances")[0].tolist(),
    )
    n2 = News(
        id="n2",
        title="AI regulation progresses",
        summary="Progress on AI regulation",
        full_text="text",
        source="s",
        published_at=datetime.utcnow(),
        mentioned_actors=[],
        domains=["domain_ai"],
        embedding=emb.encode("AI regulation progresses")[0].tolist(),
    )

    gm.add_news(n1)
    gm.add_news(n2)

    # Explicitly connect news to form a component
    gm.news_graph.add_edge("n1", "n2", weight=0.9)

    clustering = ClusteringService(gm)
    stories = clustering.cluster_news_to_stories(min_cluster_size=2, use_graph=True)

    assert len(stories) == 1
    story = stories[0]
    assert set(story.news_ids) == {"n1", "n2"}
    assert story.size == 2

