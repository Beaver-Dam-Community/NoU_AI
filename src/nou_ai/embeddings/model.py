"""Sentence-transformers embedding model wrapper with lazy loading."""

import asyncio
from typing import List, Optional

import numpy as np


class EmbeddingModel:
    """Wraps sentence-transformers for text-to-vector conversion."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def dimension(self) -> int:
        # all-MiniLM-L6-v2 outputs 384-dim vectors
        return 384

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def encode(self, text: str) -> np.ndarray:
        """Encode a single text into a vector."""
        self._ensure_model()
        return self._model.encode(text, normalize_embeddings=True)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode multiple texts into vectors."""
        self._ensure_model()
        return self._model.encode(texts, normalize_embeddings=True)

    async def encode_async(self, text: str) -> np.ndarray:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encode, text)
