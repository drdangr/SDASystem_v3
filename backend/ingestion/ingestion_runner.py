"""
Entry point for ingestion pipeline (stub).
"""
from typing import List

from backend.ingestion.rss_connector import RSSConnector
from backend.ingestion.normalizer import normalize_raw_item


def ingest_rss(feeds: List[str]):
    connector = RSSConnector(feeds)
    raw_items = connector.fetch()
    return [normalize_raw_item(item) for item in raw_items]

