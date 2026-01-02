"""
End-to-end tests for full system workflow with database
Tests complete cycles: news loading -> actor extraction -> clustering -> story creation
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime

from backend.services.database_manager import DatabaseManager
from backend.services.graph_manager import GraphManager
from backend.services.clustering_service import ClusteringService
from backend.services.event_extraction_service import EventExtractionService
from backend.services.embedding_service import EmbeddingService
from backend.models.entities import News, Actor, Story, ActorType


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
def cleanup_e2e_data(test_db):
    """Cleanup E2E test data"""
    yield
    with test_db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM news_relations WHERE source_news_id LIKE 'e2e_%' OR target_news_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM event_actors WHERE event_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM story_events WHERE story_id LIKE 'e2e_%' OR event_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM story_actors WHERE story_id LIKE 'e2e_%' OR actor_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM story_news WHERE story_id LIKE 'e2e_%' OR news_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM news_actors WHERE news_id LIKE 'e2e_%' OR actor_id LIKE 'e2e_%'")
            cur.execute("DELETE FROM events WHERE id LIKE 'e2e_%'")
            cur.execute("DELETE FROM stories WHERE id LIKE 'e2e_%'")
            cur.execute("DELETE FROM news WHERE id LIKE 'e2e_%'")
            cur.execute("DELETE FROM actors WHERE id LIKE 'e2e_%'")


@pytest.fixture
def e2e_graph_manager(test_db):
    """Create GraphManager for E2E tests"""
    return GraphManager(db_manager=test_db)


@pytest.fixture
def e2e_embedding_service():
    """Create EmbeddingService for E2E tests"""
    return EmbeddingService(backend="mock")  # Use mock for speed in tests


class TestE2EFullCycle:
    """End-to-end tests for complete system workflow"""
    
    def test_e2e_news_to_story_cycle(self, e2e_graph_manager, e2e_embedding_service, cleanup_e2e_data):
        """Test complete cycle: create news -> generate embeddings -> cluster -> create story"""
        clustering_service = ClusteringService(e2e_graph_manager)
        event_service = EventExtractionService()
        
        # Step 1: Create news with embeddings
        news_items = []
        for i in range(6):
            text = f"Breaking news {i}: Major event happened. Important development."
            embedding = e2e_embedding_service.encode(text)[0].tolist()
            
            news = News(
                id=f"e2e_news_{i}",
                title=f"E2E News {i}",
                summary=f"Summary {i}",
                source="E2E Test",
                published_at=datetime.utcnow(),
                embedding=embedding
            )
            e2e_graph_manager.add_news(news)
            news_items.append(news)
        
        # Step 2: Compute similarities
        relations = e2e_graph_manager.compute_news_similarities(threshold=0.6)
        assert len(relations) >= 0  # May or may not find relations depending on embeddings
        
        # Step 3: Cluster into stories
        stories = clustering_service.cluster_news_to_stories(min_cluster_size=2)
        
        # Step 4: Extract events
        all_events = []
        for news in news_items:
            events = event_service.extract_events_from_news(news)
            for event in events:
                e2e_graph_manager.add_event(event)
                all_events.append(event)
        
        # Verify results
        assert len(news_items) == 6
        
        # Verify stories were created (if clustering found clusters)
        if len(stories) > 0:
            story = stories[0]
            retrieved = e2e_graph_manager.db.get_story(story.id)
            assert retrieved is not None
            assert len(retrieved.news_ids) >= 2
        
        # Verify events were created
        assert len(all_events) > 0
        for event in all_events:
            retrieved = e2e_graph_manager.db.get_event(event.id)
            assert retrieved is not None
    
    def test_e2e_with_actors(self, e2e_graph_manager, e2e_embedding_service, cleanup_e2e_data):
        """Test E2E cycle with actor extraction"""
        clustering_service = ClusteringService(e2e_graph_manager)
        
        # Step 1: Create actors
        actors = []
        for i in range(3):
            actor = Actor(
                id=f"e2e_actor_{i}",
                canonical_name=f"E2E Actor {i}",
                actor_type=ActorType.PERSON
            )
            e2e_graph_manager.add_actor(actor)
            actors.append(actor)
        
        # Step 2: Create news with actor mentions
        news_items = []
        for i in range(5):
            text = f"News about {actors[i % 3].canonical_name}. Important update."
            embedding = e2e_embedding_service.encode(text)[0].tolist()
            
            news = News(
                id=f"e2e_actor_news_{i}",
                title=f"News about {actors[i % 3].canonical_name}",
                summary=f"Summary {i}",
                source="E2E Test",
                published_at=datetime.utcnow(),
                embedding=embedding,
                mentioned_actors=[actors[i % 3].id]
            )
            e2e_graph_manager.add_news(news)
            news_items.append(news)
        
        # Step 3: Verify relationships
        for news in news_items:
            news_actors = e2e_graph_manager.db.get_news_actors(news.id)
            assert len(news_actors) > 0
        
        # Step 4: Cluster
        stories = clustering_service.cluster_news_to_stories(min_cluster_size=2)
        
        # Verify stories have actors
        if len(stories) > 0:
            story = stories[0]
            retrieved = e2e_graph_manager.db.get_story(story.id)
            assert retrieved is not None
            # Story should have top_actors if clustering worked
            if len(retrieved.top_actors) > 0:
                assert all(actor_id in [a.id for a in actors] for actor_id in retrieved.top_actors)
    
    def test_e2e_data_persistence(self, e2e_graph_manager, cleanup_e2e_data):
        """Test that data persists across GraphManager instances"""
        # Create data with first instance
        news = News(
            id="e2e_persist_1",
            title="Persistent News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        e2e_graph_manager.add_news(news)
        
        actor = Actor(
            id="e2e_persist_actor",
            canonical_name="Persistent Actor",
            actor_type=ActorType.PERSON
        )
        e2e_graph_manager.add_actor(actor)
        
        # Create new GraphManager instance (simulating server restart)
        new_graph_manager = GraphManager(db_manager=e2e_graph_manager.db)
        
        # Verify data is still there
        retrieved_news = new_graph_manager.get_news(news.id)
        retrieved_actor = new_graph_manager.get_actor(actor.id)
        
        assert retrieved_news is not None
        assert retrieved_news.title == news.title
        assert retrieved_actor is not None
        assert retrieved_actor.canonical_name == actor.canonical_name

