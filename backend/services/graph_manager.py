"""
Graph manager for two-layer graph: News and Actors
"""
import networkx as nx
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.models.entities import (
    News, Actor, ActorRelation, NewsRelation, Story, Event
)


class GraphManager:
    """Manages the two-layer graph structure"""

    def __init__(self):
        # Layer 1: News graph
        self.news_graph = nx.Graph()

        # Layer 2: Actors graph
        self.actors_graph = nx.DiGraph()  # Directed for relationships

        # Cross-layer: News ↔ Actors mentions
        self.mentions_graph = nx.Graph()  # Bipartite graph

        # Storage
        self.news: Dict[str, News] = {}
        self.actors: Dict[str, Actor] = {}
        self.stories: Dict[str, Story] = {}
        self.events: Dict[str, Event] = {}

    # --- News Layer ---

    def add_news(self, news: News) -> None:
        """Add news item to graph"""
        self.news[news.id] = news
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
        if relation.source_news_id in self.news and relation.target_news_id in self.news:
            self.news_graph.add_edge(
                relation.source_news_id,
                relation.target_news_id,
                similarity=relation.similarity,
                weight=relation.weight,
                is_editorial=relation.is_editorial
            )

    def compute_news_similarities(self, threshold: float = 0.5) -> List[NewsRelation]:
        """Compute cosine similarities between all news items"""
        relations = []
        news_items = list(self.news.values())

        # Filter items with embeddings
        embedded_news = [n for n in news_items if n.embedding is not None]

        if len(embedded_news) < 2:
            return relations

        # Create embedding matrix
        embeddings = np.array([n.embedding for n in embedded_news])
        similarities = cosine_similarity(embeddings)

        # Create relations
        for i in range(len(embedded_news)):
            for j in range(i + 1, len(embedded_news)):
                sim = float(similarities[i, j])
                if sim >= threshold:
                    sim = min(1.0, sim)  # Clamp to avoid float precision issues > 1.0
                    relation = NewsRelation(
                        source_news_id=embedded_news[i].id,
                        target_news_id=embedded_news[j].id,
                        similarity=sim,
                        weight=sim
                    )
                    relations.append(relation)
                    self.add_news_relation(relation)

        return relations

    def boost_similarity_by_shared_actors(self, boost_factor: float = 0.1) -> None:
        """Boost edge weights for news sharing actors"""
        for edge in self.news_graph.edges(data=True):
            source_id, target_id, data = edge
            source_actors = set(self.news[source_id].mentioned_actors)
            target_actors = set(self.news[target_id].mentioned_actors)

            shared = len(source_actors & target_actors)
            if shared > 0:
                current_weight = data.get('weight', 1.0)
                new_weight = min(1.0, current_weight + (boost_factor * shared))
                self.news_graph[source_id][target_id]['weight'] = new_weight

    # --- Actor Layer ---

    def add_actor(self, actor: Actor) -> None:
        """Add actor to graph"""
        self.actors[actor.id] = actor
        self.actors_graph.add_node(
            actor.id,
            canonical_name=actor.canonical_name,
            actor_type=actor.actor_type,
            aliases=actor.aliases
        )

    def ensure_actor(self, name: str, actor_type: str = "person", confidence: float = 0.5) -> str:
        """Find actor by name (case-insensitive) or create new one"""
        actor_type = self._normalize_actor_type(actor_type)
        for actor in self.actors.values():
            if actor.canonical_name.lower() == name.lower():
                return actor.id
        actor_id = f"actor_{len(self.actors) + 1}"
        new_actor = Actor(
            id=actor_id,
            canonical_name=name,
            actor_type=actor_type or "person",
            confidence=confidence
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
        # update news object cache
        if news_id in self.news:
            if actor_id not in self.news[news_id].mentioned_actors:
                self.news[news_id].mentioned_actors.append(actor_id)

    def update_story_top_actors(self, story_id: str, top_n: int = 5) -> None:
        """Recompute top actors for a story based on mentions in its news"""
        if story_id not in self.stories:
            return
        story = self.stories[story_id]
        counts = {}
        for news_id in story.news_ids:
            if news_id in self.news:
                for aid in self.news[news_id].mentioned_actors:
                    counts[aid] = counts.get(aid, 0) + 1
        # sort by frequency desc
        sorted_ids = [aid for aid, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
        top_ids = sorted_ids[:top_n]
        # convert to names for UI compatibility
        top_names = []
        for aid in top_ids:
            actor = self.actors.get(aid)
            if actor:
                top_names.append(actor.canonical_name)
        story.top_actors = top_names

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
        if relation.source_actor_id in self.actors and relation.target_actor_id in self.actors:
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
        actor_node = f"actor_{actor_id}"
        if actor_node in self.mentions_graph:
            return len([n for n in self.mentions_graph.neighbors(actor_node)])
        return 0

    def get_news_actors(self, news_id: str) -> List[str]:
        """Get all actors mentioned in a news item"""
        news_node = f"news_{news_id}"
        if news_node in self.mentions_graph:
            return [
                n.replace("actor_", "")
                for n in self.mentions_graph.neighbors(news_node)
                if n.startswith("actor_")
            ]
        return []

    def get_actor_news(self, actor_id: str) -> List[str]:
        """Get all news mentioning this actor"""
        actor_node = f"actor_{actor_id}"
        if actor_node in self.mentions_graph:
            return [
                n.replace("news_", "")
                for n in self.mentions_graph.neighbors(actor_node)
                if n.startswith("news_")
            ]
        return []

    # --- Stories ---

    def add_story(self, story: Story) -> None:
        """Add story to storage"""
        self.stories[story.id] = story

        # Update news with story assignment
        for news_id in story.news_ids:
            if news_id in self.news:
                self.news[news_id].story_id = story.id
                self.news_graph.nodes[news_id]['story_id'] = story.id

    def get_story_subgraph(self, story_id: str) -> nx.Graph:
        """Get subgraph of news in a story"""
        if story_id not in self.stories:
            return nx.Graph()

        story = self.stories[story_id]
        return self.news_graph.subgraph(story.news_ids).copy()

    # --- Events ---

    def add_event(self, event: Event) -> None:
        """Add timeline event"""
        self.events[event.id] = event

        # Link to story
        if event.story_id and event.story_id in self.stories:
            story = self.stories[event.story_id]
            if event.id not in story.event_ids:
                story.event_ids.append(event.id)

    def get_story_events(self, story_id: str) -> List[Event]:
        """Get all events for a story, sorted by date"""
        if story_id not in self.stories:
            return []

        story = self.stories[story_id]
        events = [self.events[eid] for eid in story.event_ids if eid in self.events]
        return sorted(events, key=lambda e: e.event_date)

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
        return {
            "news_count": len(self.news),
            "actors_count": len(self.actors),
            "stories_count": len(self.stories),
            "events_count": len(self.events),
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
        else:
            # Create new editorial edge
            relation = NewsRelation(
                source_news_id=source_id,
                target_news_id=target_id,
                similarity=weight,
                weight=weight,
                is_editorial=True
            )
            self.add_news_relation(relation)
