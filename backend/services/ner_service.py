"""
NER Service for actor extraction from text
For prototype: uses simple pattern matching and keyword extraction
Can be replaced with spaCy or other NER models
"""
import uuid
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from backend.models.entities import Actor, ActorType, ActorRelation, RelationType


class NERService:
    """Named Entity Recognition service for extracting actors"""

    def __init__(self):
        # Gazetteer: known entities (can be loaded from file)
        self.gazetteer: Dict[str, Actor] = {}

        # Canonical names mapping
        self.canonical_map: Dict[str, str] = {}  # alias -> canonical_id

        # Relationship patterns (simple pattern matching)
        self.relation_patterns = {
            RelationType.MEMBER_OF: [
                r"(\w+)\s+(?:министр|minister|president|CEO|director)\s+(?:of|в)\s+(\w+)",
                r"(\w+)\s+from\s+(\w+)",
            ],
            RelationType.CRITICIZED: [
                r"(\w+)\s+(?:criticized|раскритиковал|осудил)\s+(\w+)",
            ],
            RelationType.SUPPORTS: [
                r"(\w+)\s+(?:supports|поддерживает|backed)\s+(\w+)",
            ],
        }

    def load_gazetteer(self, actors: List[Actor]) -> None:
        """Load known actors into gazetteer"""
        for actor in actors:
            self.gazetteer[actor.id] = actor

            # Build canonical mapping
            self.canonical_map[actor.canonical_name.lower()] = actor.id

            for alias_entry in actor.aliases:
                alias = alias_entry.get("name", "")
                if alias:
                    self.canonical_map[alias.lower()] = actor.id

    def extract_actors_from_text(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Tuple[List[str], List[Actor]]:
        """
        Extract actors from text

        Returns:
            - List of known actor IDs
            - List of newly discovered Actor objects
        """
        known_actors = []
        new_actors = []

        # Simple approach: match against gazetteer
        text_lower = text.lower()

        for canonical, actor_id in self.canonical_map.items():
            if canonical in text_lower:
                if actor_id not in known_actors:
                    known_actors.append(actor_id)

        # Extract potential new entities (very simplified)
        # In real implementation, use spaCy NER here
        potential_entities = self._extract_capitalized_phrases(text)

        for entity in potential_entities:
            entity_lower = entity.lower()

            # Skip if already known
            if entity_lower in self.canonical_map:
                continue

            # Create new actor (with low confidence)
            actor_type = self._infer_actor_type(entity, text)
            actor = Actor(
                id=f"actor_{uuid.uuid4().hex[:12]}",
                canonical_name=entity,
                actor_type=actor_type,
                aliases=[],
                metadata={"confidence": 0.5, "auto_extracted": True}
            )
            new_actors.append(actor)

        return known_actors, new_actors

    def _extract_capitalized_phrases(self, text: str, max_words: int = 3) -> List[str]:
        """Extract capitalized phrases (potential named entities)"""
        # Pattern: 1-3 capitalized words in a row
        pattern = r'\b[A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+){0,' + str(max_words - 1) + r'}\b'
        matches = re.findall(pattern, text)

        # Filter out common words (simplified)
        stop_words = {"The", "This", "That", "These", "Those", "Это", "Этот"}
        matches = [m for m in matches if m not in stop_words]

        return list(set(matches))

    def _infer_actor_type(self, entity: str, context: str) -> ActorType:
        """Infer actor type from entity and context"""
        entity_lower = entity.lower()
        context_lower = context.lower()

        # Company indicators
        if any(indicator in entity_lower for indicator in ["corp", "inc", "llc", "ltd", "gmbh", "oao"]):
            return ActorType.COMPANY

        # Country indicators (simplified)
        countries = ["russia", "ukraine", "usa", "china", "germany", "france", "россия", "украина"]
        if entity_lower in countries:
            return ActorType.COUNTRY

        # Organization indicators
        org_keywords = ["organization", "committee", "agency", "ministry", "department", "организация"]
        if any(kw in context_lower for kw in org_keywords):
            return ActorType.ORGANIZATION

        # Default to person
        return ActorType.PERSON

    def extract_relations_from_text(
        self,
        text: str,
        mentioned_actors: List[str]
    ) -> List[ActorRelation]:
        """
        Extract relationships between actors from text

        Args:
            text: Source text
            mentioned_actors: List of actor IDs mentioned in text

        Returns:
            List of ActorRelation objects
        """
        relations = []

        # Simple pattern-based extraction
        for relation_type, patterns in self.relation_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Try to map matched entities to known actors
                    entity1 = match.group(1)
                    entity2 = match.group(2)

                    actor1_id = self._find_actor_by_name(entity1, mentioned_actors)
                    actor2_id = self._find_actor_by_name(entity2, mentioned_actors)

                    if actor1_id and actor2_id:
                        relation = ActorRelation(
                            id=f"rel_{uuid.uuid4().hex[:12]}",
                            source_actor_id=actor1_id,
                            target_actor_id=actor2_id,
                            relation_type=relation_type,
                            confidence=0.6,
                            is_ephemeral=(relation_type in [RelationType.CRITICIZED, RelationType.SUPPORTS]),
                            ttl_days=60 if relation_type in [RelationType.CRITICIZED, RelationType.SUPPORTS] else None
                        )
                        relations.append(relation)

        return relations

    def _find_actor_by_name(self, name: str, candidate_ids: List[str]) -> Optional[str]:
        """Find actor ID by name from candidates"""
        name_lower = name.lower()

        # Check canonical map
        if name_lower in self.canonical_map:
            actor_id = self.canonical_map[name_lower]
            if actor_id in candidate_ids:
                return actor_id

        # Check partial matches in candidates
        for actor_id in candidate_ids:
            if actor_id in self.gazetteer:
                actor = self.gazetteer[actor_id]
                if name_lower in actor.canonical_name.lower():
                    return actor_id
                for alias_entry in actor.aliases:
                    if name_lower in alias_entry.get("name", "").lower():
                        return actor_id

        return None

    def canonicalize_actor(self, actor_name: str) -> Optional[str]:
        """Find canonical actor ID for a name"""
        return self.canonical_map.get(actor_name.lower())

    def add_actor_alias(self, actor_id: str, alias: str, alias_type: str = "alias") -> None:
        """Add alias to actor"""
        if actor_id in self.gazetteer:
            actor = self.gazetteer[actor_id]
            actor.aliases.append({"name": alias, "type": alias_type})
            self.canonical_map[alias.lower()] = actor_id

    def merge_actors(self, primary_id: str, secondary_id: str) -> Optional[Actor]:
        """Merge two actors into one"""
        if primary_id not in self.gazetteer or secondary_id not in self.gazetteer:
            return None

        primary = self.gazetteer[primary_id]
        secondary = self.gazetteer[secondary_id]

        # Add secondary's name and aliases to primary
        primary.aliases.append({"name": secondary.canonical_name, "type": "merged"})
        primary.aliases.extend(secondary.aliases)

        # Update canonical map
        self.canonical_map[secondary.canonical_name.lower()] = primary_id
        for alias_entry in secondary.aliases:
            alias = alias_entry.get("name", "")
            if alias:
                self.canonical_map[alias.lower()] = primary_id

        # Remove secondary
        del self.gazetteer[secondary_id]

        primary.updated_at = datetime.utcnow()
        return primary
