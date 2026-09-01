import types

from backend.app.db import vector_store as vs


def test_score_to_relevance_thresholds():
    store = vs.MedicalVectorStore.__new__(vs.MedicalVectorStore)
    assert store._score_to_relevance(0.81) == "VERY_HIGH"
    assert store._score_to_relevance(0.7) == "HIGH"
    assert store._score_to_relevance(0.5) == "MEDIUM"
    assert store._score_to_relevance(0.3) == "LOW"
    assert store._score_to_relevance(0.1) == "VERY_LOW"


def test_reciprocal_rank_fusion_combines_lists():
    store = vs.MedicalVectorStore.__new__(vs.MedicalVectorStore)
    semantic = [{"content": "A", "metadata": {}, "score": 0.9, "relevance": "HIGH"}]
    keyword = [
        {"content": "B", "metadata": {}, "score": 0.9, "relevance": "HIGH"},
        {"content": "A", "metadata": {}, "score": 0.1, "relevance": "LOW"},
    ]
    combined = store._reciprocal_rank_fusion(
        semantic, keyword, semantic_weight=0.7, k=10
    )
    assert {c["content"] for c in combined} == {"A", "B"}
    assert all("relevance" in c for c in combined)


def test_hybrid_search_cache_hit(monkeypatch):
    store = vs.MedicalVectorStore.__new__(vs.MedicalVectorStore)
    store.collection_name = "medical_literature"

    monkeypatch.setattr(vs.rag_search_cache, "get", lambda key: [{"content": "cached"}])

    # If cache hits, semantic_search shouldn't be needed
    called = {"semantic": 0}

    def _semantic(*args, **kwargs):
        called["semantic"] += 1
        return []

    store.semantic_search = _semantic  # type: ignore[assignment]
    store._keyword_search = lambda *a, **k: []  # type: ignore[assignment]
    out = store.hybrid_search("aspirin", k=3)
    assert out == [{"content": "cached"}]
    assert called["semantic"] == 0


def test_hybrid_search_keyword_only_when_semantic_empty(monkeypatch):
    store = vs.MedicalVectorStore.__new__(vs.MedicalVectorStore)
    store.collection_name = "medical_literature"
    monkeypatch.setattr(vs.rag_search_cache, "get", lambda key: None)
    monkeypatch.setattr(vs.rag_search_cache, "set", lambda key, value: None)

    store.semantic_search = lambda *a, **k: []  # type: ignore[assignment]
    store._keyword_search = lambda *a, **k: [  # type: ignore[assignment]
        {"content": "kw", "metadata": {}, "score": 0.5, "relevance": "MEDIUM"}
    ]
    out = store.hybrid_search("aspirin", k=1)
    assert out and out[0]["content"] == "kw"


def test_medical_vector_store_init_and_semantic_search_without_real_db(monkeypatch):
    # Patch embeddings and PGVector to avoid network/DB
    class _Emb:
        def __init__(self, base_url, model):
            self.base_url = base_url
            self.model = model

    class _Doc:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata

    class _VS:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def similarity_search_with_score(self, query, k, filter=None):
            return [(_Doc("content", {"drug_name": "aspirin"}), 0.75)]

        def add_documents(self, docs):
            return None

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            return None

        def commit(self):
            return None

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(vs, "OllamaEmbeddings", _Emb)
    monkeypatch.setattr(vs, "PGVector", _VS)
    monkeypatch.setattr(vs, "engine", _Engine())

    # Ensure module-level settings has required attributes (Settings.database_url_safe is a property)
    fake_settings = types.SimpleNamespace(
        ollama_host="http://example",
        database_url_safe="postgresql://u:p@h:5432/db",
        embedding_model="qwen3-embedding:0.6b",
    )
    monkeypatch.setattr(vs, "settings", fake_settings, raising=True)

    store = vs.MedicalVectorStore()
    results = store.semantic_search("aspirin", k=1)
    assert results and results[0]["content"] == "content"
