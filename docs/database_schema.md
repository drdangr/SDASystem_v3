# Database Schema (PostgreSQL + pgvector)

Полная схема базы данных для SDASystem v3. Все вычислимые данные хранятся в PostgreSQL с использованием расширения pgvector для векторного поиска.

## Обзор

База данных содержит следующие основные сущности:
- **News** - новости с эмбеддингами (vector)
- **Actors** - акторы из NER (люди, компании, страны, организации)
- **Stories** - истории/сюжеты (кластеры новостей)
- **Events** - события для таймлайна (fact/opinion)
- **Domains** - домены/категории
- **Relations** - связи между сущностями (many-to-many)

## Таблицы

### 1. news
Основная таблица новостей с векторными эмбеддингами.

```sql
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
    story_id VARCHAR REFERENCES stories(id),
    duplicate_of VARCHAR REFERENCES news(id),
    
    -- Metadata
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    editorial_notes TEXT
);
```

### 2. actors
Акторы, извлеченные через NER.

```sql
CREATE TABLE actors (
    id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL,
    actor_type VARCHAR NOT NULL,  -- person, company, country, etc.
    wikidata_qid VARCHAR,
    metadata JSONB,  -- для гибких полей (positions, country, birth_date, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3. actor_aliases
Алиасы акторов (many-to-many).

```sql
CREATE TABLE actor_aliases (
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    alias VARCHAR NOT NULL,
    alias_type VARCHAR,  -- canonical, nickname, typo, etc.
    PRIMARY KEY (actor_id, alias)
);
```

### 4. actor_relations
Связи между акторами.

```sql
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
```

### 5. news_relations
Связи между новостями (similarity).

```sql
CREATE TABLE news_relations (
    source_news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    target_news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    similarity FLOAT NOT NULL,
    weight FLOAT DEFAULT 1.0,
    is_editorial BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (source_news_id, target_news_id)
);
```

### 6. news_actors
Связь новостей и акторов (many-to-many).

```sql
CREATE TABLE news_actors (
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    confidence FLOAT DEFAULT 0.5,
    PRIMARY KEY (news_id, actor_id)
);
```

### 7. events
События для таймлайна.

```sql
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    story_id VARCHAR REFERENCES stories(id),
    event_type VARCHAR NOT NULL,  -- fact, opinion
    title VARCHAR NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    extracted_at TIMESTAMP DEFAULT NOW(),
    source_trust FLOAT DEFAULT 0.5,
    confidence FLOAT DEFAULT 0.7
);
```

### 8. event_actors
Связь событий и акторов (many-to-many).

```sql
CREATE TABLE event_actors (
    event_id VARCHAR REFERENCES events(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, actor_id)
);
```

### 9. stories
Истории/сюжеты (кластеры новостей).

```sql
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
```

### 10. story_news
Связь историй и новостей (many-to-many).

```sql
CREATE TABLE story_news (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    is_core BOOLEAN DEFAULT FALSE,  -- для core_news_ids
    PRIMARY KEY (story_id, news_id)
);
```

### 11. story_actors
Связь историй и акторов (top_actors, many-to-many).

```sql
CREATE TABLE story_actors (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    actor_id VARCHAR REFERENCES actors(id) ON DELETE CASCADE,
    mention_count INTEGER DEFAULT 1,  -- для сортировки top_actors
    PRIMARY KEY (story_id, actor_id)
);
```

### 12. story_events
Связь историй и событий (many-to-many).

```sql
CREATE TABLE story_events (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    event_id VARCHAR REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, event_id)
);
```

### 13. domains
Домены/категории.

```sql
CREATE TABLE domains (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,  -- politics, economics, etc.
    parent_id VARCHAR REFERENCES domains(id),
    description TEXT,
    keywords JSONB  -- массив строк
);
```

### 14. news_domains
Связь новостей и доменов (many-to-many).

```sql
CREATE TABLE news_domains (
    news_id VARCHAR REFERENCES news(id) ON DELETE CASCADE,
    domain_id VARCHAR REFERENCES domains(id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, domain_id)
);
```

### 15. story_domains
Связь историй и доменов (many-to-many).

```sql
CREATE TABLE story_domains (
    story_id VARCHAR REFERENCES stories(id) ON DELETE CASCADE,
    domain_id VARCHAR REFERENCES domains(id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, domain_id)
);
```

## Индексы

### Векторный индекс для поиска похожих новостей
```sql
CREATE INDEX news_embedding_idx ON news 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### Индексы для частых запросов
```sql
CREATE INDEX news_story_id_idx ON news(story_id);
CREATE INDEX news_published_at_idx ON news(published_at);
CREATE INDEX news_source_idx ON news(source);
CREATE INDEX actors_canonical_name_idx ON actors(canonical_name);
CREATE INDEX actors_wikidata_qid_idx ON actors(wikidata_qid);
CREATE INDEX actor_relations_source_idx ON actor_relations(source_actor_id);
CREATE INDEX actor_relations_target_idx ON actor_relations(target_actor_id);
CREATE INDEX news_actors_actor_idx ON news_actors(actor_id);
CREATE INDEX events_story_id_idx ON events(story_id);
CREATE INDEX events_event_date_idx ON events(event_date);
CREATE INDEX events_news_id_idx ON events(news_id);
CREATE INDEX stories_is_active_idx ON stories(is_active);
CREATE INDEX stories_relevance_idx ON stories(relevance DESC);
CREATE INDEX story_news_news_idx ON story_news(news_id);
```

## Установка и настройка

1. Установить PostgreSQL (версия 12+)
2. Установить расширение pgvector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Создать базу данных:
   ```sql
   CREATE DATABASE sdas_db;
   ```
4. Применить схему из `backend/db/schema.sql`

## Миграция данных

Использовать скрипт `scripts/migrate_json_to_db.py` для переноса данных из JSON файлов в PostgreSQL.

## Тестирование

После настройки схемы рекомендуется запустить тесты для проверки корректности работы:

```bash
source venv/bin/activate
python -m pytest tests/test_database_manager.py -v
```

Все 36 тестов должны пройти успешно. Подробный отчет: [docs/database_tests_report.md](database_tests_report.md)

## Примечания

- Размер вектора embedding (384) соответствует модели `all-MiniLM-L6-v2`. При использовании другой модели размер нужно изменить.
- JSONB используется для гибких полей (metadata, bullets, keywords).
- Все связи many-to-many реализованы через отдельные таблицы.
- Векторный индекс ivfflat оптимален для средних объемов данных (до 1M векторов). Для больших объемов можно использовать hnsw.

## Дополнительные ресурсы

- [Database Setup Guide](database_setup.md)
- [Migration Guide](DATABASE_MIGRATION.md)
- [Test Report](database_tests_report.md)

