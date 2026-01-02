"""
Script to recompute embeddings for all news items in the database
Useful when switching from mock to real embeddings
"""
import sys
import os
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.embedding_service import EmbeddingService
from backend.services.database_manager import DatabaseManager
from backend.models.entities import News
from dotenv import load_dotenv

load_dotenv()


def recompute_embeddings(
    backend: str = "local",
    batch_size: int = 32,
    force_recompute: bool = False,
    limit: Optional[int] = None
):
    """
    Recompute embeddings for all news items
    
    Args:
        backend: Backend to use ("local", "gemini", or "mock")
        batch_size: Number of news items to process at once
        force_recompute: If True, recompute even if embedding exists
        limit: Maximum number of news items to process (None for all)
    """
    print("="*60)
    print("Recomputing Embeddings")
    print("="*60)
    print(f"Backend: {backend}")
    print(f"Batch size: {batch_size}")
    print(f"Force recompute: {force_recompute}")
    if limit:
        print(f"Limit: {limit} news items")
    print()
    
    # Initialize services
    db = DatabaseManager()
    embedding_service = EmbeddingService(backend=backend)
    
    if embedding_service.backend == "mock":
        print("Warning: Using mock embeddings. Set EMBEDDING_BACKEND=local for real embeddings.")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Get all news
    print("Loading news from database...")
    all_news = db.get_all_news(limit=limit)
    
    # Filter news that need embeddings
    if force_recompute:
        news_to_process = all_news
        print(f"Processing {len(news_to_process)} news items (force recompute)")
    else:
        news_to_process = [n for n in all_news if not n.embedding]
        print(f"Found {len(news_to_process)} news items without embeddings")
        print(f"Skipping {len(all_news) - len(news_to_process)} news items with existing embeddings")
    
    if not news_to_process:
        print("No news items to process.")
        return
    
    # Process in batches
    total = len(news_to_process)
    processed = 0
    failed = 0
    
    print(f"\nProcessing {total} news items in batches of {batch_size}...")
    print("-"*60)
    
    for i in range(0, total, batch_size):
        batch = news_to_process[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        print(f"Batch {batch_num}/{total_batches} ({len(batch)} items)...", end=" ", flush=True)
        
        # Prepare texts
        texts = []
        news_ids = []
        for news in batch:
            text = f"{news.title}. {news.summary or ''}"
            texts.append(text)
            news_ids.append(news.id)
        
        try:
            # Generate embeddings
            embeddings = embedding_service.encode(texts)
            
            # Update database
            for news, embedding in zip(batch, embeddings):
                news.embedding = embedding.tolist()
                db.save_news(news)
            
            processed += len(batch)
            print(f"✓ ({processed}/{total})")
            
        except Exception as e:
            failed += len(batch)
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("-"*60)
    print(f"\nCompleted:")
    print(f"  Processed: {processed}")
    print(f"  Failed: {failed}")
    print(f"  Total: {total}")
    
    if processed > 0:
        print(f"\n✓ Successfully recomputed embeddings for {processed} news items")
    
    if failed > 0:
        print(f"⚠ Failed to process {failed} news items")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Recompute embeddings for news items")
    parser.add_argument(
        "--backend",
        choices=["local", "gemini", "mock"],
        default=os.getenv("EMBEDDING_BACKEND", "local"),
        help="Embedding backend to use (default: from EMBEDDING_BACKEND env var or 'local')"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for processing (default: 32)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recompute even if embedding exists"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of news items to process (default: all)"
    )
    
    args = parser.parse_args()
    
    recompute_embeddings(
        backend=args.backend,
        batch_size=args.batch_size,
        force_recompute=args.force,
        limit=args.limit
    )


if __name__ == "__main__":
    main()

