"""
Data models for SDASystem_v3
"""
from datetime import datetime
from typing import List, Dict, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field


class ActorType(str, Enum):
    """Types of actors"""
    PERSON = "person"
    COMPANY = "company"
    COUNTRY = "country"
    ORGANIZATION = "organization"
    GOVERNMENT = "government"
    STRUCTURE = "structure"
    EVENT_ENTITY = "event"


class RelationType(str, Enum):
    """Types of relationships between actors"""
    MEMBER_OF = "member_of"
    ALLY_OF = "ally_of"
    COMPETITOR_OF = "competitor_of"
    PART_OF = "part_of"
    OPERATES_IN = "operates_in"
    ROLE_IN = "role_in"
    REGULATES = "regulates"
    OWNS = "owns"
    CRITICIZED = "criticized"  # ephemeral
    SUPPORTS = "supports"  # ephemeral


class EventType(str, Enum):
    """Types of timeline events"""
    FACT = "fact"  # blue - verified factual event
    OPINION = "opinion"  # orange - expressed opinion/stance


class AliasType(str, Enum):
    """Types of actor aliases"""
    CANONICAL = "canonical"
    NICKNAME = "nickname"
    TYPO = "typo"
    EUPHEMISM = "euphemism"
    ABBREVIATION = "abbreviation"


class DomainCategory(str, Enum):
    """Main domain categories"""
    POLITICS = "politics"
    ECONOMICS = "economics"
    CULTURE = "culture"
    TECHNOLOGY = "technology"
    MILITARY = "military"
    HEALTH = "health"
    ENVIRONMENT = "environment"
    SPORTS = "sports"
    OTHER = "other"


# --- Base Models ---

class Actor(BaseModel):
    """Actor entity (person, company, country, etc.)"""
    id: str = Field(..., description="Unique actor ID")
    canonical_name: str = Field(..., description="Canonical name")
    actor_type: ActorType = Field(..., description="Type of actor")
    aliases: List[Dict[str, str]] = Field(default_factory=list, description="List of aliases with types")
    wikidata_qid: Optional[str] = Field(default=None, description="Wikidata QID for canonical entity")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")
    # metadata может содержать:
    # - positions: List[str] - должности (для людей)
    # - country: Optional[str] - страна (для людей)
    # - countries: List[str] - список стран гражданства
    # - birth_date: Optional[str] - дата рождения
    # - description: Optional[str] - описание из Wikidata
    # - original_language: str - язык оригинального имени

    class Config:
        use_enum_values = True


class ActorRelation(BaseModel):
    """Relationship between two actors"""
    id: str = Field(..., description="Unique relation ID")
    source_actor_id: str
    target_actor_id: str
    relation_type: RelationType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    is_ephemeral: bool = Field(default=False, description="Temporary event-based relation")
    ttl_days: Optional[int] = Field(default=None, description="TTL for ephemeral relations")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    source: str = Field(default="auto", description="Source: auto, editor, import")

    class Config:
        use_enum_values = True


class News(BaseModel):
    """News/post entity"""
    id: str = Field(..., description="Unique news ID")
    title: str = Field(..., description="News title")
    summary: str = Field(..., description="News summary")
    full_text: str = Field(default="", description="Full text content")
    url: Optional[str] = None
    source: str = Field(..., description="Source/publisher")
    author: Optional[str] = None
    published_at: datetime = Field(..., description="Publication time")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Embeddings and NER
    embedding: Optional[List[float]] = Field(default=None, description="Text embedding vector")
    mentioned_actors: List[str] = Field(default_factory=list, description="List of actor IDs")

    # Relations
    related_news_ids: List[str] = Field(default_factory=list, description="Related news IDs")
    story_id: Optional[str] = Field(default=None, description="Assigned story ID")

    # Metadata
    domains: List[str] = Field(default_factory=list, description="Related domains/subdomains")
    is_duplicate: bool = Field(default=False)
    duplicate_of: Optional[str] = None

    # Editorial
    is_pinned: bool = Field(default=False, description="Pinned as story core")
    editorial_notes: str = Field(default="")

    class Config:
        use_enum_values = True


class NewsRelation(BaseModel):
    """Relationship between news items"""
    source_news_id: str
    target_news_id: str
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Editorial weight override")
    is_editorial: bool = Field(default=False, description="Manually created by editor")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Event(BaseModel):
    """Timeline event extracted from news"""
    id: str = Field(..., description="Unique event ID")
    news_id: str = Field(..., description="Source news ID")
    story_id: Optional[str] = Field(default=None, description="Related story ID")
    event_type: EventType = Field(..., description="Fact or opinion")
    title: str = Field(..., description="Event title/description")
    description: str = Field(default="")
    event_date: datetime = Field(..., description="When event occurred/was stated")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    # Actors involved
    actors: List[str] = Field(default_factory=list, description="Actor IDs involved")

    # Source credibility
    source_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    class Config:
        use_enum_values = True


class Story(BaseModel):
    """Story cluster formed from news"""
    id: str = Field(..., description="Unique story ID")
    title: str = Field(..., description="Story title")
    summary: str = Field(..., description="Generated story summary")
    bullets: List[str] = Field(default_factory=list, description="Key points")

    # News and actors
    news_ids: List[str] = Field(default_factory=list, description="News in this story")
    core_news_ids: List[str] = Field(default_factory=list, description="Pinned core news")
    top_actors: List[str] = Field(default_factory=list, description="Most mentioned actors")

    # Events
    event_ids: List[str] = Field(default_factory=list, description="Timeline events")

    # Domains
    domains: List[str] = Field(default_factory=list, description="Related domains")
    primary_domain: Optional[DomainCategory] = None

    # Metrics
    relevance: float = Field(default=0.5, ge=0.0, le=1.0, description="Current relevance")
    cohesion: float = Field(default=0.5, ge=0.0, le=1.0, description="Cluster cohesion")
    size: int = Field(default=0, description="Number of news items")
    freshness: float = Field(default=1.0, ge=0.0, le=1.0, description="Recency score")

    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)

    # Status
    is_active: bool = Field(default=True)
    is_editorial: bool = Field(default=False, description="Editor confirmed/locked")

    class Config:
        use_enum_values = True


class Domain(BaseModel):
    """Domain/subdomain hierarchy"""
    id: str = Field(..., description="Unique domain ID")
    name: str
    category: DomainCategory
    parent_id: Optional[str] = None
    description: str = Field(default="")
    keywords: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True
