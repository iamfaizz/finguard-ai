"""ChromaDB retrieval. Embeddings run LOCALLY (all-MiniLM-L6-v2) - no API key needed."""
from dataclasses import dataclass

from app.config import settings


@dataclass
class RetrievedChunk:
    id: str
    doc_id: str
    text: str
    title: str
    source_url: str
    section: str
    as_of: str
    distance: float


class Retriever:
    def __init__(self) -> None:
        self._model = None
        self._col = None

    def warm(self) -> None:
        """Load model + open the collection once at startup (first request stays fast)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(settings.embed_model)
        if self._col is None:
            import chromadb

            client = chromadb.PersistentClient(path=settings.chroma_path)
            self._col = client.get_or_create_collection(
                settings.chroma_collection, metadata={"hnsw:space": "cosine"}
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.warm()
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    @property
    def collection(self):
        self.warm()
        return self._col

    def count(self) -> int:
        return self.collection.count()

    def search(self, query: str, k: int | None = None, use_threshold: bool = True) -> list[RetrievedChunk]:
        col = self.collection
        if col.count() == 0:
            return []
        res = col.query(
            query_embeddings=self.embed([query]),
            n_results=k or settings.top_k,
            include=["documents", "metadatas", "distances"],
        )
        out: list[RetrievedChunk] = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            if use_threshold and dist > settings.max_distance:
                continue
            out.append(RetrievedChunk(
                id=cid, doc_id=meta["doc_id"], text=doc, title=meta["title"],
                source_url=meta["source_url"], section=meta.get("section", ""),
                as_of=meta["as_of"], distance=dist,
            ))
        return out
