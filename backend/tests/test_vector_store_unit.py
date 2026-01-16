from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://medsafe:test_password@localhost:5432/medsafe"
    )


@dataclass
class _Doc:
    page_content: str
    metadata: Dict[str, Any]


class _FakeSplitter:
    def split_text(self, text: str) -> List[str]:
        return [text[:5], text[5:]] if len(text) > 5 else [text]


class _FakeVectorStore:
    def __init__(self):
        self.added = []
        self.search_calls = []

    def add_documents(self, docs):
        self.added.extend(docs)

    def similarity_search_with_score(
        self, query: str, k: int, filter=None
    ):  # noqa: A002
        self.search_calls.append((query, k, filter))
        return [(_Doc("c1", {"a": 1}), 0.7), (_Doc("c2", {"b": 2}), 0.1)]


class _FakeCache:
    def __init__(self):
        self._d = {}

    def get(self, key):
        return self._d.get(key)

    def set(self, key, value):
        self._d[key] = value


class _FakeDBResult(list):
    def fetchone(self):
        return self[0] if self else None


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []
        self.committed = False

    def execute(self, stmt, params=None):  # noqa: ARG002
        self.executed.append(str(stmt))
        return _FakeDBResult(self.rows)

    def commit(self):
        self.committed = True


def _make_store(mod):
    store = mod.MedicalVectorStore.__new__(mod.MedicalVectorStore)
    store.collection_name = "medical_literature"
    store.vector_store = _FakeVectorStore()
    store.text_splitter = _FakeSplitter()
    return store


def test_add_documents_chunks_and_calls_vector_store(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    docs = [
        {
            "text": "abcdef",
            "metadata": {"x": 1},
            "drug_name": "A",
            "source": "S",
            "section": "sec",
        }
    ]
    chunks = store.add_documents(docs, batch_size=10)
    assert chunks == 2
    assert len(store.vector_store.added) == 2


def test_semantic_search_formats_results_and_relevance(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    out = store.semantic_search("q", k=2, filter_dict={"drug_name": "a"})
    assert len(out) == 2
    assert out[0]["content"] == "c1"
    assert out[0]["relevance"] in {"VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"}


def test_hybrid_search_uses_cache_and_rrf(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    fake_cache = _FakeCache()
    monkeypatch.setattr(mod, "rag_search_cache", fake_cache, raising=True)

    # Make keyword search deterministic
    monkeypatch.setattr(
        store,
        "_keyword_search",
        lambda query, k=5, filter_dict=None: [
            {"content": "c1", "metadata": {}, "score": 0.2, "relevance": "LOW"}
        ],  # noqa: ARG002
        raising=True,
    )

    r1 = store.hybrid_search("hello", k=1, semantic_weight=0.7, filter_dict=None)
    assert r1
    # Second call should be cache hit
    r2 = store.hybrid_search("hello", k=1, semantic_weight=0.7, filter_dict=None)
    assert r2 == r1


def test_rrf_combines_and_updates_relevance(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    semantic = [{"content": "a", "metadata": {}, "score": 0.9, "relevance": "HIGH"}]
    keyword = [{"content": "b", "metadata": {}, "score": 0.9, "relevance": "HIGH"}]
    combined = store._reciprocal_rank_fusion(
        semantic, keyword, semantic_weight=0.5, k=60
    )
    assert len(combined) == 2
    assert all("relevance" in d for d in combined)


def test_score_to_relevance_thresholds(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    assert store._score_to_relevance(0.9) == "VERY_HIGH"
    assert store._score_to_relevance(0.7) == "HIGH"
    assert store._score_to_relevance(0.5) == "MEDIUM"
    assert store._score_to_relevance(0.3) == "LOW"
    assert store._score_to_relevance(0.1) == "VERY_LOW"


def test_search_by_drug_builds_filter_and_delegates(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)
    calls = {"args": None}

    def _sem(query, k=5, filter_dict=None):  # noqa: ARG002
        calls["args"] = (query, k, filter_dict)
        return [{"content": "x"}]

    monkeypatch.setattr(store, "semantic_search", _sem, raising=True)
    out = store.search_by_drug("Aspirin", section="warnings", k=3)
    assert out == [{"content": "x"}]
    q, k, f = calls["args"]
    assert k == 3
    assert f["drug_name"] == "aspirin"
    assert f["section"] == "warnings"


def test_get_collection_stats_success_and_delete_collection(monkeypatch):
    from backend.app.db import vector_store as mod

    store = _make_store(mod)

    @contextlib.contextmanager
    def _ctx_stats():
        yield _FakeDB(rows=[(10, 2, 1)])

    monkeypatch.setattr(mod, "get_db_context", _ctx_stats, raising=True)
    stats = store.get_collection_stats()
    assert stats["total_embeddings"] == 10
    assert stats["unique_drugs"] == 2

    @contextlib.contextmanager
    def _ctx_delete():
        yield _FakeDB(rows=[])

    monkeypatch.setattr(mod, "get_db_context", _ctx_delete, raising=True)
    assert store.delete_collection() is True


def test_get_vector_store_singleton(monkeypatch):
    from backend.app.db import vector_store as mod

    class _FakeVS:
        def __init__(self):
            self.x = 1

    monkeypatch.setattr(mod, "MedicalVectorStore", _FakeVS, raising=True)
    monkeypatch.setattr(mod, "_vector_store_instance", None, raising=True)
    a = mod.get_vector_store()
    b = mod.get_vector_store()
    assert a is b
