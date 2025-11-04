"""
Circuit Breaker para resiliência de serviços externos
"""

from circuitbreaker import circuit
import logging
from typing import Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)


# Circuit breakers configurados
@circuit(failure_threshold=5, recovery_timeout=60, expected_exception=Exception)
async def call_ollama_with_circuit_breaker(func: Callable, *args, **kwargs) -> Any:
    """
    Chamar Ollama API com circuit breaker

    Args:
        func: Função a ser chamada
        *args, **kwargs: Argumentos da função

    Returns:
        Resultado da função

    Raises:
        CircuitBreakerError: Se o circuit breaker estiver aberto
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ollama API call failed: {e}")
        raise


@circuit(failure_threshold=3, recovery_timeout=30, expected_exception=Exception)
async def call_external_api_with_circuit_breaker(
    func: Callable, *args, **kwargs
) -> Any:
    """
    Chamar API externa com circuit breaker

    Args:
        func: Função a ser chamada
        *args, **kwargs: Argumentos da função

    Returns:
        Resultado da função

    Raises:
        CircuitBreakerError: Se o circuit breaker estiver aberto
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"External API call failed: {e}")
        raise


def with_circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60):
    """
    Decorator para adicionar circuit breaker a uma função

    Args:
        failure_threshold: Número de falhas antes de abrir o circuit
        recovery_timeout: Tempo em segundos para tentar recuperar

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @circuit(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
        )
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{func.__name__} failed: {e}")
                raise

        return wrapper

    return decorator


class CircuitBreakerManager:
    """Gerenciador de circuit breakers"""

    @staticmethod
    def get_status() -> dict:
        """
        Obter status de todos os circuit breakers

        Returns:
            Dict com status dos circuits
        """
        # Implementar lógica para coletar status
        return {
            "ollama": "closed",
            "external_api": "closed",
        }

    @staticmethod
    def reset_all():
        """Resetar todos os circuit breakers"""
        # Implementar lógica para resetar
        logger.info("All circuit breakers reset")
