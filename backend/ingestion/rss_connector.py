"""
RSS connector stub.
Fetches feed and yields normalized dicts (not persisted).
"""
from typing import List, Dict


class RSSConnector:
    def __init__(self, feed_urls: List[str]):
        self.feed_urls = feed_urls

    def fetch(self) -> List[Dict]:
        # TODO: implement real RSS fetching. For now return stub.
        results = []
        for url in self.feed_urls:
            results.append({
                "source": url,
                "title": "Mock RSS item",
                "summary": "This is a mock RSS entry.",
                "full_text": "Mock content from RSS.",
                "published_at": None,
                "url": url,
            })
        return results

