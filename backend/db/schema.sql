-- SDASystem v3 Database Schema
-- PostgreSQL + pgvector

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. News table (with embeddings)
CREATE TABLE news (
    id VARCHAR PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    full_text TEXT,
    url VARCHAR,
    source VARCHAR NOT NULL,
    author VARCHAR,
    published_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Embedding (pgvector)
    embedding vector(384),  -- размер зависит от модели (MiniLM = 384)
    
    -- Relations
    story_id VARCHAR,
    duplicate_of VARCHAR,
    
    -- Metadata
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    editorial_notes TEXT
);

-- 2. Actors table
CREATE TABLE actors (
    id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL,
    actor_type VARCHAR NOT NULL,  -- person, company, country, etc.
    wikidata_qid VARCHAR,
    metadata JSONB,  -- для гибких полей (positions, country, birth_date, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. Actor aliases (many-to-many)
CREATE TABLE actor_aliases (
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    alias VARCHAR NOT NULL,
    alias_type VARCHAR,  -- canonical, nickname, typo, etc.
    PRIMARY KEY (actor_id, alias)
);

-- 4. Actor relations
CREATE TABLE actor_relations (
    id VARCHAR PRIMARY KEY,
    source_actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    target_actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    relation_type VARCHAR NOT NULL,  -- member_of, ally_of, etc.
    weight FLOAT DEFAULT 1.0,
    confidence FLOAT DEFAULT 0.8,
    is_ephemeral BOOLEAN DEFAULT FALSE,
    ttl_days INTEGER,
    expires_at TIMESTAMP,
    source VARCHAR DEFAULT 'auto',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_actor_id, target_actor_id, relation_type)
);

-- 5. News relations (similarity)
CREATE TABLE news_relations (
    source_news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    target_news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    similarity FLOAT NOT NULL,
    weight FLOAT DEFAULT 1.0,
    is_editorial BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (source_news_id, target_news_id)
);

-- 6. News-Actors (many-to-many)
CREATE TABLE news_actors (
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 0.5,
    PRIMARY KEY (news_id, actor_id)
);

-- 7. Events table
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    story_id VARCHAR,
    event_type VARCHAR NOT NULL,  -- fact, opinion
    title VARCHAR NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    extracted_at TIMESTAMP DEFAULT NOW(),
    source_trust FLOAT DEFAULT 0.5,
    confidence FLOAT DEFAULT 0.7
);

-- 8. Event-Actors (many-to-many)
CREATE TABLE event_actors (
    event_id VARCHAR REFERENCES events(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, actor_id)
);

-- 9. Stories table
CREATE TABLE stories (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    summary TEXT,
    bullets JSONB,  -- массив строк
    primary_domain VARCHAR,  -- politics, economics, etc.
    relevance FLOAT DEFAULT 0.5,
    cohesion FLOAT DEFAULT 0.5,
    size INTEGER DEFAULT 0,
    freshness FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    is_editorial BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW()
);

-- 10. Story-News (many-to-many)
CREATE TABLE story_news (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    is_core BOOLEAN DEFAULT FALSE,  -- для core_news_ids
    PRIMARY KEY (story_id, news_id)
);

-- 11. Story-Actors (many-to-many)
CREATE TABLE story_actors (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    mention_count INTEGER DEFAULT 1,  -- для сортировки top_actors
    PRIMARY KEY (story_id, actor_id)
);

-- 12. Story-Events (many-to-many)
CREATE TABLE story_events (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    event_id VARCHAR REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, event_id)
);

-- 13. Domains table
CREATE TABLE domains (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,  -- politics, economics, etc.
    parent_id VARCHAR REFERENCES domains(id),
    description TEXT,
    keywords JSONB  -- массив строк
);

-- 14. News-Domains (many-to-many)
CREATE TABLE news_domains (
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    domain_id VARCHAR REFERENCES domains(id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, domain_id)
);

-- 15. Story-Domains (many-to-many)
CREATE TABLE story_domains (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    domain_id VARCHAR REFERENCES domains(id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, domain_id)
);

-- Add foreign key constraints after stories table exists
ALTER TABLE news ADD CONSTRAINT fk_news_story FOREIGN KEY (story_id) REFERENCES stories(id);
ALTER TABLE news ADD CONSTRAINT fk_news_duplicate FOREIGN KEY (duplicate_of) REFERENCES news(id);
ALTER TABLE events ADD CONSTRAINT fk_events_story FOREIGN KEY (story_id) REFERENCES stories(id);

-- Indexes

-- Vector index for similarity search
CREATE INDEX news_embedding_idx ON news 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- News indexes
CREATE INDEX news_story_id_idx ON news(story_id);
CREATE INDEX news_published_at_idx ON news(published_at);
CREATE INDEX news_source_idx ON news(source);

-- Actor indexes
CREATE INDEX actors_canonical_name_idx ON actors(canonical_name);
CREATE INDEX actors_wikidata_qid_idx ON actors(wikidata_qid);
CREATE INDEX actors_actor_type_idx ON actors(actor_type);

-- Actor relations indexes
CREATE INDEX actor_relations_source_idx ON actor_relations(source_actor_id);
CREATE INDEX actor_relations_target_idx ON actor_relations(target_actor_id);

-- News-Actors indexes
CREATE INDEX news_actors_actor_idx ON news_actors(actor_id);
CREATE INDEX news_actors_news_idx ON news_actors(news_id);

-- Event indexes
CREATE INDEX events_story_id_idx ON events(story_id);
CREATE INDEX events_event_date_idx ON events(event_date);
CREATE INDEX events_news_id_idx ON events(news_id);
CREATE INDEX events_event_type_idx ON events(event_type);

-- Story indexes
CREATE INDEX stories_is_active_idx ON stories(is_active);
CREATE INDEX stories_relevance_idx ON stories(relevance DESC);
CREATE INDEX stories_primary_domain_idx ON stories(primary_domain);

-- Story-News indexes
CREATE INDEX story_news_news_idx ON story_news(news_id);
CREATE INDEX story_news_story_idx ON story_news(story_id);

-- Story-Actors indexes
CREATE INDEX story_actors_actor_idx ON story_actors(actor_id);
CREATE INDEX story_actors_story_idx ON story_actors(story_id);

-- Domain indexes
CREATE INDEX domains_category_idx ON domains(category);
CREATE INDEX domains_parent_id_idx ON domains(parent_id);

