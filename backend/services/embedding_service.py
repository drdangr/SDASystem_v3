"""
Embedding service for generating text embeddings
Supports multiple backends: sentence-transformers (local), Gemini API (cloud), or mock
"""
import numpy as np
import os
from typing import List, Union, Optional, Literal
import time


class EmbeddingService:
    """Service for generating text embeddings with multiple backends"""

    def __init__(
        self,
        backend: Optional[Literal["local", "gemini", "mock"]] = None,
        model_name: str = "all-MiniLM-L6-v2",
        api_key: Optional[str] = None,
        use_mock: Optional[bool] = None
    ):
        """
        Initialize embedding service

        Args:
            backend: Backend to use ("local" for sentence-transformers, "gemini" for Gemini API, "mock" for mock)
                    If None, determined from env vars or defaults to "mock"
            model_name: SentenceTransformer model name (for local backend)
            api_key: Gemini API key (for gemini backend). If None, uses GEMINI_API_KEY env var
            use_mock: Deprecated - use backend="mock" instead. If True, forces mock mode
        """
        # Determine backend from env or parameter
        if backend is None:
            backend = os.getenv("EMBEDDING_BACKEND", "mock").lower()
        
        # Legacy support: use_mock parameter
        if use_mock is True:
            backend = "mock"
        elif use_mock is False and backend == "mock":
            backend = "local"  # Default to local if use_mock=False
        
        self.backend = backend
        self.model_name = model_name
        self.model = None
        self.gemini_client = None
        self.gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        # Initialize backend
        if self.backend == "local":
            self._init_local()
        elif self.backend == "gemini":
            self._init_gemini()
        elif self.backend == "mock":
            print("Using mock embeddings (set EMBEDDING_BACKEND=local or EMBEDDING_BACKEND=gemini for real embeddings)")
        else:
            raise ValueError(f"Unknown embedding backend: {self.backend}. Must be 'local', 'gemini', or 'mock'")

    def _init_local(self):
        """Initialize sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            print(f"Loading sentence-transformers model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print(f"Model loaded successfully. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        except ImportError:
            error_msg = "sentence-transformers not installed. Install with: pip install sentence-transformers"
            print(f"ERROR: {error_msg}")
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Error loading sentence-transformers model: {e}"
            print(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg)

    def _init_gemini(self):
        """Initialize Gemini API client"""
        if not self.gemini_api_key:
            error_msg = "GEMINI_API_KEY not set. Set it in environment variables or pass api_key parameter."
            print(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            # Check if embedding model is available
            # Note: Gemini doesn't have a dedicated embedding model, but we can use text-embedding-004
            # For now, we'll use the generative model and extract embeddings if available
            # This is a placeholder - actual implementation depends on Gemini API capabilities
            self.gemini_client = genai
            print("Gemini API client initialized")
        except ImportError:
            error_msg = "google-generativeai not installed. Install with: pip install google-generativeai"
            print(f"ERROR: {error_msg}")
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Error initializing Gemini API: {e}"
            print(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg)

    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for text(s)

        Args:
            texts: Single text or list of texts
            batch_size: Batch size for processing (for local backend)

        Returns:
            Numpy array of embeddings
        """
        if isinstance(texts, str):
            texts = [texts]

        if self.backend == "local":
            return self._encode_local(texts, batch_size)
        elif self.backend == "gemini":
            return self._encode_gemini(texts)
        else:
            return self._mock_encode(texts)

    def _encode_local(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings using sentence-transformers"""
        if self.model is None:
            return self._mock_encode(texts)
        
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return np.array(embeddings)

    def _encode_gemini(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings using Gemini API
        Note: Gemini doesn't have a dedicated embedding endpoint, so this is a placeholder
        For now, we'll use a workaround or fall back to local/mock
        """
        # TODO: Implement Gemini embedding API when available
        # For now, check if we can use text-embedding-004 or similar
        print("Warning: Gemini embedding API not yet implemented, falling back to mock")
        return self._mock_encode(texts)
        
        # Placeholder for future implementation:
        # try:
        #     import google.generativeai as genai
        #     embeddings = []
        #     for text in texts:
        #         # Use Gemini embedding model if available
        #         result = genai.embed_content(
        #             model="models/text-embedding-004",
        #             content=text
        #         )
        #         embeddings.append(result['embedding'])
        #     return np.array(embeddings)
        # except Exception as e:
        #     print(f"Error using Gemini embeddings: {e}")
        #     return self._mock_encode(texts)

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

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this service"""
        if self.backend == "local" and self.model:
            return self.model.get_sentence_embedding_dimension()
        elif self.backend == "gemini":
            # Gemini text-embedding-004 produces 768-dimensional embeddings
            return 768
        else:
            # Mock embeddings are 384-dimensional (matching MiniLM)
            return 384
