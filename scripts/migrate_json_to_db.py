"""
Migration script: JSON files → PostgreSQL database
Migrates all data from JSON files to PostgreSQL + pgvector
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.database_manager import DatabaseManager
from backend.models.entities import (
    News, Actor, Story, Event, Domain, ActorType, EventType, DomainCategory
)


def migrate_actors(db: DatabaseManager, data_dir: str) -> Dict[str, Actor]:
    """Migrate actors from JSON to database"""
    actors_file = Path(data_dir) / "actors.json"
    if not actors_file.exists():
        print("No actors.json found, skipping actors migration")
        return {}
    
    print(f"Migrating actors from {actors_file}...")
    with open(actors_file, 'r', encoding='utf-8') as f:
        actors_data = json.load(f)
    
    actors = {}
    for item in actors_data:
        # Convert actor_type string to enum if needed
        if isinstance(item.get('actor_type'), str):
            try:
                item['actor_type'] = ActorType(item['actor_type'])
            except ValueError:
                item['actor_type'] = ActorType.ORGANIZATION
        
        actor = Actor(**item)
        db.save_actor(actor)
        actors[actor.id] = actor
    
    print(f"✓ Migrated {len(actors)} actors")
    return actors


def migrate_news(db: DatabaseManager, data_dir: str, skip_story_id: bool = False) -> Dict[str, News]:
    """Migrate news from JSON to database"""
    news_file = Path(data_dir) / "news.json"
    if not news_file.exists():
        print("No news.json found, skipping news migration")
        return {}
    
    print(f"Migrating news from {news_file}...")
    with open(news_file, 'r', encoding='utf-8') as f:
        news_data = json.load(f)
    
    news_items = {}
    for item in news_data:
        # Convert published_at string to datetime
        if 'published_at' in item and item['published_at']:
            if isinstance(item['published_at'], str):
                item['published_at'] = datetime.fromisoformat(item['published_at'])
        
        # Convert created_at if present
        if 'created_at' in item and item['created_at']:
            if isinstance(item['created_at'], str):
                item['created_at'] = datetime.fromisoformat(item['created_at'])
        
        news = News(**item)
        # Temporarily clear story_id to avoid FK violations
        if skip_story_id:
            original_story_id = news.story_id
            news.story_id = None
            db.save_news(news)
            news.story_id = original_story_id  # Restore for later update
        else:
            db.save_news(news)
        news_items[news.id] = news
    
    print(f"✓ Migrated {len(news_items)} news items")
    return news_items


def migrate_stories(db: DatabaseManager, data_dir: str) -> Dict[str, Story]:
    """Migrate stories from JSON to database"""
    stories_file = Path(data_dir) / "stories.json"
    if not stories_file.exists():
        print("No stories.json found, skipping stories migration")
        return {}
    
    print(f"Migrating stories from {stories_file}...")
    with open(stories_file, 'r', encoding='utf-8') as f:
        stories_data = json.load(f)
    
    stories = {}
    for item in stories_data:
        # Convert dates
        for date_field in ['first_seen', 'last_activity', 'created_at', 'updated_at']:
            if date_field in item and item[date_field]:
                if isinstance(item[date_field], str):
                    item[date_field] = datetime.fromisoformat(item[date_field])
        
        # Convert primary_domain to enum if present
        if 'primary_domain' in item and item['primary_domain']:
            if isinstance(item['primary_domain'], str):
                try:
                    item['primary_domain'] = DomainCategory(item['primary_domain'])
                except ValueError:
                    item['primary_domain'] = None
        
        # Fill missing fields
        if not item.get('summary'):
            item['summary'] = f"Auto summary for {item.get('title', 'Story')}"
        if not item.get('bullets'):
            item['bullets'] = [f"Key point for {item.get('title', 'story')}"]
        if not item.get('domains'):
            item['domains'] = []
        if not item.get('top_actors'):
            item['top_actors'] = []
        if not item.get('news_ids'):
            item['news_ids'] = []
        if not item.get('core_news_ids'):
            item['core_news_ids'] = []
        if not item.get('event_ids'):
            item['event_ids'] = []
        
        story = Story(**item)
        db.save_story(story)
        stories[story.id] = story
    
    print(f"✓ Migrated {len(stories)} stories")
    return stories


def migrate_events_from_news(db: DatabaseManager, news_items: Dict[str, News]):
    """Extract and migrate events from news items"""
    from backend.services.event_extraction_service import EventExtractionService
    
    print("Extracting and migrating events from news...")
    event_service = EventExtractionService()
    
    total_events = 0
    for news in news_items.values():
        events = event_service.extract_events_from_news(news)
        for event in events:
            # Ensure story linkage
            if not event.story_id:
                event.story_id = news.story_id
            db.save_event(event)
            total_events += 1
    
    print(f"✓ Migrated {total_events} events")
    return total_events


def validate_migration(db: DatabaseManager, expected_counts: Dict[str, int]):
    """Validate migration by comparing counts"""
    print("\nValidating migration...")
    
    actual_news = len(db.get_all_news())
    actual_actors = len(db.get_all_actors())
    actual_stories = len(db.get_all_stories(active_only=False))
    
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM events")
            actual_events = cur.fetchone()[0]
    
    print(f"Expected: {expected_counts.get('news', 0)} news, {expected_counts.get('actors', 0)} actors, "
          f"{expected_counts.get('stories', 0)} stories, {expected_counts.get('events', 0)} events")
    print(f"Actual:   {actual_news} news, {actual_actors} actors, "
          f"{actual_stories} stories, {actual_events} events")
    
    if (actual_news == expected_counts.get('news', 0) and
        actual_actors == expected_counts.get('actors', 0) and
        actual_stories == expected_counts.get('stories', 0)):
        print("✓ Migration validation passed")
        return True
    else:
        print("⚠ Migration validation failed - counts don't match")
        return False


def main():
    """Main migration function"""
    data_dir = os.getenv("DATA_DIR", "data")
    
    print("=" * 60)
    print("JSON to PostgreSQL Migration")
    print("=" * 60)
    
    # Initialize database manager
    try:
        db = DatabaseManager()
        print("✓ Connected to database")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        print("\nPlease ensure PostgreSQL is running and pgvector extension is installed.")
        print("Set environment variables: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT")
        return 1
    
    # Migrate data (order matters: actors -> news (without story_id) -> stories -> update news -> events)
    expected_counts = {}
    
    actors = migrate_actors(db, data_dir)
    expected_counts['actors'] = len(actors)
    
    # First migrate news without story_id to avoid FK violations
    news_items = migrate_news(db, data_dir, skip_story_id=True)
    expected_counts['news'] = len(news_items)
    
    # Then migrate stories (which reference news)
    stories = migrate_stories(db, data_dir)
    expected_counts['stories'] = len(stories)
    
    # Update news with story_id
    print("\nUpdating news with story assignments...")
    for news in news_items.values():
        if news.story_id:
            db.save_news(news)  # Update with story_id
    print(f"✓ Updated {sum(1 for n in news_items.values() if n.story_id)} news with story assignments")
    
    # Extract and migrate events
    events_count = migrate_events_from_news(db, news_items)
    expected_counts['events'] = events_count
    
    # Compute similarities
    print("\nComputing news similarities...")
    relations = db.compute_news_similarities(threshold=0.6)
    print(f"✓ Computed {len(relations)} news relations")
    
    # Validate
    validate_migration(db, expected_counts)
    
    print("\n" + "=" * 60)
    print("Migration completed!")
    print("=" * 60)
    
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

