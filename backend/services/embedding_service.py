"""
Embedding service for generating text embeddings
Uses sentence-transformers for semantic similarity
"""
import numpy as np
from typing import List, Union, Optional


class EmbeddingService:
    """Service for generating text embeddings"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", use_mock: bool = True):
        """
        Initialize embedding service

        Args:
            model_name: SentenceTransformer model name
            use_mock: Use mock embeddings for prototype (faster, no model download)
        """
        self.use_mock = use_mock
        self.model_name = model_name
        self.model = None

        if not use_mock:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(model_name)
            except ImportError:
                print("Warning: sentence-transformers not installed, using mock embeddings")
                self.use_mock = True

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text(s)

        Args:
            texts: Single text or list of texts

        Returns:
            Numpy array of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]

        if self.use_mock:
            return self._mock_encode(texts)
        else:
            embeddings = self.model.encode(texts)
            return np.array(embeddings)

    def _mock_encode(self, texts: List[str]) -> np.ndarray:
        """
        Generate mock embeddings based on simple text features
        For prototype only - replace with real embeddings for production
        """
        embeddings = []

        for text in texts:
            # Create pseudo-embedding from text features
            text_lower = text.lower()

            # Simple feature extraction (384 dimensions to match MiniLM)
            embedding = np.zeros(384)

            # Word counts for different topics (simplified)
            keywords = {
                # Politics (dims 0-30)
                0: ['политика', 'politics', 'government', 'правительство', 'выборы', 'election'],
                # Economics (dims 31-60)
                31: ['экономика', 'economy', 'бизнес', 'business', 'финансы', 'finance'],
                # Technology (dims 61-90)
                61: ['технологии', 'technology', 'ai', 'искусственный интеллект', 'software'],
                # Military (dims 91-120)
                91: ['военный', 'military', 'война', 'war', 'армия', 'army'],
                # Health (dims 121-150)
                121: ['здоровье', 'health', 'медицина', 'medicine', 'covid'],
                # Culture (dims 151-180)
                151: ['культура', 'culture', 'искусство', 'art', 'film', 'кино'],
            }

            # Set features based on keyword presence
            for start_dim, words in keywords.items():
                for i, word in enumerate(words):
                    if word in text_lower:
                        embedding[start_dim + i] = 1.0

            # Add some randomness for variation
            np.random.seed(hash(text) % (2**32))
            noise = np.random.normal(0, 0.1, 384)
            embedding += noise

            # Add text length feature
            embedding[200] = min(1.0, len(text) / 500)

            # Add word count feature
            embedding[201] = min(1.0, len(text.split()) / 100)

            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            embeddings.append(embedding)

        return np.array(embeddings)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings"""
        from sklearn.metrics.pairwise import cosine_similarity

        # Reshape if needed
        if embedding1.ndim == 1:
            embedding1 = embedding1.reshape(1, -1)
        if embedding2.ndim == 1:
            embedding2 = embedding2.reshape(1, -1)

        similarity = cosine_similarity(embedding1, embedding2)[0][0]
        return float(similarity)

    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[np.ndarray],
        top_k: int = 10,
        threshold: float = 0.5
    ) -> List[tuple]:
        """
        Find most similar embeddings

        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (index, similarity) tuples, sorted by similarity
        """
        from sklearn.metrics.pairwise import cosine_similarity

        if not candidate_embeddings:
            return []

        # Compute similarities
        query_emb = query_embedding.reshape(1, -1)
        candidate_matrix = np.array(candidate_embeddings)

        similarities = cosine_similarity(query_emb, candidate_matrix)[0]

        # Filter and sort
        results = [
            (i, float(sim))
            for i, sim in enumerate(similarities)
            if sim >= threshold
        ]
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]
