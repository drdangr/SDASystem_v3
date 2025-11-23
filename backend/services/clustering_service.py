"""
Story clustering service using graph-based and HDBSCAN approaches
"""
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import numpy as np
from sklearn.cluster import DBSCAN
import networkx as nx

from backend.models.entities import Story, News, DomainCategory
from backend.services.graph_manager import GraphManager


class ClusteringService:
    """Service for clustering news into stories"""

    def __init__(self, graph_manager: GraphManager):
        self.graph = graph_manager

    def cluster_news_to_stories(
        self,
        min_cluster_size: int = 2,
        eps: float = 0.3,
        use_graph: bool = True
    ) -> List[Story]:
        """
        Cluster news items into story candidates

        Args:
            min_cluster_size: Minimum news items in a cluster
            eps: DBSCAN epsilon parameter (max distance)
            use_graph: Use graph-based clustering (preferred)

        Returns:
            List of Story objects
        """
        stories = []

        if use_graph:
            # Graph-based clustering using connected components
            stories = self._cluster_by_graph_components(min_cluster_size)
        else:
            # Embedding-based DBSCAN clustering
            stories = self._cluster_by_embeddings(min_cluster_size, eps)

        # Calculate metrics for all stories
        for story in stories:
            self._calculate_story_metrics(story)
            self.graph.add_story(story)

        return stories

    def _cluster_by_graph_components(self, min_size: int) -> List[Story]:
        """Cluster using connected components in news graph"""
        components = self.graph.get_connected_components(min_size=min_size)
        stories = []

        for component in components:
            story = self._create_story_from_news_ids(component)
            stories.append(story)

        return stories

    def _cluster_by_embeddings(self, min_size: int, eps: float) -> List[Story]:
        """Cluster using DBSCAN on embeddings"""
        # Get news with embeddings
        news_items = [n for n in self.graph.news.values() if n.embedding is not None]

        if len(news_items) < min_size:
            return []

        # Create embedding matrix
        embeddings = np.array([n.embedding for n in news_items])

        # DBSCAN clustering
        clustering = DBSCAN(eps=eps, min_samples=min_size, metric='cosine')
        labels = clustering.fit_predict(embeddings)

        # Group by cluster label
        clusters: Dict[int, List[str]] = {}
        for idx, label in enumerate(labels):
            if label == -1:  # Noise
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(news_items[idx].id)

        # Create stories
        stories = []
        for news_ids in clusters.values():
            story = self._create_story_from_news_ids(news_ids)
            stories.append(story)

        return stories

    def _create_story_from_news_ids(self, news_ids: List[str]) -> Story:
        """Create a Story object from a cluster of news IDs"""
        # Get news objects
        news_items = [self.graph.news[nid] for nid in news_ids if nid in self.graph.news]

        if not news_items:
            raise ValueError("No valid news items in cluster")

        # Sort by publication date
        news_items.sort(key=lambda n: n.published_at)

        # Extract actors
        all_actors = []
        for news in news_items:
            all_actors.extend(news.mentioned_actors)

        # Count actor frequency
        actor_counts = {}
        for actor_id in all_actors:
            actor_counts[actor_id] = actor_counts.get(actor_id, 0) + 1

        # Top actors (most mentioned)
        top_actors = sorted(actor_counts.items(), key=lambda x: x[1], reverse=True)
        top_actors = [actor_id for actor_id, _ in top_actors[:10]]

        # Extract domains
        all_domains = []
        for news in news_items:
            all_domains.extend(news.domains)
        unique_domains = list(set(all_domains))

        # Determine primary domain (most common)
        primary_domain = self._infer_primary_domain(unique_domains)

        # Generate title and summary
        title = self._generate_story_title(news_items, top_actors)
        summary = self._generate_story_summary(news_items)
        bullets = self._generate_story_bullets(news_items)

        # Create story
        story_id = f"story_{uuid.uuid4().hex[:12]}"

        # Determine core news (pinned or earliest)
        core_news_ids = [n.id for n in news_items if n.is_pinned]
        if not core_news_ids and news_items:
            core_news_ids = [news_items[0].id]  # First chronologically

        story = Story(
            id=story_id,
            title=title,
            summary=summary,
            bullets=bullets,
            news_ids=news_ids,
            core_news_ids=core_news_ids,
            top_actors=top_actors,
            domains=unique_domains,
            primary_domain=primary_domain,
            size=len(news_ids),
            first_seen=news_items[0].published_at,
            last_activity=news_items[-1].published_at
        )

        return story

    def _calculate_story_metrics(self, story: Story) -> None:
        """Calculate relevance, cohesion, freshness for a story"""
        # Cohesion: average edge weight in cluster
        story.cohesion = self.graph.calculate_cluster_cohesion(story.news_ids)

        # Freshness: based on most recent activity
        now = datetime.utcnow()
        hours_since_update = (now - story.last_activity).total_seconds() / 3600
        story.freshness = max(0.0, 1.0 - (hours_since_update / 168))  # Decay over 7 days

        # Relevance: combination of size, freshness, and cohesion
        size_score = min(1.0, story.size / 10)  # Normalize by max expected size
        story.relevance = (size_score * 0.3 + story.freshness * 0.4 + story.cohesion * 0.3)

        story.updated_at = now

    def _generate_story_title(self, news_items: List[News], top_actors: List[str]) -> str:
        """Generate story title from news"""
        # Use first news title as base, or combine with top actor
        if not news_items:
            return "Untitled Story"

        base_title = news_items[0].title

        # If we have top actors, try to incorporate them
        if top_actors and top_actors[0] in self.graph.actors:
            actor_name = self.graph.actors[top_actors[0]].canonical_name
            # Simple heuristic: if actor not in title, prepend
            if actor_name.lower() not in base_title.lower():
                return f"{actor_name}: {base_title}"

        return base_title

    def _generate_story_summary(self, news_items: List[News]) -> str:
        """Generate story summary from news summaries"""
        if not news_items:
            return ""

        # For prototype: concatenate first few summaries
        summaries = [n.summary for n in news_items[:3] if n.summary]
        return " | ".join(summaries)

    def _generate_story_bullets(self, news_items: List[News]) -> List[str]:
        """Generate bullet points from news"""
        bullets = []
        for news in news_items[:5]:  # Top 5 news
            bullet = f"{news.published_at.strftime('%Y-%m-%d')}: {news.title}"
            bullets.append(bullet)
        return bullets

    def _infer_primary_domain(self, domains: List[str]) -> Optional[DomainCategory]:
        """Infer primary domain category from domain list"""
        if not domains:
            return DomainCategory.OTHER

        # Simple keyword matching
        domain_keywords = {
            DomainCategory.POLITICS: ["politics", "government", "election", "policy", "democracy", "international", "regulation", "united_states", "united states"],
            DomainCategory.ECONOMICS: ["economy", "economics", "business", "finance", "market", "trade", "mergers"],
            DomainCategory.TECHNOLOGY: ["technology", "tech", "ai", "software", "digital"],
            DomainCategory.MILITARY: ["military", "defense", "war", "army", "conflict"],
            DomainCategory.HEALTH: ["health", "medicine", "covid", "disease", "hospital"],
            DomainCategory.CULTURE: ["culture", "art", "music", "film", "entertainment"],
            DomainCategory.ENVIRONMENT: ["environment", "climate", "energy", "pollution"],
            DomainCategory.SPORTS: ["sports", "football", "olympics", "championship"],
        }

        # Count matches
        category_scores = {cat: 0 for cat in DomainCategory}

        for domain in domains:
            domain_lower = domain.lower()
            for category, keywords in domain_keywords.items():
                if any(kw in domain_lower for kw in keywords):
                    category_scores[category] += 1

        # Return category with highest score
        max_category = max(category_scores.items(), key=lambda x: x[1])
        if max_category[1] > 0:
            return max_category[0]

        return DomainCategory.OTHER

    # --- Story Operations ---

    def merge_stories(self, story_ids: List[str]) -> Optional[Story]:
        """Merge multiple stories into one"""
        stories = [self.graph.stories[sid] for sid in story_ids if sid in self.graph.stories]

        if len(stories) < 2:
            return None

        # Combine all news
        all_news_ids = []
        for story in stories:
            all_news_ids.extend(story.news_ids)

        # Remove duplicates
        all_news_ids = list(set(all_news_ids))

        # Create new merged story
        merged_story = self._create_story_from_news_ids(all_news_ids)
        merged_story.is_editorial = True

        # Remove old stories
        for sid in story_ids:
            if sid in self.graph.stories:
                del self.graph.stories[sid]

        self.graph.add_story(merged_story)
        return merged_story

    def split_story(self, story_id: str, news_groups: List[List[str]]) -> List[Story]:
        """Split a story into multiple stories"""
        if story_id not in self.graph.stories:
            return []

        new_stories = []
        for news_ids in news_groups:
            if len(news_ids) >= 1:
                story = self._create_story_from_news_ids(news_ids)
                story.is_editorial = True
                new_stories.append(story)
                self.graph.add_story(story)

        # Remove original story
        del self.graph.stories[story_id]

        return new_stories

    def update_story_relevance(self, story_id: str) -> None:
        """Recalculate story metrics"""
        if story_id in self.graph.stories:
            story = self.graph.stories[story_id]
            self._calculate_story_metrics(story)
