"""
Benchmark script for comparing embedding backends
Compares local (sentence-transformers) vs mock embeddings
"""
import sys
import os
from pathlib import Path
import time
import numpy as np
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.embedding_service import EmbeddingService
from backend.models.entities import News
import json


def load_test_news(limit: int = 50) -> List[News]:
    """Load test news from database or JSON"""
    news_file = project_root / "data" / "news.json"
    if news_file.exists():
        with open(news_file, 'r', encoding='utf-8') as f:
            news_data = json.load(f)
            news_list = [News(**item) for item in news_data[:limit]]
            return news_list
    return []


def prepare_texts(news_list: List[News]) -> List[str]:
    """Prepare texts for embedding from news"""
    texts = []
    for news in news_list:
        text = f"{news.title}. {news.summary or ''}"
        texts.append(text)
    return texts


def benchmark_backend(backend: str, texts: List[str], api_key: Optional[str] = None) -> dict:
    """Benchmark a specific backend"""
    print(f"\n{'='*60}")
    print(f"Benchmarking {backend.upper()} backend")
    print(f"{'='*60}")
    
    # Initialize service
    start_init = time.time()
    if backend == "gemini":
        service = EmbeddingService(backend="gemini", api_key=api_key)
    elif backend == "local":
        service = EmbeddingService(backend="local")
    else:
        service = EmbeddingService(backend="mock")
    init_time = time.time() - start_init
    
    print(f"Initialization time: {init_time:.2f}s")
    print(f"Backend: {service.backend}")
    print(f"Embedding dimension: {service.get_embedding_dimension()}")
    
    # Warm-up (first call is usually slower)
    if len(texts) > 0:
        _ = service.encode(texts[0])
    
    # Benchmark encoding
    num_texts = len(texts)
    print(f"\nEncoding {num_texts} texts...")
    
    start_encode = time.time()
    embeddings = service.encode(texts)
    encode_time = time.time() - start_encode
    
    # Calculate metrics
    avg_time_per_text = encode_time / num_texts if num_texts > 0 else 0
    texts_per_second = num_texts / encode_time if encode_time > 0 else 0
    
    # Check embedding quality (similarity between similar texts)
    if num_texts >= 2:
        similarity = service.compute_similarity(embeddings[0], embeddings[1])
    else:
        similarity = None
    
    results = {
        "backend": backend,
        "num_texts": num_texts,
        "init_time": init_time,
        "encode_time": encode_time,
        "avg_time_per_text": avg_time_per_text,
        "texts_per_second": texts_per_second,
        "embedding_dimension": service.get_embedding_dimension(),
        "sample_similarity": similarity
    }
    
    print(f"\nResults:")
    print(f"  Total encoding time: {encode_time:.2f}s")
    print(f"  Average time per text: {avg_time_per_text*1000:.2f}ms")
    print(f"  Texts per second: {texts_per_second:.1f}")
    if similarity is not None:
        print(f"  Sample similarity (first two texts): {similarity:.3f}")
    
    return results


def compare_embeddings(embeddings1: np.ndarray, embeddings2: np.ndarray) -> dict:
    """Compare two sets of embeddings"""
    if embeddings1.shape != embeddings2.shape:
        return {"error": "Shape mismatch"}
    
    # Compute pairwise similarities
    from sklearn.metrics.pairwise import cosine_similarity
    
    similarities = []
    for i in range(min(len(embeddings1), len(embeddings2))):
        sim = cosine_similarity(
            embeddings1[i:i+1],
            embeddings2[i:i+1]
        )[0][0]
        similarities.append(sim)
    
    return {
        "mean_similarity": np.mean(similarities),
        "std_similarity": np.std(similarities),
        "min_similarity": np.min(similarities),
        "max_similarity": np.max(similarities)
    }


def main():
    """Run benchmark"""
    print("="*60)
    print("Embedding Backend Benchmark")
    print("="*60)
    
    # Load test data
    print("\nLoading test data...")
    news_list = load_test_news(limit=50)
    if not news_list:
        print("Error: No test news found. Please ensure data/news.json exists.")
        return
    
    texts = prepare_texts(news_list)
    print(f"Loaded {len(texts)} news items for testing")
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Benchmark each backend
    results = {}
    
    # Mock backend (baseline)
    results["mock"] = benchmark_backend("mock", texts)
    
    # Local backend (sentence-transformers)
    results["local"] = benchmark_backend("local", texts)
    
    # Gemini backend (if API key available)
    if api_key:
        results["gemini"] = benchmark_backend("gemini", texts, api_key)
    else:
        print("\nSkipping Gemini benchmark: GEMINI_API_KEY not set")
    
    # Compare embeddings quality (mock vs local)
    if "mock" in results and "local" in results:
        print("\n" + "="*60)
        print("Comparing Mock vs Local Embeddings")
        print("="*60)
        
        mock_service = EmbeddingService(backend="mock")
        local_service = EmbeddingService(backend="local")
        
        mock_emb = mock_service.encode(texts)
        local_emb = local_service.encode(texts)
        
        comparison = compare_embeddings(mock_emb, local_emb)
        print(f"Mean similarity: {comparison['mean_similarity']:.3f}")
        print(f"Std similarity: {comparison['std_similarity']:.3f}")
        print(f"Min similarity: {comparison['min_similarity']:.3f}")
        print(f"Max similarity: {comparison['max_similarity']:.3f}")
        results["comparison"] = comparison
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Backend':<15} {'Time (s)':<12} {'Texts/s':<12} {'Dim':<8}")
    print("-" * 60)
    for backend, res in results.items():
        if isinstance(res, dict) and "encode_time" in res:
            print(f"{res['backend']:<15} {res['encode_time']:<12.2f} {res['texts_per_second']:<12.1f} {res['embedding_dimension']:<8}")
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    if "local" in results:
        local_res = results["local"]
        if local_res["texts_per_second"] > 10:
            print("✓ Local backend (sentence-transformers) is fast enough for production")
            print("  Recommended for: Real-time processing, large batches")
        else:
            print("⚠ Local backend may be slow for large volumes")
    
    if "gemini" in results:
        gemini_res = results["gemini"]
        print("✓ Gemini backend available")
        print("  Consider for: Cloud deployment, when local resources are limited")
    
    print("\nTo use a specific backend, set EMBEDDING_BACKEND environment variable:")
    print("  export EMBEDDING_BACKEND=local    # Use sentence-transformers")
    print("  export EMBEDDING_BACKEND=gemini  # Use Gemini API (requires API key)")
    print("  export EMBEDDING_BACKEND=mock    # Use mock embeddings (default)")


if __name__ == "__main__":
    from typing import List, Optional
    main()

