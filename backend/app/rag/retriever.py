from dataclasses import dataclass
import numpy as np
from .loader import RagStore


@dataclass
class RetrievedChunk:
    text: str
    metadata: dict
    score: float


def _unpack(item):
    if isinstance(item, str):
        return item, {}
    if isinstance(item, dict):
        text = item.get("text") or item.get("chunk") or item.get("content") or ""
        inner_meta = item.get("metadata")
        meta = dict(inner_meta) if isinstance(inner_meta, dict) else {}
        for key in ("scheme_name", "slug", "url", "source_url", "source", "category", "row_number"):
            if key in item and key not in meta:
                meta[key] = item[key]
        return str(text), meta
    return str(item), {}


class Retriever:
    def __init__(self, store: RagStore):
        self.store = store

    def search(self, question: str, top_k: int) -> list[RetrievedChunk]:
        vector = self.store.model.encode([question], normalize_embeddings=True, convert_to_numpy=True)
        vector = np.asarray(vector, dtype="float32")
        if vector.shape[1] != self.store.index.d:
            raise ValueError("Question embedding dimension does not match FAISS index")
        scores, indexes = self.store.index.search(vector, min(top_k, len(self.store.chunks)))
        results, seen = [], set()
        for score, index in zip(scores[0], indexes[0]):
            if index < 0:
                continue
            text, metadata = _unpack(self.store.chunks[int(index)])
            key = text.strip()
            if key and key not in seen:
                seen.add(key)
                results.append(RetrievedChunk(key, metadata, float(score)))
        return results
