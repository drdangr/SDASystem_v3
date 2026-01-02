"""
Graph manager for two-layer graph: News and Actors
Now uses PostgreSQL + pgvector for persistence
"""
import networkx as nx
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np

from backend.models.entities import (
    News, Actor, ActorRelation, NewsRelation, Story, Event
)
from backend.services.database_manager import DatabaseManager


class GraphManager:
    """Manages the two-layer graph structure with PostgreSQL backend"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize graph manager
        
        Args:
            db_manager: DatabaseManager instance (creates new if None)
        """
        self.db = db_manager or DatabaseManager()
        
        # Layer 1: News graph (kept for graph operations, synced with DB)
        self.news_graph = nx.Graph()

        # Layer 2: Actors graph (kept for graph operations, synced with DB)
        self.actors_graph = nx.DiGraph()  # Directed for relationships

        # Cross-layer: News ↔ Actors mentions (kept for graph operations)
        self.mentions_graph = nx.Graph()  # Bipartite graph
        
        # Cache for frequently accessed items (optional optimization)
        self._news_cache: Dict[str, News] = {}
        self._actors_cache: Dict[str, Actor] = {}
        self._stories_cache: Dict[str, Story] = {}

    # --- News Layer ---

    def add_news(self, news: News) -> None:
        """Add news item to graph and database"""
        # Save to database
        self.db.save_news(news)
        
        # Update cache
        self._news_cache[news.id] = news
        
        # Update graph (for graph operations)
        self.news_graph.add_node(
            news.id,
            title=news.title,
            published_at=news.published_at,
            embedding=news.embedding,
            story_id=news.story_id,
            is_pinned=news.is_pinned,
            domains=news.domains
        )

        # Add mentions edges to actors
        for actor_id in news.mentioned_actors:
            self.mentions_graph.add_edge(
                f"news_{news.id}",
                f"actor_{actor_id}",
                news_id=news.id,
                actor_id=actor_id
            )

    def add_news_relation(self, relation: NewsRelation) -> None:
        """Add relationship between news items"""
        # Save to database (handled in compute_news_similarities or explicitly)
        # Update graph
        source_news = self.get_news(relation.source_news_id)
        target_news = self.get_news(relation.target_news_id)
        
        if source_news and target_news:
            self.news_graph.add_edge(
                relation.source_news_id,
                relation.target_news_id,
                similarity=relation.similarity,
                weight=relation.weight,
                is_editorial=relation.is_editorial
            )

    def compute_news_similarities(self, threshold: float = 0.5) -> List[NewsRelation]:
        """Compute cosine similarities between all news items using pgvector"""
        # Use DatabaseManager's optimized pgvector implementation
        relations = self.db.compute_news_similarities(threshold=threshold)
        
        # Update graph with relations
        for relation in relations:
            self.news_graph.add_edge(
                relation.source_news_id,
                relation.target_news_id,
                similarity=relation.similarity,
                weight=relation.weight,
                is_editorial=relation.is_editorial
            )
        
        return relations

    def boost_similarity_by_shared_actors(self, boost_factor: float = 0.1) -> None:
        """Boost edge weights for news sharing actors"""
        for edge in self.news_graph.edges(data=True):
            source_id, target_id, data = edge
            source_news = self.get_news(source_id)
            target_news = self.get_news(target_id)
            
            if not source_news or not target_news:
                continue
                
            source_actors = set(source_news.mentioned_actors)
            target_actors = set(target_news.mentioned_actors)

            shared = len(source_actors & target_actors)
            if shared > 0:
                current_weight = data.get('weight', 1.0)
                new_weight = min(1.0, current_weight + (boost_factor * shared))
                self.news_graph[source_id][target_id]['weight'] = new_weight
                
                # Update in database
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE news_relations
                            SET weight = %s
                            WHERE source_news_id = %s AND target_news_id = %s
                        """, (new_weight, source_id, target_id))

    # --- Actor Layer ---

    def add_actor(self, actor: Actor) -> None:
        """Add actor to graph and database"""
        # Save to database
        self.db.save_actor(actor)
        
        # Update cache
        self._actors_cache[actor.id] = actor
        
        # Update graph
        self.actors_graph.add_node(
            actor.id,
            canonical_name=actor.canonical_name,
            actor_type=actor.actor_type,
            aliases=actor.aliases
        )

    def ensure_actor(self, name: str, actor_type: str = "person", confidence: float = 0.5) -> str:
        """Find actor by name (case-insensitive) or create new one"""
        actor_type = self._normalize_actor_type(actor_type)
        
        # Search in database
        all_actors = self.db.get_all_actors()
        for actor in all_actors:
            if actor.canonical_name.lower() == name.lower():
                return actor.id
        
        # Create new actor
        import uuid
        actor_id = f"actor_{uuid.uuid4().hex[:12]}"
        from backend.models.entities import ActorType
        new_actor = Actor(
            id=actor_id,
            canonical_name=name,
            actor_type=ActorType(actor_type or "person")
        )
        self.add_actor(new_actor)
        return actor_id

    def add_mention(self, news_id: str, actor_id: str, confidence: float = 0.5) -> None:
        """Link news to actor in mentions graph"""
        news_node = f"news_{news_id}"
        actor_node = f"actor_{actor_id}"
        self.mentions_graph.add_node(news_node, type="news")
        self.mentions_graph.add_node(actor_node, type="actor")
        self.mentions_graph.add_edge(
            news_node,
            actor_node,
            confidence=confidence
        )
        # Update news object (mention is saved via save_news when news is updated)
        news = self.get_news(news_id)
        if news and actor_id not in news.mentioned_actors:
            news.mentioned_actors.append(actor_id)
            self.db.save_news(news)

    def update_story_top_actors(self, story_id: str, top_n: int = 5) -> None:
        """Recompute top actors for a story based on mentions in its news"""
        story = self.get_story(story_id)
        if not story:
            return
        
        counts = {}
        for news_id in story.news_ids:
            news = self.get_news(news_id)
            if news:
                for aid in news.mentioned_actors:
                    counts[aid] = counts.get(aid, 0) + 1
        # sort by frequency desc
        sorted_ids = [aid for aid, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
        top_ids = sorted_ids[:top_n]
        story.top_actors = top_ids
        
        # Save updated story
        self.db.save_story(story)
        self._stories_cache[story_id] = story

    def _normalize_actor_type(self, actor_type: str) -> str:
        allowed = {"person", "company", "country", "organization", "government", "structure", "event"}
        if not actor_type:
            return "organization"
        t = str(actor_type).lower()
        if t in allowed:
            return t
        # map common synonyms
        if t in {"org", "other"}:
            return "organization"
        return "organization"

    def add_actor_relation(self, relation: ActorRelation) -> None:
        """Add relationship between actors"""
        source_actor = self.get_actor(relation.source_actor_id)
        target_actor = self.get_actor(relation.target_actor_id)
        
        if source_actor and target_actor:
            # Save to database
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO actor_relations (id, source_actor_id, target_actor_id, relation_type,
                                                     weight, confidence, is_ephemeral, ttl_days, expires_at,
                                                     source, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_actor_id, target_actor_id, relation_type) DO UPDATE SET
                            weight = EXCLUDED.weight,
                            confidence = EXCLUDED.confidence
                    """, (
                        relation.id, relation.source_actor_id, relation.target_actor_id,
                        relation.relation_type.value, relation.weight, relation.confidence,
                        relation.is_ephemeral, relation.ttl_days, relation.expires_at,
                        relation.source, relation.created_at
                    ))
            
            # Update graph
            self.actors_graph.add_edge(
                relation.source_actor_id,
                relation.target_actor_id,
                relation_type=relation.relation_type,
                weight=relation.weight,
                confidence=relation.confidence,
                is_ephemeral=relation.is_ephemeral,
                expires_at=relation.expires_at
            )

    def get_actor_mentions_count(self, actor_id: str) -> int:
        """Count how many news mention this actor"""
        actor_node = actor_id if actor_id.startswith("actor_") else f"actor_{actor_id}"
        if actor_node in self.mentions_graph:
            return len([n for n in self.mentions_graph.neighbors(actor_node)])
        return 0

    def get_news_actors(self, news_id: str) -> List[str]:
        """Get all actors mentioned in a news item"""
        return self.db.get_news_actors(news_id)

    def get_actor_news(self, actor_id: str) -> List[str]:
        """Get all news mentioning this actor"""
        return self.db.get_actor_news(actor_id)

    # --- Stories ---

    def add_story(self, story: Story) -> None:
        """Add story to storage and database"""
        # Save to database
        self.db.save_story(story)
        
        # Update cache
        self._stories_cache[story.id] = story

        # Update news with story assignment
        for news_id in story.news_ids:
            news = self.get_news(news_id)
            if news:
                news.story_id = story.id
                self.db.save_news(news)
                self.news_graph.nodes[news_id]['story_id'] = story.id

    def get_story_subgraph(self, story_id: str) -> nx.Graph:
        """Get subgraph of news in a story"""
        story = self.get_story(story_id)
        if not story:
            return nx.Graph()

        return self.news_graph.subgraph(story.news_ids).copy()

    # --- Events ---

    def add_event(self, event: Event) -> None:
        """Add timeline event to database"""
        # Save to database
        self.db.save_event(event)

        # Link to story
        if event.story_id:
            story = self.get_story(event.story_id)
            if story and event.id not in story.event_ids:
                story.event_ids.append(event.id)
                self.db.save_story(story)
                self._stories_cache[story.id] = story

    def get_story_events(self, story_id: str) -> List[Event]:
        """Get all events for a story, sorted by date"""
        return self.db.get_story_events(story_id)

    # --- Graph Analytics ---

    def get_connected_components(self, min_size: int = 2) -> List[List[str]]:
        """Get connected components in news graph (story candidates)"""
        components = list(nx.connected_components(self.news_graph))
        return [list(comp) for comp in components if len(comp) >= min_size]

    def get_node_neighbors(self, news_id: str, depth: int = 1) -> List[str]:
        """Get neighbors of a news node up to depth"""
        if news_id not in self.news_graph:
            return []

        if depth == 1:
            return list(self.news_graph.neighbors(news_id))

        # BFS for multiple depths
        visited = {news_id}
        current_level = {news_id}

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                for neighbor in self.news_graph.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level

        visited.remove(news_id)
        return list(visited)

    def calculate_cluster_cohesion(self, news_ids: List[str]) -> float:
        """Calculate cohesion score for a cluster of news"""
        if len(news_ids) < 2:
            return 1.0

        subgraph = self.news_graph.subgraph(news_ids)
        edges = subgraph.edges(data=True)

        if len(edges) == 0:
            return 0.0

        # Average edge weight
        weights = [data.get('weight', 1.0) for _, _, data in edges]
        return float(np.mean(weights))

    # --- Utilities ---

    def get_graph_stats(self) -> Dict:
        """Get overall graph statistics"""
        all_news = self.db.get_all_news()
        all_actors = self.db.get_all_actors()
        all_stories = self.db.get_all_stories(active_only=False)
        
        # Count events (approximate, could be optimized)
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM events")
                events_count = cur.fetchone()[0]
        
        return {
            "news_count": len(all_news),
            "actors_count": len(all_actors),
            "stories_count": len(all_stories),
            "events_count": events_count,
            "news_edges": self.news_graph.number_of_edges(),
            "actor_edges": self.actors_graph.number_of_edges(),
            "mention_edges": self.mentions_graph.number_of_edges(),
            "news_components": nx.number_connected_components(self.news_graph)
        }

    def update_editorial_edge(self, source_id: str, target_id: str, weight: float) -> None:
        """Update edge weight (editorial action)"""
        if self.news_graph.has_edge(source_id, target_id):
            self.news_graph[source_id][target_id]['weight'] = weight
            self.news_graph[source_id][target_id]['is_editorial'] = True
            
            # Update in database
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE news_relations
                        SET weight = %s, is_editorial = TRUE
                        WHERE source_news_id = %s AND target_news_id = %s
                    """, (weight, source_id, target_id))
        else:
            # Create new editorial edge
            relation = NewsRelation(
                source_news_id=source_id,
                target_news_id=target_id,
                similarity=weight,
                weight=weight,
                is_editorial=True,
                created_at=datetime.utcnow()
            )
            self.add_news_relation(relation)
            
            # Save to database
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO news_relations (source_news_id, target_news_id, similarity, weight, is_editorial, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_news_id, target_news_id) DO UPDATE SET
                            weight = EXCLUDED.weight,
                            is_editorial = EXCLUDED.is_editorial
                    """, (relation.source_news_id, relation.target_news_id, relation.similarity,
                          relation.weight, relation.is_editorial, relation.created_at))
    
    # --- Helper methods for getting entities ---
    
    def get_news(self, news_id: str) -> Optional[News]:
        """Get news by ID (with cache)"""
        if news_id in self._news_cache:
            return self._news_cache[news_id]
        news = self.db.get_news(news_id)
        if news:
            self._news_cache[news_id] = news
        return news
    
    def get_actor(self, actor_id: str) -> Optional[Actor]:
        """Get actor by ID (with cache)"""
        if actor_id in self._actors_cache:
            return self._actors_cache[actor_id]
        actor = self.db.get_actor(actor_id)
        if actor:
            self._actors_cache[actor_id] = actor
        return actor
    
    def get_story(self, story_id: str) -> Optional[Story]:
        """Get story by ID (with cache)"""
        if story_id in self._stories_cache:
            return self._stories_cache[story_id]
        story = self.db.get_story(story_id)
        if story:
            self._stories_cache[story_id] = story
        return story
    
    @property
    def news(self) -> Dict[str, News]:
        """Get all news (for backward compatibility)"""
        all_news = self.db.get_all_news()
        return {n.id: n for n in all_news}
    
    @property
    def actors(self) -> Dict[str, Actor]:
        """Get all actors (for backward compatibility)"""
        all_actors = self.db.get_all_actors()
        return {a.id: a for a in all_actors}
    
    @property
    def stories(self) -> Dict[str, Story]:
        """Get all stories (for backward compatibility)"""
        all_stories = self.db.get_all_stories(active_only=False)
        return {s.id: s for s in all_stories}
    
    @property
    def events(self) -> Dict[str, Event]:
        """Get all events (for backward compatibility)"""
        # This is less efficient, but needed for compatibility
        # Could be optimized with a get_all_events method
        from psycopg2.extras import RealDictCursor
        result = {}
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM events")
                for row in cur.fetchall():
                    event = self.db._row_to_event(row)
                    result[event.id] = event
        return result
