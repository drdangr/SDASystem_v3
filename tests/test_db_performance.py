"""
Performance tests for database operations
Benchmarks vector search and data loading performance
"""
import sys
import os
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime
import numpy as np

from backend.services.database_manager import DatabaseManager
from backend.services.graph_manager import GraphManager
from backend.models.entities import News, Actor, ActorType


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


class TestVectorSearchPerformance:
    """Performance tests for vector search"""
    
    def test_vector_search_performance_small(self, test_db):
        """Test vector search performance on small dataset (10 items)"""
        # Create test news
        news_items = []
        for i in range(10):
            embedding = [0.1 + (i * 0.01)] * 384
            news = News(
                id=f"perf_news_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=embedding
            )
            test_db.save_news(news)
            news_items.append(news)
        
        # Benchmark search
        query_embedding = [0.1] * 384
        start = time.time()
        results = test_db.find_similar_news(query_embedding, threshold=0.9, limit=10)
        elapsed = time.time() - start
        
        # Should be fast (< 1 second for 10 items)
        assert elapsed < 1.0
        assert len(results) > 0
        
        # Cleanup
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM news WHERE id LIKE 'perf_%'")
    
    def test_compute_similarities_performance(self, test_db):
        """Test compute_news_similarities performance"""
        # Create test news
        news_items = []
        for i in range(20):
            embedding = [0.1 + (i * 0.01)] * 384
            news = News(
                id=f"perf_sim_{i}",
                title=f"News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=embedding
            )
            test_db.save_news(news)
            news_items.append(news)
        
        # Benchmark
        start = time.time()
        relations = test_db.compute_news_similarities(threshold=0.9)
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 5 seconds for 20 items)
        assert elapsed < 5.0
        assert isinstance(relations, list)
        
        # Cleanup
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM news_relations WHERE source_news_id LIKE 'perf_%' OR target_news_id LIKE 'perf_%'")
                cur.execute("DELETE FROM news WHERE id LIKE 'perf_%'")


class TestDataLoadingPerformance:
    """Performance tests for data loading"""
    
    def test_bulk_insert_performance(self, test_db):
        """Test bulk insert performance"""
        # Create test data
        news_items = []
        for i in range(50):
            news = News(
                id=f"bulk_news_{i}",
                title=f"Bulk News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            news_items.append(news)
        
        # Benchmark insert
        start = time.time()
        for news in news_items:
            test_db.save_news(news)
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 10 seconds for 50 items)
        assert elapsed < 10.0
        
        # Verify all inserted
        all_news = test_db.get_all_news()
        bulk_news = [n for n in all_news if n.id.startswith("bulk_")]
        assert len(bulk_news) == 50
        
        # Cleanup
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM news WHERE id LIKE 'bulk_%'")
    
    def test_get_all_news_performance(self, test_db):
        """Test get_all_news performance"""
        # Create test data
        for i in range(30):
            news = News(
                id=f"load_news_{i}",
                title=f"Load News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            test_db.save_news(news)
        
        # Benchmark load
        start = time.time()
        all_news = test_db.get_all_news()
        elapsed = time.time() - start
        
        # Should be fast (< 2 seconds for 30 items)
        assert elapsed < 2.0
        
        # Cleanup
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM news WHERE id LIKE 'load_%'")


class TestGraphManagerPerformance:
    """Performance tests for GraphManager with database"""
    
    def test_graph_manager_add_multiple_news(self, test_db):
        """Test GraphManager performance with multiple news"""
        graph_manager = GraphManager(db_manager=test_db)
        
        # Create test data
        news_items = []
        for i in range(20):
            news = News(
                id=f"gm_perf_{i}",
                title=f"Graph News {i}",
                summary=f"Summary {i}",
                source="Test",
                published_at=datetime.utcnow(),
                embedding=[0.1] * 384
            )
            news_items.append(news)
        
        # Benchmark
        start = time.time()
        for news in news_items:
            graph_manager.add_news(news)
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 5.0
        
        # Verify
        assert len(graph_manager.news_graph.nodes()) >= 20
        
        # Cleanup
        with test_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM news WHERE id LIKE 'gm_perf_%'")

