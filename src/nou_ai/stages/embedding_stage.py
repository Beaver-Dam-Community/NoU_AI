"""Stage 2: Embedding similarity search against known attack vectors."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from nou_ai.types import StageResult, StageName, Decision
from nou_ai.stages.base import BaseStage

logger = logging.getLogger("nou_ai")

_KNOWN_ATTACKS_PATH = Path(__file__).parent.parent / "patterns" / "known_attacks.json"


class EmbeddingStage(BaseStage):
    """Semantic vector search — compares input against known malicious prompts."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(StageName.EMBEDDING, config)
        self.similarity_threshold: float = self.config.get("similarity_threshold", 0.82)
        self.model_name: str = self.config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        self.top_k: int = self.config.get("top_k", 5)

        self._model = None
        self._index = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-load model and index on first use."""
        if self._initialized:
            return

        from nou_ai.embeddings.model import EmbeddingModel
        from nou_ai.embeddings.faiss_index import FaissIndex

        self._model = EmbeddingModel(self.model_name)
        self._index = FaissIndex(dimension=self._model.dimension)
        self._load_known_attacks()
        self._initialized = True

    def _load_known_attacks(self):
        """Load known malicious prompts from JSON and index them."""
        attacks_path = self.config.get("known_attacks_path", str(_KNOWN_ATTACKS_PATH))
        path = Path(attacks_path)
        if not path.exists():
            logger.warning("Known attacks file not found: %s", path)
            return

        with open(path) as f:
            data = json.load(f)

        texts = [a["text"] for a in data.get("attacks", [])]
        if not texts:
            return

        vectors = self._model.encode_batch(texts)
        metadata_list = [{"category": a.get("category", "")} for a in data["attacks"]]
        self._index.add_batch(vectors, texts, metadata_list)
        logger.info("Loaded %d known attack vectors", len(texts))

    def add_attack_vector(self, text: str, category: str = "custom"):
        """Add a new known attack vector at runtime."""
        self._ensure_initialized()
        vec = self._model.encode(text)
        self._index.add(vec, text=text, metadata={"category": category})

    def scan(self, text: str) -> StageResult:
        self._ensure_initialized()

        if self._index.size == 0:
            return StageResult(
                stage=StageName.EMBEDDING,
                decision=Decision.ALLOW,
                score=0.0,
                reason="No attack vectors loaded, skipping embedding check",
            )

        vec = self._model.encode(text)
        scores, indices, matched_texts = self._index.search(vec, k=self.top_k)

        if scores and scores[0] >= self.similarity_threshold:
            matched_idx = indices[0]
            matched_metadata = self._index._metadata[matched_idx] if 0 <= matched_idx < len(self._index._metadata) else {}
            return StageResult(
                stage=StageName.EMBEDDING,
                decision=Decision.BLOCK,
                score=scores[0],
                reason=f"Similar to known attack (score={scores[0]:.3f}): '{matched_texts[0][:80]}...'",
                metadata={
                    "top_score": scores[0],
                    "matched_text": matched_texts[0],
                    "matched_metadata": matched_metadata,
                    "top_k_scores": scores,
                },
            )

        best = scores[0] if scores else 0.0
        return StageResult(
            stage=StageName.EMBEDDING,
            decision=Decision.ALLOW,
            score=best,
            reason=f"No similar known attacks (best score={best:.3f}, threshold={self.similarity_threshold})",
            metadata={"top_score": best, "top_k_scores": scores},
        )

    async def scan_async(self, text: str) -> StageResult:
        self._ensure_initialized()

        if self._index.size == 0:
            return StageResult(
                stage=StageName.EMBEDDING,
                decision=Decision.ALLOW,
                score=0.0,
                reason="No attack vectors loaded, skipping embedding check",
            )

        vec = await self._model.encode_async(text)
        scores, indices, matched_texts = self._index.search(vec, k=self.top_k)

        if scores and scores[0] >= self.similarity_threshold:
            matched_idx = indices[0]
            matched_metadata = self._index._metadata[matched_idx] if 0 <= matched_idx < len(self._index._metadata) else {}
            return StageResult(
                stage=StageName.EMBEDDING,
                decision=Decision.BLOCK,
                score=scores[0],
                reason=f"Similar to known attack (score={scores[0]:.3f}): '{matched_texts[0][:80]}...'",
                metadata={
                    "top_score": scores[0],
                    "matched_text": matched_texts[0],
                    "matched_metadata": matched_metadata,
                    "top_k_scores": scores,
                },
            )

        best = scores[0] if scores else 0.0
        return StageResult(
            stage=StageName.EMBEDDING,
            decision=Decision.ALLOW,
            score=best,
            reason=f"No similar known attacks (best score={best:.3f}, threshold={self.similarity_threshold})",
            metadata={"top_score": best, "top_k_scores": scores},
        )
