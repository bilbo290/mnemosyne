from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

MODEL_NAME = "all-MiniLM-L6-v2"

_ef: SentenceTransformerEmbeddingFunction | None = None


def get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    """Return a cached SentenceTransformerEmbeddingFunction for ChromaDB."""
    global _ef
    if _ef is None:
        _ef = SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    return _ef
