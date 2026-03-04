from __future__ import annotations

from typing import List

from openai import OpenAI

from backend.app.core.settings import settings


class EmbeddingClient:
    """
    Client for generating text embeddings using OpenAI's embedding models.
    
    Uses text-embedding-3-small by default (1536 dimensions).
    """

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small"):
        """
        Initialize the embedding client.
        
        Args:
            api_key: OpenAI API key. If None, uses settings.openai_api_key
            model: Embedding model name. Defaults to text-embedding-3-small (1536 dim)
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise RuntimeError("openai_api_key is not configured. Set OPENAI_API_KEY in env.local")
        
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        
        # Model dimension mapping
        self.model_dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
    
    def get_dimension(self) -> int:
        """Get the dimension size for the current model."""
        return self.model_dimensions.get(self.model, 1536)
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding vector
        """
        if not text or not text.strip():
            # Return zero vector if text is empty
            return [0.0] * self.get_dimension()
        
        response = self.client.embeddings.create(
            model=self.model,
            input=text.strip()
        )
        
        return response.data[0].embedding
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each API call
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # Filter out empty texts
            non_empty_batch = [t.strip() for t in batch if t and t.strip()]
            
            if not non_empty_batch:
                # Add zero vectors for empty texts
                all_embeddings.extend([[0.0] * self.get_dimension()] * len(batch))
                continue
            
            response = self.client.embeddings.create(
                model=self.model,
                input=non_empty_batch
            )
            
            # Map embeddings back to original batch (handling empty texts)
            batch_embeddings = []
            batch_idx = 0
            for text in batch:
                if text and text.strip():
                    batch_embeddings.append(response.data[batch_idx].embedding)
                    batch_idx += 1
                else:
                    batch_embeddings.append([0.0] * self.get_dimension())
            
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings


# Global instance (lazy initialization)
_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """Get or create the global embedding client instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient(
            model=settings.embedding_model
        )
    return _embedding_client


def embed_text(text: str) -> List[float]:
    """
    Convenience function to generate an embedding for text.
    
    This is the main function to use throughout the codebase.
    """
    client = get_embedding_client()
    return client.embed_text(text)

