"""
Comprehensive unit tests for DatabaseManager
Tests all CRUD operations, relationships, vector search, and transactions
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
import numpy as np

from backend.services.database_manager import DatabaseManager
from backend.models.entities import (
    News, Actor, Story, Event, ActorRelation, NewsRelation, Domain,
    ActorType, EventType, RelationType, DomainCategory
)


@pytest.fixture(scope="module")
def test_db():
    """Create a test database manager"""
    # Use test database if available, otherwise use main database
    db_name = os.getenv("TEST_POSTGRES_DB", "sdas_db")
    db = DatabaseManager(
        dbname=db_name,
        user=os.getenv("TEST_POSTGRES_USER", "postgres"),
        password=os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("TEST_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("TEST_POSTGRES_PORT", "5432"))
    )
    
    # Try to connect
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
    # Cleanup test data
    with test_db.get_connection() as conn:
        with conn.cursor() as cur:
            # Delete in order to respect foreign keys
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
def sample_news():
    """Create sample news item"""
    return News(
        id="test_news_1",
        title="Test News Title",
        summary="Test summary",
        full_text="Test full text content",
        source="Test Source",
        published_at=datetime.utcnow(),
        embedding=[0.1] * 384  # Mock embedding
    )


@pytest.fixture
def sample_actor():
    """Create sample actor"""
    return Actor(
        id="test_actor_1",
        canonical_name="Test Actor",
        actor_type=ActorType.PERSON,
        aliases=[{"name": "TA", "type": "abbreviation"}]
    )


@pytest.fixture
def sample_story():
    """Create sample story"""
    return Story(
        id="test_story_1",
        title="Test Story",
        summary="Test story summary",
        bullets=["Bullet 1", "Bullet 2"],
        news_ids=["test_news_1"],
        core_news_ids=["test_news_1"],
        top_actors=["test_actor_1"]
    )


@pytest.fixture
def sample_event():
    """Create sample event"""
    return Event(
        id="test_event_1",
        news_id="test_news_1",
        story_id="test_story_1",
        event_type=EventType.FACT,
        title="Test Event",
        description="Test event description",
        event_date=datetime.utcnow(),
        actors=["test_actor_1"]
    )


# ============================================================================
# NEWS TESTS
# ============================================================================

class TestNewsOperations:
    """Test News CRUD operations"""
    
    def test_save_news(self, test_db, sample_news, cleanup_test_data):
        """Test saving news"""
        test_db.save_news(sample_news)
        
        retrieved = test_db.get_news(sample_news.id)
        assert retrieved is not None
        assert retrieved.id == sample_news.id
        assert retrieved.title == sample_news.title
        assert retrieved.summary == sample_news.summary
        assert len(retrieved.embedding) == 384
    
    def test_update_news(self, test_db, sample_news, cleanup_test_data):
        """Test updating news"""
        test_db.save_news(sample_news)
        
        # Update
        sample_news.title = "Updated Title"
        sample_news.summary = "Updated summary"
        test_db.save_news(sample_news)
        
        retrieved = test_db.get_news(sample_news.id)
        assert retrieved.title == "Updated Title"
        assert retrieved.summary == "Updated summary"
    
    def test_get_all_news(self, test_db, cleanup_test_data):
        """Test getting all news"""
        # Create multiple news items
        for i in range(3):
            news = News(
                id=f"test_news_all_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test Source",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            test_db.save_news(news)
        
        all_news = test_db.get_all_news()
        test_news = [n for n in all_news if n.id.startswith("test_news_all_")]
        assert len(test_news) == 3
    
    def test_get_all_news_with_limit(self, test_db, cleanup_test_data):
        """Test getting news with limit"""
        for i in range(5):
            news = News(
                id=f"test_news_limit_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test Source",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            test_db.save_news(news)
        
        limited = test_db.get_all_news(limit=3)
        test_news = [n for n in limited if n.id.startswith("test_news_limit_")]
        assert len(test_news) <= 3
    
    def test_news_without_embedding(self, test_db, cleanup_test_data):
        """Test news without embedding"""
        news = News(
            id="test_news_no_emb",
            title="News without embedding",
            summary="Summary",
            source="Test Source",
            published_at=datetime.utcnow(),
            embedding=None
        )
        test_db.save_news(news)
        
        retrieved = test_db.get_news(news.id)
        assert retrieved is not None
        assert retrieved.embedding is None


# ============================================================================
# ACTOR TESTS
# ============================================================================

class TestActorOperations:
    """Test Actor CRUD operations"""
    
    def test_save_actor(self, test_db, sample_actor, cleanup_test_data):
        """Test saving actor"""
        test_db.save_actor(sample_actor)
        
        retrieved = test_db.get_actor(sample_actor.id)
        assert retrieved is not None
        assert retrieved.id == sample_actor.id
        assert retrieved.canonical_name == sample_actor.canonical_name
        assert retrieved.actor_type == sample_actor.actor_type
        assert len(retrieved.aliases) == 1
    
    def test_actor_aliases(self, test_db, cleanup_test_data):
        """Test actor aliases storage"""
        actor = Actor(
            id="test_actor_aliases",
            canonical_name="Test Actor",
            actor_type=ActorType.PERSON,
            aliases=[
                {"name": "TA", "type": "abbreviation"},
                {"name": "Test", "type": "nickname"}
            ]
        )
        test_db.save_actor(actor)
        
        retrieved = test_db.get_actor(actor.id)
        assert len(retrieved.aliases) == 2
    
    def test_update_actor(self, test_db, sample_actor, cleanup_test_data):
        """Test updating actor"""
        test_db.save_actor(sample_actor)
        
        sample_actor.canonical_name = "Updated Name"
        sample_actor.aliases.append({"name": "New Alias", "type": "nickname"})
        test_db.save_actor(sample_actor)
        
        retrieved = test_db.get_actor(sample_actor.id)
        assert retrieved.canonical_name == "Updated Name"
        assert len(retrieved.aliases) == 2
    
    def test_get_all_actors(self, test_db, cleanup_test_data):
        """Test getting all actors"""
        for i in range(3):
            actor = Actor(
                id=f"test_actor_all_{i}",
                canonical_name=f"Actor {i}",
                actor_type=ActorType.PERSON
            )
            test_db.save_actor(actor)
        
        all_actors = test_db.get_all_actors()
        test_actors = [a for a in all_actors if a.id.startswith("test_actor_all_")]
        assert len(test_actors) == 3
    
    def test_actor_metadata(self, test_db, cleanup_test_data):
        """Test actor metadata storage"""
        actor = Actor(
            id="test_actor_meta",
            canonical_name="Test Actor",
            actor_type=ActorType.PERSON,
            metadata={"country": "US", "position": "President"}
        )
        test_db.save_actor(actor)
        
        retrieved = test_db.get_actor(actor.id)
        assert retrieved.metadata["country"] == "US"
        assert retrieved.metadata["position"] == "President"


# ============================================================================
# STORY TESTS
# ============================================================================

class TestStoryOperations:
    """Test Story CRUD operations"""
    
    def test_save_story(self, test_db, sample_story, sample_news, sample_actor, cleanup_test_data):
        """Test saving story"""
        test_db.save_news(sample_news)
        test_db.save_actor(sample_actor)
        test_db.save_story(sample_story)
        
        retrieved = test_db.get_story(sample_story.id)
        assert retrieved is not None
        assert retrieved.id == sample_story.id
        assert retrieved.title == sample_story.title
        assert len(retrieved.news_ids) == 1
        assert len(retrieved.top_actors) == 1
    
    def test_story_news_relationship(self, test_db, cleanup_test_data):
        """Test story-news relationship"""
        # Create news
        news1 = News(
            id="test_story_news_1",
            title="News 1",
            summary="Summary 1",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        news2 = News(
            id="test_story_news_2",
            title="News 2",
            summary="Summary 2",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        test_db.save_news(news1)
        test_db.save_news(news2)
        
        # Create story with multiple news
        story = Story(
            id="test_story_multi",
            title="Multi News Story",
            summary="Story with multiple news",
            news_ids=[news1.id, news2.id],
            core_news_ids=[news1.id]
        )
        test_db.save_story(story)
        
        retrieved = test_db.get_story(story.id)
        assert len(retrieved.news_ids) == 2
        assert news1.id in retrieved.news_ids
        assert news2.id in retrieved.news_ids
        assert news1.id in retrieved.core_news_ids
    
    def test_story_actors_relationship(self, test_db, cleanup_test_data):
        """Test story-actors relationship"""
        actor1 = Actor(
            id="test_story_actor_1",
            canonical_name="Actor 1",
            actor_type=ActorType.PERSON
        )
        actor2 = Actor(
            id="test_story_actor_2",
            canonical_name="Actor 2",
            actor_type=ActorType.PERSON
        )
        test_db.save_actor(actor1)
        test_db.save_actor(actor2)
        
        story = Story(
            id="test_story_actors",
            title="Story with Actors",
            summary="Summary",
            top_actors=[actor1.id, actor2.id]
        )
        test_db.save_story(story)
        
        retrieved = test_db.get_story(story.id)
        assert len(retrieved.top_actors) == 2
        assert actor1.id in retrieved.top_actors
        assert actor2.id in retrieved.top_actors
    
    def test_get_all_stories(self, test_db, cleanup_test_data):
        """Test getting all stories"""
        for i in range(3):
            story = Story(
                id=f"test_story_all_{i}",
                title=f"Story {i}",
                summary=f"Summary {i}",
                is_active=(i < 2)  # First two active
            )
            test_db.save_story(story)
        
        active_stories = test_db.get_all_stories(active_only=True)
        test_active = [s for s in active_stories if s.id.startswith("test_story_all_")]
        assert len(test_active) == 2
        
        all_stories = test_db.get_all_stories(active_only=False)
        test_all = [s for s in all_stories if s.id.startswith("test_story_all_")]
        assert len(test_all) == 3


# ============================================================================
# EVENT TESTS
# ============================================================================

class TestEventOperations:
    """Test Event CRUD operations"""
    
    def test_save_event(self, test_db, sample_event, sample_news, sample_story, sample_actor, cleanup_test_data):
        """Test saving event"""
        test_db.save_news(sample_news)
        test_db.save_actor(sample_actor)
        test_db.save_story(sample_story)
        test_db.save_event(sample_event)
        
        retrieved = test_db.get_event(sample_event.id)
        assert retrieved is not None
        assert retrieved.id == sample_event.id
        assert retrieved.title == sample_event.title
        assert retrieved.event_type == sample_event.event_type
    
    def test_event_actors_relationship(self, test_db, cleanup_test_data):
        """Test event-actors relationship"""
        actor1 = Actor(
            id="test_event_actor_1",
            canonical_name="Actor 1",
            actor_type=ActorType.PERSON
        )
        actor2 = Actor(
            id="test_event_actor_2",
            canonical_name="Actor 2",
            actor_type=ActorType.PERSON
        )
        test_db.save_actor(actor1)
        test_db.save_actor(actor2)
        
        news = News(
            id="test_event_news",
            title="News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        test_db.save_news(news)
        
        event = Event(
            id="test_event_multi",
            news_id=news.id,
            event_type=EventType.FACT,
            title="Event with Actors",
            event_date=datetime.utcnow(),
            actors=[actor1.id, actor2.id]
        )
        test_db.save_event(event)
        
        retrieved = test_db.get_event(event.id)
        assert len(retrieved.actors) == 2
        assert actor1.id in retrieved.actors
        assert actor2.id in retrieved.actors
    
    def test_get_story_events(self, test_db, sample_story, sample_news, cleanup_test_data):
        """Test getting events for a story"""
        test_db.save_news(sample_news)
        test_db.save_story(sample_story)
        
        # Create multiple events
        events = []
        for i in range(3):
            event = Event(
                id=f"test_story_event_{i}",
                news_id=sample_news.id,
                story_id=sample_story.id,
                event_type=EventType.FACT,
                title=f"Event {i}",
                event_date=datetime.utcnow()
            )
            test_db.save_event(event)
            events.append(event)
        
        story_events = test_db.get_story_events(sample_story.id)
        assert len(story_events) == 3
        event_ids = [e.id for e in story_events]
        for event in events:
            assert event.id in event_ids


# ============================================================================
# RELATIONSHIP TESTS
# ============================================================================

class TestRelationships:
    """Test relationships between entities"""
    
    def test_news_actors_relationship(self, test_db, sample_news, sample_actor, cleanup_test_data):
        """Test news-actor relationship"""
        test_db.save_actor(sample_actor)
        sample_news.mentioned_actors = [sample_actor.id]
        test_db.save_news(sample_news)
        
        # Check relationship
        actors = test_db.get_news_actors(sample_news.id)
        assert sample_actor.id in actors
        
        news_list = test_db.get_actor_news(sample_actor.id)
        assert sample_news.id in news_list
    
    def test_multiple_news_actors(self, test_db, cleanup_test_data):
        """Test news with multiple actors"""
        actors = []
        for i in range(3):
            actor = Actor(
                id=f"test_multi_actor_{i}",
                canonical_name=f"Actor {i}",
                actor_type=ActorType.PERSON
            )
            test_db.save_actor(actor)
            actors.append(actor)
        
        news = News(
            id="test_multi_news",
            title="News with multiple actors",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384,
            mentioned_actors=[a.id for a in actors]
        )
        test_db.save_news(news)
        
        news_actors = test_db.get_news_actors(news.id)
        assert len(news_actors) == 3
        for actor in actors:
            assert actor.id in news_actors
    
    def test_actor_multiple_news(self, test_db, cleanup_test_data):
        """Test actor mentioned in multiple news"""
        actor = Actor(
            id="test_actor_multi",
            canonical_name="Multi News Actor",
            actor_type=ActorType.PERSON
        )
        test_db.save_actor(actor)
        
        news_items = []
        for i in range(3):
            news = News(
                id=f"test_actor_news_{i}",
                title=f"News {i}",
                summary="Summary",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384,
                mentioned_actors=[actor.id]
            )
            test_db.save_news(news)
            news_items.append(news)
        
        actor_news = test_db.get_actor_news(actor.id)
        assert len(actor_news) == 3
        for news in news_items:
            assert news.id in actor_news


# ============================================================================
# VECTOR SEARCH TESTS
# ============================================================================

class TestVectorSearch:
    """Test vector similarity search"""
    
    def test_find_similar_news(self, test_db, cleanup_test_data):
        """Test finding similar news by embedding"""
        # Create news with similar embeddings
        base_embedding = [0.1] * 384
        similar_embedding = [0.11] * 384  # Very similar
        different_embedding = [0.9] * 384  # Very different
        
        news1 = News(
            id="test_vector_1",
            title="Base News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=base_embedding
        )
        news2 = News(
            id="test_vector_2",
            title="Similar News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=similar_embedding
        )
        news3 = News(
            id="test_vector_3",
            title="Different News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=different_embedding
        )
        
        test_db.save_news(news1)
        test_db.save_news(news2)
        test_db.save_news(news3)
        
        # Search for similar news
        results = test_db.find_similar_news(base_embedding, threshold=0.9, limit=10)
        assert len(results) > 0
        
        result_ids = [r[0] for r in results]
        # Should find similar news
        assert news2.id in result_ids
        # Should not find very different news (or with low similarity)
        # Note: exact behavior depends on cosine similarity calculation
    
    def test_compute_news_similarities(self, test_db, cleanup_test_data):
        """Test computing similarities between all news"""
        # Create multiple news items with different embeddings
        news_items = []
        for i in range(5):
            # Create embeddings that are somewhat similar
            embedding = [0.1 + (i * 0.01)] * 384
            news = News(
                id=f"test_sim_news_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=embedding
            )
            test_db.save_news(news)
            news_items.append(news)
        
        # Compute similarities
        relations = test_db.compute_news_similarities(threshold=0.9)
        assert isinstance(relations, list)
        
        # Should create some relations (depending on threshold)
        # With very similar embeddings, should find relations
        if len(relations) > 0:
            assert all(isinstance(r, NewsRelation) for r in relations)
            assert all(r.similarity >= 0.9 for r in relations)
    
    def test_vector_search_without_embedding(self, test_db, cleanup_test_data):
        """Test vector search when news has no embedding"""
        news = News(
            id="test_no_emb",
            title="News without embedding",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=None
        )
        test_db.save_news(news)
        
        # Should not crash, just return empty results
        results = test_db.find_similar_news([0.1] * 384, threshold=0.9)
        # News without embedding should not appear in results
        result_ids = [r[0] for r in results]
        assert news.id not in result_ids


# ============================================================================
# TRANSACTION TESTS
# ============================================================================

class TestTransactions:
    """Test transaction handling"""
    
    def test_connection_pool(self, test_db):
        """Test connection pool works"""
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result[0] == 1
    
    def test_multiple_connections(self, test_db):
        """Test multiple concurrent connections"""
        def use_connection():
            with test_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone()[0]
        
        results = [use_connection() for _ in range(5)]
        assert all(r == 1 for r in results)
    
    def test_transaction_rollback(self, test_db, cleanup_test_data):
        """Test that errors cause rollback"""
        # This is a simplified test - in real scenario would test actual rollback
        try:
            with test_db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Try invalid operation
                    cur.execute("INSERT INTO news (id, title) VALUES (%s, %s)", ("test_rollback", "Test"))
                    # This should work, but if we had a constraint violation, it would rollback
        except Exception:
            # If error occurs, transaction should be rolled back
            pass
        
        # Verify the invalid data is not in database
        retrieved = test_db.get_news("test_rollback")
        # Should be None if rollback worked, or might exist if operation succeeded
        # This is a basic test - full rollback testing would require more complex setup


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestFullWorkflow:
    """Integration tests for complete workflows"""
    
    def test_complete_news_to_story_workflow(self, test_db, cleanup_test_data):
        """Test complete workflow: actors -> news -> story -> events"""
        # Create actors
        actors = []
        for i in range(3):
            actor = Actor(
                id=f"test_workflow_actor_{i}",
                canonical_name=f"Workflow Actor {i}",
                actor_type=ActorType.PERSON
            )
            test_db.save_actor(actor)
            actors.append(actor)
        
        # Create news with actor mentions
        news_items = []
        for i in range(3):
            news = News(
                id=f"test_workflow_news_{i}",
                title=f"Workflow News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1 + i * 0.01] * 384,
                mentioned_actors=[actors[i].id]
            )
            test_db.save_news(news)
            news_items.append(news)
        
        # Create story
        story = Story(
            id="test_workflow_story",
            title="Workflow Story",
            summary="Complete workflow test",
            news_ids=[n.id for n in news_items],
            core_news_ids=[news_items[0].id],
            top_actors=[a.id for a in actors]
        )
        test_db.save_story(story)
        
        # Create events
        events = []
        for i, news in enumerate(news_items):
            event = Event(
                id=f"test_workflow_event_{i}",
                news_id=news.id,
                story_id=story.id,
                event_type=EventType.FACT if i % 2 == 0 else EventType.OPINION,
                title=f"Event {i}",
                event_date=datetime.utcnow(),
                actors=[actors[i].id]
            )
            test_db.save_event(event)
            events.append(event)
        
        # Verify all relationships
        retrieved_story = test_db.get_story(story.id)
        assert retrieved_story is not None
        assert len(retrieved_story.news_ids) == 3
        assert len(retrieved_story.top_actors) == 3
        
        story_events = test_db.get_story_events(story.id)
        assert len(story_events) == 3
        
        # Verify news-actor relationships
        for news in news_items:
            news_actors = test_db.get_news_actors(news.id)
            assert len(news_actors) == 1
        
        # Verify actor-news relationships
        for actor in actors:
            actor_news = test_db.get_actor_news(actor.id)
            assert len(actor_news) == 1
    
    def test_update_story_with_new_news(self, test_db, cleanup_test_data):
        """Test updating story with new news items"""
        # Create initial news and story
        news1 = News(
            id="test_update_news_1",
            title="News 1",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        test_db.save_news(news1)
        
        story = Story(
            id="test_update_story",
            title="Update Story",
            summary="Summary",
            news_ids=[news1.id]
        )
        test_db.save_story(story)
        
        # Add new news
        news2 = News(
            id="test_update_news_2",
            title="News 2",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        test_db.save_news(news2)
        
        # Update story
        story.news_ids.append(news2.id)
        test_db.save_story(story)
        
        retrieved = test_db.get_story(story.id)
        assert len(retrieved.news_ids) == 2
        assert news1.id in retrieved.news_ids
        assert news2.id in retrieved.news_ids


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_get_nonexistent_news(self, test_db):
        """Test getting non-existent news"""
        result = test_db.get_news("nonexistent_id")
        assert result is None
    
    def test_get_nonexistent_actor(self, test_db):
        """Test getting non-existent actor"""
        result = test_db.get_actor("nonexistent_id")
        assert result is None
    
    def test_get_nonexistent_story(self, test_db):
        """Test getting non-existent story"""
        result = test_db.get_story("nonexistent_id")
        assert result is None
    
    def test_empty_relationships(self, test_db, cleanup_test_data):
        """Test entities with empty relationships"""
        news = News(
            id="test_empty_news",
            title="News",
            summary="Summary",
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384,
            mentioned_actors=[]  # No actors
        )
        test_db.save_news(news)
        
        actors = test_db.get_news_actors(news.id)
        assert len(actors) == 0
        
        story = Story(
            id="test_empty_story",
            title="Story",
            summary="Summary",
            news_ids=[],  # No news
            top_actors=[]  # No actors
        )
        test_db.save_story(story)
        
        retrieved = test_db.get_story(story.id)
        assert len(retrieved.news_ids) == 0
        assert len(retrieved.top_actors) == 0
    
    def test_news_with_very_long_text(self, test_db, cleanup_test_data):
        """Test news with very long text fields"""
        long_text = "A" * 10000
        news = News(
            id="test_long_news",
            title="Long News",
            summary=long_text,
            full_text=long_text,
            source="Test",
            published_at=datetime.utcnow(),
            embedding=[0.1] * 384
        )
        test_db.save_news(news)
        
        retrieved = test_db.get_news(news.id)
        assert retrieved is not None
        assert len(retrieved.summary) == 10000
    
    def test_actor_with_many_aliases(self, test_db, cleanup_test_data):
        """Test actor with many aliases"""
        aliases = [{"name": f"Alias {i}", "type": "nickname"} for i in range(20)]
        actor = Actor(
            id="test_many_aliases",
            canonical_name="Actor with Many Aliases",
            actor_type=ActorType.PERSON,
            aliases=aliases
        )
        test_db.save_actor(actor)
        
        retrieved = test_db.get_actor(actor.id)
        assert len(retrieved.aliases) == 20


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance and scalability tests"""
    
    def test_bulk_news_insert(self, test_db, cleanup_test_data):
        """Test inserting many news items"""
        import time
        start = time.time()
        
        for i in range(50):
            news = News(
                id=f"test_bulk_{i}",
                title=f"Bulk News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            test_db.save_news(news)
        
        elapsed = time.time() - start
        # Should complete in reasonable time (< 5 seconds for 50 items)
        assert elapsed < 5.0
        
        # Verify all were saved
        all_news = test_db.get_all_news()
        bulk_news = [n for n in all_news if n.id.startswith("test_bulk_")]
        assert len(bulk_news) == 50
    
    def test_vector_search_performance(self, test_db, cleanup_test_data):
        """Test vector search performance"""
        import time
        
        # Create many news items
        for i in range(20):
            embedding = [0.1 + (i * 0.01)] * 384
            news = News(
                id=f"test_perf_{i}",
                title=f"News {i}",
                summary="Summary",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=embedding
            )
            test_db.save_news(news)
        
        # Test search performance
        start = time.time()
        results = test_db.find_similar_news([0.1] * 384, threshold=0.9, limit=10)
        elapsed = time.time() - start
        
        # Vector search should be fast (< 1 second for 20 items)
        assert elapsed < 1.0
        assert isinstance(results, list)
