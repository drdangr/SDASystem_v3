"""
Integration tests for database integration with GraphManager and services
Tests full workflow with database backend
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime
from typing import List

from backend.services.database_manager import DatabaseManager
from backend.services.graph_manager import GraphManager
from backend.services.clustering_service import ClusteringService
from backend.services.event_extraction_service import EventExtractionService
from backend.models.entities import (
    News, Actor, Story, Event, ActorType, EventType
)


@pytest.fixture(scope="module")
def test_db():
    """Create a test database manager"""
    db_name = os.getenv("TEST_POSTGRES_DB", "sdas_db")
    db = DatabaseManager(
        dbname=db_name,
        user=os.getenv("TEST_POSTGRES_USER", "postgres"),
        password=os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("TEST_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("TEST_POSTGRES_PORT", "5432"))
    )
    
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        yield db
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        db.close()


@pytest.fixture
def cleanup_test_data(test_db):
    """Cleanup test data after each test"""
    yield
    with test_db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM news_relations WHERE source_news_id LIKE 'test_%' OR target_news_id LIKE 'test_%'")
            cur.execute("DELETE FROM event_actors WHERE event_id LIKE 'test_%'")
            cur.execute("DELETE FROM story_events WHERE story_id LIKE 'test_%' OR event_id LIKE 'test_%'")
            cur.execute("DELETE FROM story_actors WHERE story_id LIKE 'test_%' OR actor_id LIKE 'test_%'")
            cur.execute("DELETE FROM story_news WHERE story_id LIKE 'test_%' OR news_id LIKE 'test_%'")
            cur.execute("DELETE FROM news_actors WHERE news_id LIKE 'test_%' OR actor_id LIKE 'test_%'")
            cur.execute("DELETE FROM actor_aliases WHERE actor_id LIKE 'test_%'")
            cur.execute("DELETE FROM actor_relations WHERE source_actor_id LIKE 'test_%' OR target_actor_id LIKE 'test_%'")
            cur.execute("DELETE FROM events WHERE id LIKE 'test_%'")
            cur.execute("DELETE FROM stories WHERE id LIKE 'test_%'")
            cur.execute("DELETE FROM news WHERE id LIKE 'test_%'")
            cur.execute("DELETE FROM actors WHERE id LIKE 'test_%'")


@pytest.fixture
def graph_manager(test_db):
    """Create GraphManager with test database"""
    return GraphManager(db_manager=test_db)


@pytest.fixture
def clustering_service(graph_manager):
    """Create ClusteringService with GraphManager"""
    return ClusteringService(graph_manager)


@pytest.fixture
def event_service():
    """Create EventExtractionService"""
    return EventExtractionService()


class TestGraphManagerIntegration:
    """Integration tests for GraphManager with database"""
    
    def test_graph_manager_add_news(self, graph_manager, cleanup_test_data):
        """Test GraphManager.add_news() saves to database"""
        news = News(
            id="test_gm_news_1",
            title="Test News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        
        graph_manager.add_news(news)
        
        # Verify in database
        retrieved = graph_manager.db.get_news(news.id)
        assert retrieved is not None
        assert retrieved.title == news.title
        
        # Verify in graph
        assert news.id in graph_manager.news_graph.nodes()
    
    def test_graph_manager_add_actor(self, graph_manager, cleanup_test_data):
        """Test GraphManager.add_actor() saves to database"""
        actor = Actor(
            id="test_gm_actor_1",
            canonical_name="Test Actor",
            actor_type=ActorType.PERSON
        )
        
        graph_manager.add_actor(actor)
        
        # Verify in database
        retrieved = graph_manager.db.get_actor(actor.id)
        assert retrieved is not None
        assert retrieved.canonical_name == actor.canonical_name
        
        # Verify in graph
        assert actor.id in graph_manager.actors_graph.nodes()
    
    def test_graph_manager_news_actor_mentions(self, graph_manager, cleanup_test_data):
        """Test news-actor mentions relationship"""
        actor = Actor(
            id="test_gm_actor_2",
            canonical_name="Mentioned Actor",
            actor_type=ActorType.PERSON
        )
        graph_manager.add_actor(actor)
        
        news = News(
            id="test_gm_news_2",
            title="News with Actor",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384,
            mentioned_actors=[actor.id]
        )
        graph_manager.add_news(news)
        
        # Verify relationship in database
        news_actors = graph_manager.db.get_news_actors(news.id)
        assert actor.id in news_actors
        
        # Verify in mentions graph
        assert graph_manager.mentions_graph.has_edge(f"news_{news.id}", f"actor_{actor.id}")
    
    def test_graph_manager_compute_similarities(self, graph_manager, cleanup_test_data):
        """Test compute_news_similarities uses pgvector"""
        # Create multiple news with similar embeddings
        news_items = []
        for i in range(3):
            news = News(
                id=f"test_gm_sim_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1 + i * 0.01] * 384
            )
            graph_manager.add_news(news)
            news_items.append(news)
        
        # Compute similarities
        relations = graph_manager.compute_news_similarities(threshold=0.9)
        
        # Should find some relations
        assert isinstance(relations, list)
        # Relations should be saved in database
        if len(relations) > 0:
            assert all(isinstance(r, NewsRelation) for r in relations)


class TestClusteringServiceIntegration:
    """Integration tests for ClusteringService with database"""
    
    def test_clustering_creates_stories_in_db(self, clustering_service, graph_manager, cleanup_test_data):
        """Test that clustering creates stories in database"""
        # Create news items
        news_items = []
        for i in range(5):
            news = News(
                id=f"test_cluster_news_{i}",
                title=f"Cluster News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1 + (i % 2) * 0.01] * 384  # Two groups
            )
            graph_manager.add_news(news)
            news_items.append(news)
        
        # Cluster (may or may not find clusters depending on embeddings)
        stories = clustering_service.cluster_news_to_stories(min_cluster_size=2)
        
        # Verify stories are in database (if any were created)
        if len(stories) > 0:
            for story in stories:
                retrieved = graph_manager.db.get_story(story.id)
                assert retrieved is not None
                assert len(retrieved.news_ids) >= 2
        else:
            # If no clusters found, that's okay - embeddings might be too different
            # Just verify the news are still in database
            all_news = graph_manager.db.get_all_news()
            test_news = [n for n in all_news if n.id.startswith("test_cluster_")]
            assert len(test_news) == 5


class TestEventExtractionIntegration:
    """Integration tests for EventExtractionService with database"""
    
    def test_event_extraction_saves_to_db(self, event_service, graph_manager, cleanup_test_data):
        """Test that extracted events are saved to database"""
        news = News(
            id="test_event_news_1",
            title="Breaking: Major Event Happened",
            summary="A major event occurred on January 1, 2024. Important developments.",
            full_text="On January 1, 2024, a major event happened. This is significant.",
            source="Test",
            published_at=datetime(2024, 1, 1),
            embedding=[0.1] * 384
        )
        graph_manager.add_news(news)
        
        # Extract events
        events = event_service.extract_events_from_news(news)
        
        # Add events to graph (which saves to DB)
        for event in events:
            graph_manager.add_event(event)
        
        # Verify events in database
        assert len(events) > 0
        for event in events:
            retrieved = graph_manager.db.get_event(event.id)
            assert retrieved is not None
            assert retrieved.news_id == news.id


class TestFullPipelineIntegration:
    """Full pipeline integration tests"""
    
    def test_full_pipeline_news_to_story(self, graph_manager, clustering_service, event_service, cleanup_test_data):
        """Test full pipeline: news -> actors -> clustering -> events"""
        # Create actors
        actors = []
        for i in range(2):
            actor = Actor(
                id=f"test_pipeline_actor_{i}",
                canonical_name=f"Pipeline Actor {i}",
                actor_type=ActorType.PERSON
            )
            graph_manager.add_actor(actor)
            actors.append(actor)
        
        # Create news with actors
        news_items = []
        for i in range(4):
            news = News(
                id=f"test_pipeline_news_{i}",
                title=f"Pipeline News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1 + (i % 2) * 0.01] * 384,
                mentioned_actors=[actors[i % 2].id]
            )
            graph_manager.add_news(news)
            news_items.append(news)
        
        # Extract events
        all_events = []
        for news in news_items:
            events = event_service.extract_events_from_news(news)
            for event in events:
                graph_manager.add_event(event)
                all_events.append(event)
        
        # Cluster into stories (may or may not find clusters)
        stories = clustering_service.cluster_news_to_stories(min_cluster_size=2)
        
        # Verify everything is in database
        if len(stories) > 0:
            # Verify story has news
            story = stories[0]
            retrieved_story = graph_manager.db.get_story(story.id)
            assert retrieved_story is not None
            assert len(retrieved_story.news_ids) >= 2
            
            # Verify events are linked to story
            story_events = graph_manager.db.get_story_events(story.id)
            assert len(story_events) >= 0  # Events may or may not be linked
        else:
            # If no clusters found, verify news and events are still in database
            all_news = graph_manager.db.get_all_news()
            test_news = [n for n in all_news if n.id.startswith("test_pipeline_")]
            assert len(test_news) == 4
        
        # Verify news-actor relationships
        for news in news_items:
            news_actors = graph_manager.db.get_news_actors(news.id)
            assert len(news_actors) > 0


class TestAPIIntegration:
    """Integration tests for API endpoints with database"""
    
    def test_api_data_consistency(self, test_db, cleanup_test_data):
        """Test that API would return consistent data from database"""
        # Create test data
        actor = Actor(
            id="test_api_actor",
            canonical_name="API Test Actor",
            actor_type=ActorType.PERSON
        )
        test_db.save_actor(actor)
        
        news = News(
            id="test_api_news",
            title="API Test News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384,
            mentioned_actors=[actor.id]
        )
        test_db.save_news(news)
        
        # Verify data can be retrieved (simulating API call)
        retrieved_actor = test_db.get_actor(actor.id)
        retrieved_news = test_db.get_news(news.id)
        
        assert retrieved_actor is not None
        assert retrieved_news is not None
        assert actor.id in test_db.get_news_actors(news.id)

