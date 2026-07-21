import httpx
import math
import asyncio
from typing import List, Optional
from src.utils.logger import logger
from src import config

class EmbeddingService:
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        # Since text-embedding-3-large is an OpenAI model and supported by OpenRouter
        self.embedding_model = "text-embedding-3-large"
        self._cache = {}

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        Retries up to 3 times on failure.
        """
        if text in self._cache:
            return self._cache[text]

        if not self.api_key:
            logger.warning("No API Key found. Skipping embedding generation.")
            # Fallback to zero vector for graceful failure if keys aren't set
            return [0.0] * 3072

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"input": text, "model": self.embedding_model, "dimensions": 384}
                    )
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        embedding = data["data"][0]["embedding"]
                        # OpenAI's v3 models are trained with Matryoshka representation learning.
                        # This means we can safely truncate them to 384 dimensions without losing much accuracy.
                        if len(embedding) > 384:
                            embedding = embedding[:384]
                        self._cache[text] = embedding
                        return embedding
                    else:
                        logger.warning(f"Embedding API error (attempt {attempt+1}/{max_retries}): {resp.status_code} - {resp.text}")
                        if attempt == max_retries - 1:
                            raise ValueError(f"HTTP {resp.status_code}: {resp.text}")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                logger.error(f"Failed to generate embedding (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        return dot_product / (norm_a * norm_b)

# Singleton instance
embedding_service = EmbeddingService()
