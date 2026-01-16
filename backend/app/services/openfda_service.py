"""
Cliente OpenFDA para buscar eventos adversos e bulas (drug labels).
Compatível com testes existentes e utilizado como fallback/validação.

SKILLS: @api-design-principles, @python-performance-optimization

RESILIENCE PATTERNS:
- Circuit breaker para evitar cascading failures
- Cache TTL global para reduzir chamadas à API
- Retry com backoff exponencial
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..utils.cache import get_cached_openfda, set_cached_openfda

logger = logging.getLogger(__name__)


# Circuit breaker específico para OpenFDA
# - 3 falhas consecutivas abre o circuit
# - 60 segundos de recovery timeout
# - Exceções esperadas: HTTPError, TimeoutException, ConnectError
OPENFDA_CIRCUIT_FAILURE_THRESHOLD = 3
OPENFDA_CIRCUIT_RECOVERY_TIMEOUT = 60


class OpenFDAService:
    """
    Cliente assíncrono para OpenFDA Drug API.

    Features:
    - Circuit breaker para resiliência (3 falhas = 60s cooldown)
    - Cache TTL global (1h para labels)
    - Retry automático com backoff exponencial
    - Rate limiting respeitando limites da API
    """

    # Circuit breaker state tracking
    _circuit_open: bool = False
    _circuit_open_time: Optional[datetime] = None

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        self.base_url = "https://api.fda.gov/drug"
        self.timeout = timeout
        self.api_key = api_key or getattr(settings, "openfda_api_key", None)
        self.session = httpx.AsyncClient(timeout=self.timeout)
        self.max_retries = 3
        self.retry_delay = 1.0  # segundos
        self._failure_count = 0

    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker allows request.

        Returns:
            True if request can proceed, False if circuit is open
        """
        if not self._circuit_open:
            return True

        # Check if recovery timeout has passed
        if self._circuit_open_time:
            elapsed = (datetime.now() - self._circuit_open_time).total_seconds()
            if elapsed >= OPENFDA_CIRCUIT_RECOVERY_TIMEOUT:
                logger.info(f"OpenFDA circuit breaker HALF-OPEN (testing recovery)")
                self._circuit_open = False
                self._failure_count = 0
                return True

        logger.warning(f"OpenFDA circuit breaker OPEN - skipping request")
        return False

    def _record_success(self):
        """Record successful request, reset failure count."""
        self._failure_count = 0
        if self._circuit_open:
            logger.info("OpenFDA circuit breaker CLOSED (recovered)")
            self._circuit_open = False
            self._circuit_open_time = None

    def _record_failure(self):
        """Record failed request, potentially open circuit."""
        self._failure_count += 1
        if self._failure_count >= OPENFDA_CIRCUIT_FAILURE_THRESHOLD:
            if not self._circuit_open:
                logger.warning(
                    f"OpenFDA circuit breaker OPEN "
                    f"(failures={self._failure_count}, cooldown={OPENFDA_CIRCUIT_RECOVERY_TIMEOUT}s)"
                )
                self._circuit_open = True
                self._circuit_open_time = datetime.now()

    def get_circuit_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": "open" if self._circuit_open else "closed",
            "failure_count": self._failure_count,
            "threshold": OPENFDA_CIRCUIT_FAILURE_THRESHOLD,
            "recovery_timeout": OPENFDA_CIRCUIT_RECOVERY_TIMEOUT,
            "open_since": (
                self._circuit_open_time.isoformat() if self._circuit_open_time else None
            ),
        }

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """GET request com circuit breaker, retry e backoff exponencial."""
        # Check circuit breaker first
        if not self._check_circuit_breaker():
            return {"results": [], "_circuit_breaker": True}

        req_params = {**params}
        if self.api_key:
            req_params["api_key"] = self.api_key

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self.session.get(
                    f"{self.base_url}/{path}", params=req_params
                )
                resp.raise_for_status()
                self._record_success()
                return resp.json()
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limit
                    wait_time = self.retry_delay * (2**attempt)
                    logger.warning(f"OpenFDA rate limit, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code == 404:
                    self._record_success()  # 404 is not a failure
                    return {"results": []}  # Not found = empty
                else:
                    self._record_failure()
                    raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                wait_time = self.retry_delay * (2**attempt)
                logger.warning(
                    f"OpenFDA connection error, retry {attempt+1}/{self.max_retries}"
                )
                await asyncio.sleep(wait_time)

        # All retries exhausted - record failure
        self._record_failure()
        logger.error(
            f"OpenFDA request failed after {self.max_retries} retries: {last_error}"
        )
        raise last_error if last_error else Exception("OpenFDA request failed")

    async def get_adverse_events(
        self, drug_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Busca eventos adversos relacionados ao medicamento."""
        params = {
            "search": f'patient.drug.medicinalproduct:"{drug_name}"',
            "limit": max(1, min(limit, 100)),
        }
        data = await self._get("event.json", params=params)
        return data.get("results", []) or []

    async def get_drug_label(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca bula/rótulo do medicamento com cache TTL global.

        Features:
        - Cache TTL global (1h) via utils/cache.py
        - Circuit breaker para resiliência
        - Retorna dict com _circuit_breaker=True se circuit estiver aberto
        """
        # Check global cache first
        cached = get_cached_openfda(drug_name)
        if cached is not None:
            logger.debug(f"OpenFDA global cache hit: {drug_name}")
            return cached

        # Fetch from API (circuit breaker checked in _get)
        params = {
            "search": f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"',
            "limit": 1,
        }

        try:
            data = await self._get("label.json", params=params)

            # Check if circuit breaker blocked the request
            if data.get("_circuit_breaker"):
                logger.warning(f"OpenFDA skipped for {drug_name} (circuit breaker)")
                return {"_circuit_breaker": True, "drug_name": drug_name}

            results = data.get("results", []) or []
            result = results[0] if results else None

            # Store in global cache (even None to prevent repeated lookups)
            set_cached_openfda(drug_name, result)
            logger.debug(f"OpenFDA cached: {drug_name}")

            return result
        except Exception as e:
            logger.warning(f"OpenFDA label fetch failed for {drug_name}: {e}")
            return None

    async def get_drug_info_enriched(self, drug_name: str) -> Dict[str, Any]:
        """Retorna informações combinadas (label + eventos)."""
        label = await self.get_drug_label(drug_name)
        events = await self.get_adverse_events(drug_name, limit=5)
        return {
            "drug_name": drug_name,
            "label": label,
            "adverse_events": events,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def close(self):
        await self.session.aclose()
