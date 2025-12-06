"""
Event extraction service for timeline
Extracts facts and opinions from news text
"""
import uuid
import re
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from backend.models.entities import Event, EventType, News


class EventExtractionService:
    """Service for extracting timeline events from news"""

    def __init__(self):
        # Keywords for opinion detection
        self.opinion_keywords = [
            "считает", "полагает", "заявил", "утверждает", "thinks", "believes",
            "claims", "stated", "said", "announced", "мнение", "opinion",
            "по мнению", "according to", "criticized", "раскритиковал",
            "praised", "похвалил"
        ]

        # Keywords for factual events
        self.fact_keywords = [
            "произошло", "случилось", "occurred", "happened", "состоялся",
            "took place", "was held", "был проведен", "signed", "подписан",
            "launched", "запущен", "opened", "открыт"
        ]

        # Temporal expressions patterns
        self.temporal_patterns = [
            r'(?:в|on)\s+(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря))',
            r'(?:в|on)\s+(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(yesterday|вчера)',
            r'(today|сегодня)',
            r'(tomorrow|завтра)',
        ]

    def extract_events_from_news(
        self,
        news: News,
        source_trust: float = 0.7
    ) -> List[Event]:
        """
        Extract timeline events from a news item

        Args:
            news: News object
            source_trust: Trust level of the source (0-1)

        Returns:
            List of Event objects
        """
        events = []
        text = f"{news.title}. {news.summary}. {news.full_text}"

        # Split into sentences
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Check if sentence contains temporal reference
            event_date = self._extract_date(sentence, news.published_at)

            if event_date:
                # Determine event type
                event_type = self._classify_event_type(sentence)

                # Extract actors mentioned (from news.mentioned_actors)
                actors = news.mentioned_actors

                # Create event
                event = Event(
                    id=f"event_{uuid.uuid4().hex[:12]}",
                    news_id=news.id,
                    story_id=news.story_id,
                    event_type=event_type,
                    title=self._generate_event_title(sentence, event_type),
                    description=sentence,
                    event_date=event_date,
                    actors=actors,
                    source_trust=source_trust,
                    confidence=self._calculate_confidence(sentence, event_type)
                )
                # Guarantee story linkage if available
                if news.story_id and not event.story_id:
                    event.story_id = news.story_id
                events.append(event)

        # Fallback: if nothing extracted, create a single fact event using published_at
        if not events and news.published_at:
            events.append(Event(
                id=f"event_{uuid.uuid4().hex[:12]}",
                news_id=news.id,
                story_id=news.story_id,
                event_type=EventType.FACT,
                title=news.title[:80],
                description=news.summary[:200] or news.full_text[:200],
                event_date=news.published_at,
                actors=news.mentioned_actors,
                source_trust=source_trust,
                confidence=0.6
            ))

        return events

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        return sentences

    def _extract_date(self, sentence: str, fallback_date: datetime) -> Optional[datetime]:
        """Extract date from sentence"""
        # Try temporal patterns
        for pattern in self.temporal_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                date_str = match.group(1)

                # Handle relative dates
                if date_str.lower() in ['сегодня', 'today']:
                    return fallback_date

                if date_str.lower() in ['вчера', 'yesterday']:
                    return fallback_date - timedelta(days=1)

                if date_str.lower() in ['завтра', 'tomorrow']:
                    return fallback_date + timedelta(days=1)

                # Try to parse absolute dates
                try:
                    parsed_date = date_parser.parse(date_str, fuzzy=True)
                    return parsed_date
                except:
                    continue

        # If no explicit date, use publication date as fallback
        return fallback_date

    def _classify_event_type(self, sentence: str) -> EventType:
        """Classify event as FACT or OPINION"""
        sentence_lower = sentence.lower()

        # Check for opinion keywords
        opinion_score = sum(1 for kw in self.opinion_keywords if kw in sentence_lower)
        fact_score = sum(1 for kw in self.fact_keywords if kw in sentence_lower)

        # Check for quotes (opinions)
        if '"' in sentence or '«' in sentence or 'said' in sentence_lower:
            opinion_score += 2

        # Decide based on scores
        if opinion_score > fact_score:
            return EventType.OPINION
        else:
            return EventType.FACT

    def _generate_event_title(self, sentence: str, event_type: EventType) -> str:
        """Generate short event title from sentence"""
        # Take first 80 characters
        title = sentence[:80].strip()

        if len(sentence) > 80:
            title += "..."

        return title

    def _calculate_confidence(self, sentence: str, event_type: EventType) -> float:
        """Calculate extraction confidence"""
        # Simple heuristic based on sentence characteristics
        confidence = 0.7

        # Increase confidence if temporal markers present
        if any(pattern in sentence.lower() for pattern in ['в ', 'on ', 'at ', '2024', '2025']):
            confidence += 0.1

        # Decrease confidence for very short sentences
        if len(sentence) < 30:
            confidence -= 0.1

        return max(0.5, min(1.0, confidence))

    def merge_duplicate_events(self, events: List[Event], threshold: float = 0.8) -> List[Event]:
        """Merge duplicate or very similar events"""
        if len(events) < 2:
            return events

        unique_events = []
        used_indices = set()

        for i, event1 in enumerate(events):
            if i in used_indices:
                continue

            # Find similar events
            similar = [i]
            for j in range(i + 1, len(events)):
                if j in used_indices:
                    continue

                event2 = events[j]

                # Check similarity
                if self._events_similar(event1, event2, threshold):
                    similar.append(j)
                    used_indices.add(j)

            # If multiple similar events, merge them
            if len(similar) > 1:
                merged = self._merge_events([events[idx] for idx in similar])
                unique_events.append(merged)
            else:
                unique_events.append(event1)

            used_indices.add(i)

        return unique_events

    def _events_similar(self, event1: Event, event2: Event, threshold: float) -> bool:
        """Check if two events are similar"""
        # Same type
        if event1.event_type != event2.event_type:
            return False

        # Similar date (within 1 day)
        date_diff = abs((event1.event_date - event2.event_date).total_seconds() / 86400)
        if date_diff > 1:
            return False

        # Similar text (simple word overlap)
        words1 = set(event1.title.lower().split())
        words2 = set(event2.title.lower().split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap >= threshold

    def _merge_events(self, events: List[Event]) -> Event:
        """Merge multiple events into one"""
        # Take the one with highest confidence
        best_event = max(events, key=lambda e: e.confidence)

        # Combine actors
        all_actors = []
        for event in events:
            all_actors.extend(event.actors)
        all_actors = list(set(all_actors))

        # Update best event
        best_event.actors = all_actors
        best_event.description = " | ".join([e.description for e in events[:3]])

        return best_event
