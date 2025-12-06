"""
Normalization utilities for raw feed items -> News-compatible dicts.
"""
import uuid
from datetime import datetime
from typing import Dict, Any


def normalize_raw_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw connector item to News dict."""
    return {
        "id": raw.get("id") or f"news_{uuid.uuid4().hex[:12]}",
        "title": raw.get("title", "Untitled"),
        "summary": raw.get("summary", "")[:500],
        "full_text": raw.get("full_text", ""),
        "url": raw.get("url"),
        "source": raw.get("source", "unknown"),
        "author": raw.get("author"),
        "published_at": raw.get("published_at") or datetime.utcnow(),
        "mentioned_actors": raw.get("mentioned_actors", []),
        "related_news_ids": [],
        "story_id": raw.get("story_id"),
        "domains": raw.get("domains", []),
        "is_duplicate": False,
        "duplicate_of": None,
        "is_pinned": False,
        "editorial_notes": "",
    }

