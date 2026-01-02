"""
Database manager for PostgreSQL + pgvector
Handles all database operations for SDASystem v3
"""
import os
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.extensions import register_adapter, AsIs
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
import numpy as np

from backend.models.entities import (
    News, Actor, Story, Event, ActorRelation, NewsRelation, Domain
)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""
    
    def __init__(self, 
                 dbname: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 min_conn: int = 1,
                 max_conn: int = 10):
        """
        Initialize database manager
        
        Args:
            dbname: Database name (default: from env or 'sdas_db')
            user: Database user (default: from env or 'postgres')
            password: Database password (default: from env)
            host: Database host (default: from env or 'localhost')
            port: Database port (default: from env or 5432)
            min_conn: Minimum connections in pool
            max_conn: Maximum connections in pool
        """
        self.dbname = dbname or os.getenv("POSTGRES_DB", "sdas_db")
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "")
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", "5432"))
        
        # Connection pool
        self.pool: Optional[SimpleConnectionPool] = None
        self._init_pool(min_conn, max_conn)
    
    def _init_pool(self, min_conn: int, max_conn: int):
        """Initialize connection pool"""
        try:
            self.pool = SimpleConnectionPool(
                min_conn, max_conn,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool (context manager)"""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    # --- News operations ---
    
    def save_news(self, news: News) -> None:
        """Save or update news item"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                embedding_str = None
                if news.embedding:
                    embedding_str = '[' + ','.join(map(str, news.embedding)) + ']'
                
                cur.execute("""
                    INSERT INTO news (id, title, summary, full_text, url, source, author,
                                    published_at, created_at, embedding, story_id, duplicate_of,
                                    is_duplicate, is_pinned, editorial_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        full_text = EXCLUDED.full_text,
                        url = EXCLUDED.url,
                        source = EXCLUDED.source,
                        author = EXCLUDED.author,
                        published_at = EXCLUDED.published_at,
                        embedding = EXCLUDED.embedding,
                        story_id = EXCLUDED.story_id,
                        duplicate_of = EXCLUDED.duplicate_of,
                        is_duplicate = EXCLUDED.is_duplicate,
                        is_pinned = EXCLUDED.is_pinned,
                        editorial_notes = EXCLUDED.editorial_notes
                """, (
                    news.id, news.title, news.summary, news.full_text,
                    news.url, news.source, news.author, news.published_at,
                    news.created_at, embedding_str, news.story_id,
                    news.duplicate_of, news.is_duplicate, news.is_pinned,
                    news.editorial_notes
                ))
                
                # Update news_actors
                if news.mentioned_actors:
                    cur.execute("DELETE FROM news_actors WHERE news_id = %s", (news.id,))
                    for actor_id in news.mentioned_actors:
                        cur.execute("""
                            INSERT INTO news_actors (news_id, actor_id, confidence)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (news_id, actor_id) DO NOTHING
                        """, (news.id, actor_id, 0.5))
    
    def get_news(self, news_id: str) -> Optional[News]:
        """Get news by ID"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_news(row)
    
    def get_all_news(self, limit: Optional[int] = None) -> List[News]:
        """Get all news items"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM news ORDER BY published_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                cur.execute(query)
                return [self._row_to_news(row) for row in cur.fetchall()]
    
    def _row_to_news(self, row: Dict) -> News:
        """Convert database row to News object"""
        # Get mentioned_actors
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT actor_id FROM news_actors WHERE news_id = %s", (row['id'],))
                mentioned_actors = [r[0] for r in cur.fetchall()]
        
        # Handle embedding - pgvector returns it as a special type or list
        embedding = None
        if row.get('embedding'):
            try:
                # Try to convert to list directly
                if isinstance(row['embedding'], (list, tuple)):
                    embedding = [float(x) for x in row['embedding']]
                elif hasattr(row['embedding'], 'tolist'):
                    embedding = row['embedding'].tolist()
                elif isinstance(row['embedding'], str):
                    # Parse string representation like "[0.1,0.2,0.3]"
                    embedding = [float(x) for x in row['embedding'].strip('[]').split(',')]
                else:
                    # Try to convert to list
                    embedding = list(row['embedding'])
            except (ValueError, TypeError, AttributeError):
                embedding = None
        
        return News(
            id=row['id'],
            title=row['title'],
            summary=row.get('summary') or '',
            full_text=row.get('full_text') or '',
            url=row.get('url'),
            source=row['source'],
            author=row.get('author'),
            published_at=row['published_at'],
            created_at=row.get('created_at') or datetime.utcnow(),
            embedding=embedding,
            mentioned_actors=mentioned_actors,
            story_id=row.get('story_id'),
            duplicate_of=row.get('duplicate_of'),
            is_duplicate=row.get('is_duplicate', False),
            is_pinned=row.get('is_pinned', False),
            editorial_notes=row.get('editorial_notes') or '',
            domains=[],  # Will be loaded separately if needed
            related_news_ids=[]  # Will be loaded separately if needed
        )
    
    # --- Actor operations ---
    
    def save_actor(self, actor: Actor) -> None:
        """Save or update actor"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                metadata_json = json.dumps(actor.metadata) if actor.metadata else None
                
                cur.execute("""
                    INSERT INTO actors (id, canonical_name, actor_type, wikidata_qid,
                                      metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        canonical_name = EXCLUDED.canonical_name,
                        actor_type = EXCLUDED.actor_type,
                        wikidata_qid = EXCLUDED.wikidata_qid,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                """, (
                    actor.id, actor.canonical_name, 
                    actor.actor_type.value if hasattr(actor.actor_type, 'value') else str(actor.actor_type),
                    actor.wikidata_qid, metadata_json, actor.created_at, actor.updated_at
                ))
                
                # Update aliases
                if actor.aliases:
                    cur.execute("DELETE FROM actor_aliases WHERE actor_id = %s", (actor.id,))
                    for alias_data in actor.aliases:
                        cur.execute("""
                            INSERT INTO actor_aliases (actor_id, alias, alias_type)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (actor_id, alias) DO NOTHING
                        """, (actor.id, alias_data.get('name', ''), alias_data.get('type', 'alias')))
    
    def get_actor(self, actor_id: str) -> Optional[Actor]:
        """Get actor by ID"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM actors WHERE id = %s", (actor_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_actor(row)
    
    def get_all_actors(self) -> List[Actor]:
        """Get all actors"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM actors ORDER BY canonical_name")
                return [self._row_to_actor(row) for row in cur.fetchall()]
    
    def _row_to_actor(self, row: Dict) -> Actor:
        """Convert database row to Actor object"""
        # Get aliases
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alias, alias_type FROM actor_aliases WHERE actor_id = %s", (row['id'],))
                aliases = [{'name': r[0], 'type': r[1]} for r in cur.fetchall()]
        
        metadata = row.get('metadata') or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        from backend.models.entities import ActorType
        return Actor(
            id=row['id'],
            canonical_name=row['canonical_name'],
            actor_type=ActorType(row['actor_type']),
            aliases=aliases,
            wikidata_qid=row.get('wikidata_qid'),
            metadata=metadata,
            created_at=row.get('created_at') or datetime.utcnow(),
            updated_at=row.get('updated_at') or datetime.utcnow()
        )
    
    # --- Story operations ---
    
    def save_story(self, story: Story) -> None:
        """Save or update story"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                bullets_json = json.dumps(story.bullets) if story.bullets else None
                primary_domain = (story.primary_domain.value if hasattr(story.primary_domain, 'value') 
                                 else str(story.primary_domain)) if story.primary_domain else None
                
                cur.execute("""
                    INSERT INTO stories (id, title, summary, bullets, primary_domain,
                                       relevance, cohesion, size, freshness,
                                       is_active, is_editorial, created_at, updated_at,
                                       first_seen, last_activity)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        bullets = EXCLUDED.bullets,
                        primary_domain = EXCLUDED.primary_domain,
                        relevance = EXCLUDED.relevance,
                        cohesion = EXCLUDED.cohesion,
                        size = EXCLUDED.size,
                        freshness = EXCLUDED.freshness,
                        is_active = EXCLUDED.is_active,
                        is_editorial = EXCLUDED.is_editorial,
                        updated_at = EXCLUDED.updated_at,
                        last_activity = EXCLUDED.last_activity
                """, (
                    story.id, story.title, story.summary, bullets_json, primary_domain,
                    story.relevance, story.cohesion, story.size, story.freshness,
                    story.is_active, story.is_editorial, story.created_at, story.updated_at,
                    story.first_seen, story.last_activity
                ))
                
                # Update story_news (only if news exists)
                if story.news_ids:
                    cur.execute("DELETE FROM story_news WHERE story_id = %s", (story.id,))
                    core_ids = set(story.core_news_ids or [])
                    for news_id in story.news_ids:
                        # Check if news exists
                        cur.execute("SELECT 1 FROM news WHERE id = %s", (news_id,))
                        if cur.fetchone():
                            cur.execute("""
                                INSERT INTO story_news (story_id, news_id, is_core)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (story_id, news_id) DO NOTHING
                            """, (story.id, news_id, news_id in core_ids))
                
                # Update story_actors (top_actors)
                if story.top_actors:
                    cur.execute("DELETE FROM story_actors WHERE story_id = %s", (story.id,))
                    # Count mentions for each actor
                    actor_counts = {}
                    for news_id in story.news_ids:
                        cur.execute("SELECT actor_id FROM news_actors WHERE news_id = %s", (news_id,))
                        for (actor_id,) in cur.fetchall():
                            actor_counts[actor_id] = actor_counts.get(actor_id, 0) + 1
                    
                    for actor_id in story.top_actors:
                        # Check if actor exists
                        cur.execute("SELECT 1 FROM actors WHERE id = %s", (actor_id,))
                        if cur.fetchone():
                            count = actor_counts.get(actor_id, 1)
                            cur.execute("""
                                INSERT INTO story_actors (story_id, actor_id, mention_count)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (story_id, actor_id) DO UPDATE SET mention_count = EXCLUDED.mention_count
                            """, (story.id, actor_id, count))
                
                # Update story_events
                if story.event_ids:
                    cur.execute("DELETE FROM story_events WHERE story_id = %s", (story.id,))
                    for event_id in story.event_ids:
                        cur.execute("""
                            INSERT INTO story_events (story_id, event_id)
                            VALUES (%s, %s)
                            ON CONFLICT (story_id, event_id) DO NOTHING
                        """, (story.id, event_id))
    
    def get_story(self, story_id: str) -> Optional[Story]:
        """Get story by ID"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM stories WHERE id = %s", (story_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_story(row)
    
    def get_all_stories(self, active_only: bool = True) -> List[Story]:
        """Get all stories"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM stories"
                if active_only:
                    query += " WHERE is_active = TRUE"
                query += " ORDER BY relevance DESC, updated_at DESC"
                cur.execute(query)
                return [self._row_to_story(row) for row in cur.fetchall()]
    
    def _row_to_story(self, row: Dict) -> Story:
        """Convert database row to Story object"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get news_ids
                cur.execute("SELECT news_id, is_core FROM story_news WHERE story_id = %s", (row['id'],))
                story_news_data = cur.fetchall()
                news_ids = [r[0] for r in story_news_data]
                core_news_ids = [r[0] for r in story_news_data if r[1]]
                
                # Get top_actors (sorted by mention_count)
                cur.execute("""
                    SELECT actor_id FROM story_actors
                    WHERE story_id = %s
                    ORDER BY mention_count DESC
                """, (row['id'],))
                top_actors = [r[0] for r in cur.fetchall()]
                
                # Get event_ids
                cur.execute("SELECT event_id FROM story_events WHERE story_id = %s", (row['id'],))
                event_ids = [r[0] for r in cur.fetchall()]
                
                # Get domains
                cur.execute("SELECT domain_id FROM story_domains WHERE story_id = %s", (row['id'],))
                domains = [r[0] for r in cur.fetchall()]
        
        bullets = row.get('bullets') or []
        if isinstance(bullets, str):
            bullets = json.loads(bullets)
        
        from backend.models.entities import DomainCategory
        primary_domain = None
        if row.get('primary_domain'):
            primary_domain = DomainCategory(row['primary_domain'])
        
        return Story(
            id=row['id'],
            title=row['title'],
            summary=row.get('summary') or '',
            bullets=bullets,
            news_ids=news_ids,
            core_news_ids=core_news_ids,
            top_actors=top_actors,
            event_ids=event_ids,
            domains=domains,
            primary_domain=primary_domain,
            relevance=row.get('relevance', 0.5),
            cohesion=row.get('cohesion', 0.5),
            size=row.get('size', 0),
            freshness=row.get('freshness', 1.0),
            created_at=row.get('created_at') or datetime.utcnow(),
            updated_at=row.get('updated_at') or datetime.utcnow(),
            first_seen=row.get('first_seen') or datetime.utcnow(),
            last_activity=row.get('last_activity') or datetime.utcnow(),
            is_active=row.get('is_active', True),
            is_editorial=row.get('is_editorial', False)
        )
    
    # --- Event operations ---
    
    def save_event(self, event: Event) -> None:
        """Save or update event"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO events (id, news_id, story_id, event_type, title, description,
                                      event_date, extracted_at, source_trust, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        news_id = EXCLUDED.news_id,
                        story_id = EXCLUDED.story_id,
                        event_type = EXCLUDED.event_type,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        event_date = EXCLUDED.event_date,
                        source_trust = EXCLUDED.source_trust,
                        confidence = EXCLUDED.confidence
                """, (
                    event.id, event.news_id, event.story_id, 
                    (event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)),
                    event.title, event.description, event.event_date, event.extracted_at,
                    event.source_trust, event.confidence
                ))
                
                # Update event_actors
                if event.actors:
                    cur.execute("DELETE FROM event_actors WHERE event_id = %s", (event.id,))
                    for actor_id in event.actors:
                        cur.execute("""
                            INSERT INTO event_actors (event_id, actor_id)
                            VALUES (%s, %s)
                            ON CONFLICT (event_id, actor_id) DO NOTHING
                        """, (event.id, actor_id))
                
                # Update story_events relationship if story_id is set
                if event.story_id:
                    cur.execute("""
                        INSERT INTO story_events (story_id, event_id)
                        VALUES (%s, %s)
                        ON CONFLICT (story_id, event_id) DO NOTHING
                    """, (event.story_id, event.id))
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM events WHERE id = %s", (event_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_event(row)
    
    def get_story_events(self, story_id: str) -> List[Event]:
        """Get all events for a story"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.* FROM events e
                    INNER JOIN story_events se ON e.id = se.event_id
                    WHERE se.story_id = %s
                    ORDER BY e.event_date ASC
                """, (story_id,))
                return [self._row_to_event(row) for row in cur.fetchall()]
    
    def _row_to_event(self, row: Dict) -> Event:
        """Convert database row to Event object"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT actor_id FROM event_actors WHERE event_id = %s", (row['id'],))
                actors = [r[0] for r in cur.fetchall()]
        
        from backend.models.entities import EventType
        return Event(
            id=row['id'],
            news_id=row['news_id'],
            story_id=row.get('story_id'),
            event_type=EventType(row['event_type']),
            title=row['title'],
            description=row.get('description') or '',
            event_date=row['event_date'],
            extracted_at=row.get('extracted_at') or datetime.utcnow(),
            actors=actors,
            source_trust=row.get('source_trust', 0.5),
            confidence=row.get('confidence', 0.7)
        )
    
    # --- Vector search ---
    
    def find_similar_news(self, embedding: List[float], threshold: float = 0.6, limit: int = 10) -> List[Tuple[str, float]]:
        """
        Find similar news using pgvector cosine distance
        
        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity threshold
            limit: Maximum number of results
        
        Returns:
            List of (news_id, similarity) tuples
        """
        if not embedding:
            return []
        
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Use cosine distance (1 - cosine similarity)
                # We want similarity, so we use 1 - distance
                cur.execute("""
                    SELECT id, 1 - (embedding <=> %s::vector) as similarity
                    FROM news
                    WHERE embedding IS NOT NULL
                      AND 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (embedding_str, embedding_str, threshold, embedding_str, limit))
                
                return [(row[0], float(row[1])) for row in cur.fetchall()]
    
    def compute_news_similarities(self, threshold: float = 0.6) -> List[NewsRelation]:
        """
        Compute similarities between all news items using pgvector
        More efficient than sklearn for large datasets
        """
        relations = []
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get all news with embeddings
                cur.execute("SELECT id, embedding FROM news WHERE embedding IS NOT NULL")
                news_with_embeddings = cur.fetchall()
                
                if len(news_with_embeddings) < 2:
                    return relations
                
                # For each news, find similar ones
                for news_id, embedding in news_with_embeddings:
                    if embedding is None:
                        continue
                    
                    # Convert embedding to list if it's numpy array
                    if isinstance(embedding, np.ndarray):
                        embedding_list = embedding.tolist()
                    elif isinstance(embedding, (list, tuple)):
                        embedding_list = list(embedding)
                    else:
                        continue
                    
                    # Format as PostgreSQL array string for vector type
                    embedding_str = '[' + ','.join(map(str, embedding_list)) + ']'
                    
                    # Find similar news (excluding self)
                    cur.execute("""
                        SELECT id, 1 - (embedding <=> %s::vector) as similarity
                        FROM news
                        WHERE id != %s
                          AND embedding IS NOT NULL
                          AND 1 - (embedding <=> %s::vector) >= %s
                        ORDER BY embedding <=> %s::vector
                    """, (embedding_str, news_id, embedding_str, threshold, embedding_str))
                    
                    for similar_id, similarity in cur.fetchall():
                        # Avoid duplicates (only store one direction)
                        if news_id < similar_id:
                            relation = NewsRelation(
                                source_news_id=news_id,
                                target_news_id=similar_id,
                                similarity=float(similarity),
                                weight=float(similarity),
                                is_editorial=False,
                                created_at=datetime.utcnow()
                            )
                            relations.append(relation)
                            
                            # Save to database
                            cur.execute("""
                                INSERT INTO news_relations (source_news_id, target_news_id, similarity, weight, is_editorial, created_at)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (source_news_id, target_news_id) DO UPDATE SET
                                    similarity = EXCLUDED.similarity,
                                    weight = EXCLUDED.weight
                            """, (
                                relation.source_news_id, relation.target_news_id,
                                relation.similarity, relation.weight,
                                relation.is_editorial, relation.created_at
                            ))
        
        return relations
    
    # --- Helper methods ---
    
    def get_news_actors(self, news_id: str) -> List[str]:
        """Get all actors for a news item"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT actor_id FROM news_actors WHERE news_id = %s", (news_id,))
                return [r[0] for r in cur.fetchall()]
    
    def get_actor_news(self, actor_id: str) -> List[str]:
        """Get all news mentioning an actor"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT news_id FROM news_actors WHERE actor_id = %s", (actor_id,))
                return [r[0] for r in cur.fetchall()]
    
    def close(self):
        """Close connection pool"""
        if self.pool:
            self.pool.closeall()

