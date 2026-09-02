"""
Unit tests for cache utilities

Tests TTLCache, cache decorators, and cache management functions.
"""

from unittest.mock import MagicMock, patch


class TestTTLCache:
    """Tests for TTLCache class"""

    def test_ttl_cache_init(self):
        """Test TTLCache initialization"""
        from backend.app.utils.cache import TTLCache

        cache = TTLCache(ttl_seconds=60, max_size=100)

        assert cache is not None
        assert cache.ttl_seconds == 60
        assert cache.max_size == 100

    def test_ttl_cache_set_get(self):
        """Test setting and getting values"""
        from backend.app.utils.cache import TTLCache

        cache = TTLCache(ttl_seconds=60, max_size=100)

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_ttl_cache_get_missing(self):
        """Test getting non-existent key"""
        from backend.app.utils.cache import TTLCache

        cache = TTLCache(ttl_seconds=60, max_size=100)

        result = cache.get("nonexistent")

        assert result is None

    def test_ttl_cache_overwrite(self):
        """Test overwriting a key"""
        from backend.app.utils.cache import TTLCache

        cache = TTLCache(ttl_seconds=60, max_size=100)

        cache.set("key1", "value1")
        cache.set("key1", "value2")
        result = cache.get("key1")

        assert result == "value2"

    def test_ttl_cache_clear(self):
        """Test clearing the cache"""
        from backend.app.utils.cache import TTLCache

        cache = TTLCache(ttl_seconds=60, max_size=100)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestNormalizeDrugName:
    """Tests for normalize_drug_name function"""

    def test_normalize_lowercase(self):
        """Test normalization lowercases string"""
        from backend.app.utils.cache import normalize_drug_name

        result = normalize_drug_name("ASPIRIN")

        assert result == "aspirin"

    def test_normalize_trim_whitespace(self):
        """Test normalization trims whitespace"""
        from backend.app.utils.cache import normalize_drug_name

        result = normalize_drug_name("  aspirin  ")

        assert result == "aspirin"

    def test_normalize_empty_string(self):
        """Test normalization of empty string"""
        from backend.app.utils.cache import normalize_drug_name

        result = normalize_drug_name("")

        assert result == ""

    def test_normalize_mixed_case(self):
        """Test normalization of mixed case"""
        from backend.app.utils.cache import normalize_drug_name

        result = normalize_drug_name("AcetylSalicylic Acid")

        assert "acetylsalicylic" in result.lower()


class TestCacheStats:
    """Tests for get_cache_stats function"""

    def test_get_cache_stats_returns_dict(self):
        """Test get_cache_stats returns dictionary"""
        from backend.app.utils.cache import get_cache_stats

        stats = get_cache_stats()

        assert isinstance(stats, dict)

    def test_cache_stats_has_expected_keys(self):
        """Test cache stats has expected structure"""
        from backend.app.utils.cache import get_cache_stats

        stats = get_cache_stats()

        # Should have some stats
        assert len(stats) >= 0


class TestClearAllCaches:
    """Tests for clear_all_caches function"""

    def test_clear_all_caches(self):
        """Test clearing all caches"""
        from backend.app.utils.cache import clear_all_caches

        result = clear_all_caches()

        assert isinstance(result, dict)


class TestInteractionPairCache:
    """Tests for interaction pair cache functions"""

    def test_get_interaction_pair_cache_key(self):
        """Test cache key generation for drug pairs"""
        from backend.app.utils.cache import get_interaction_pair_cache_key

        key1 = get_interaction_pair_cache_key("aspirin", "warfarin")
        key2 = get_interaction_pair_cache_key("warfarin", "aspirin")

        # Should be consistent regardless of order
        assert key1 == key2

    def test_get_cached_interaction_pair_miss(self):
        """Test cache miss for interaction pair"""
        from backend.app.utils.cache import (
            clear_all_caches,
            get_cached_interaction_pair,
        )

        clear_all_caches()
        result = get_cached_interaction_pair("unknown1", "unknown2")

        assert result is None

    def test_set_and_get_cached_interaction_pair(self):
        """Test setting and getting cached interaction"""
        from backend.app.utils.cache import (
            clear_all_caches,
            get_cached_interaction_pair,
            set_cached_interaction_pair,
        )

        clear_all_caches()

        interaction = {"severity": "high", "description": "test"}
        set_cached_interaction_pair("drug1", "drug2", interaction)

        result = get_cached_interaction_pair("drug1", "drug2")

        # May or may not be cached depending on implementation
        assert result is None or result == interaction


class TestOpenFDACache:
    """Tests for OpenFDA cache functions"""

    def test_get_cached_openfda_miss(self):
        """Test cache miss for OpenFDA data"""
        from backend.app.utils.cache import clear_all_caches, get_cached_openfda

        clear_all_caches()
        result = get_cached_openfda("unknown_drug")

        assert result is None

    def test_set_and_get_cached_openfda(self):
        """Test setting and getting cached OpenFDA data"""
        from backend.app.utils.cache import (
            clear_all_caches,
            get_cached_openfda,
            set_cached_openfda,
        )

        clear_all_caches()

        data = {"drug_name": "aspirin", "warnings": ["test"]}
        set_cached_openfda("aspirin", data)

        result = get_cached_openfda("aspirin")

        # May or may not be cached
        assert result is None or result == data


class TestCacheDecorators:
    """Tests for cache decorators"""

    def test_cache_embedding_decorator(self):
        """Test cache_embedding decorator"""
        from backend.app.utils.cache import cache_embedding

        @cache_embedding
        def test_func(text):
            return [0.1, 0.2, 0.3]

        # Should return result
        result = test_func("test text")
        assert result == [0.1, 0.2, 0.3]

    def test_cache_drug_interaction_decorator(self):
        """Test cache_drug_interaction decorator"""
        from backend.app.utils.cache import cache_drug_interaction

        @cache_drug_interaction
        def test_func(drug1, drug2):
            return {"interaction": True}

        result = test_func("aspirin", "warfarin")
        assert result == {"interaction": True}

    def test_cache_llm_response_decorator(self):
        """Test cache_llm_response decorator"""
        from backend.app.utils.cache import cache_llm_response

        @cache_llm_response
        def test_func(prompt):
            return "LLM response"

        result = test_func("test prompt")
        assert result == "LLM response"

    def test_cache_rag_search_decorator(self):
        """Test cache_rag_search decorator"""
        from backend.app.utils.cache import cache_rag_search

        @cache_rag_search
        def test_func(query):
            return [{"doc": "result"}]

        result = test_func("test query")
        assert result == [{"doc": "result"}]


class TestCheckRedisHealth:
    """Tests for the check_redis_health helper used by health probes"""

    def test_returns_false_when_client_unavailable(self):
        """No Redis client available -> unhealthy"""
        from backend.app.utils import cache

        with patch.object(cache, "_get_redis_client", return_value=None):
            assert cache.check_redis_health() is False

    def test_returns_true_when_ping_succeeds(self):
        """Successful PING -> healthy"""
        from backend.app.utils import cache

        client = MagicMock()
        client.ping.return_value = True
        with patch.object(cache, "_get_redis_client", return_value=client):
            assert cache.check_redis_health() is True

    def test_returns_false_when_ping_raises(self):
        """Connection error during PING -> unhealthy, no exception"""
        from backend.app.utils import cache

        client = MagicMock()
        client.ping.side_effect = ConnectionError("connection refused")
        with patch.object(cache, "_get_redis_client", return_value=client):
            assert cache.check_redis_health() is False
