"""FAISS index wrapper for cosine similarity search."""

from typing import Dict, List, Optional, Tuple

import numpy as np


class FaissIndex:
    """Thin wrapper around FAISS IndexFlatIP (inner product = cosine after L2 norm)."""

    def __init__(self, dimension: int = 384):
        import faiss
        self.dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._metadata: List[Dict] = []
        self._texts: List[str] = []

    @property
    def size(self) -> int:
        return self._index.ntotal

    def add(self, vector: np.ndarray, text: str = "", metadata: Optional[Dict] = None):
        """Add a single normalized vector."""
        import faiss
        vec = np.array([vector], dtype=np.float32)
        faiss.normalize_L2(vec)
        self._index.add(vec)
        self._texts.append(text)
        self._metadata.append(metadata or {})

    def add_batch(self, vectors: np.ndarray, texts: List[str], metadata_list: Optional[List[Dict]] = None):
        """Add multiple normalized vectors."""
        import faiss
        vecs = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(vecs)
        self._index.add(vecs)
        self._texts.extend(texts)
        if metadata_list:
            self._metadata.extend(metadata_list)
        else:
            self._metadata.extend([{}] * len(texts))

    def search(self, vector: np.ndarray, k: int = 5) -> Tuple[List[float], List[int], List[str]]:
        """Search for k nearest neighbors. Returns (scores, indices, texts)."""
        import faiss
        vec = np.array([vector], dtype=np.float32)
        faiss.normalize_L2(vec)
        k = min(k, self.size) if self.size > 0 else 0
        if k == 0:
            return [], [], []
        scores, indices = self._index.search(vec, k)
        result_scores = scores[0].tolist()
        result_indices = indices[0].tolist()
        result_texts = [self._texts[i] for i in result_indices if 0 <= i < len(self._texts)]
        return result_scores, result_indices, result_texts

    def save(self, path: str):
        import faiss, json
        faiss.write_index(self._index, path)
        with open(path + ".meta.json", "w") as f:
            json.dump({"texts": self._texts, "metadata": self._metadata}, f)

    @classmethod
    def load(cls, path: str, dimension: int = 384) -> "FaissIndex":
        import faiss, json
        idx = cls(dimension)
        idx._index = faiss.read_index(path)
        with open(path + ".meta.json") as f:
            data = json.load(f)
        idx._texts = data["texts"]
        idx._metadata = data["metadata"]
        return idx
