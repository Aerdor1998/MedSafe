"""
Middleware de métricas Prometheus
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from prometheus_client import Counter, Histogram, Gauge

# Métricas Prometheus
REQUEST_COUNT = Counter(
    'medsafe_requests_total',
    'Total de requisições HTTP',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'medsafe_request_duration_seconds',
    'Duração das requisições HTTP',
    ['method', 'endpoint']
)

REQUEST_IN_PROGRESS = Gauge(
    'medsafe_requests_in_progress',
    'Requisições em andamento'
)

ACTIVE_SESSIONS = Gauge(
    'medsafe_active_sessions',
    'Sessões ativas'
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware para coletar métricas Prometheus
    """
    
    async def dispatch(self, request: Request, call_next):
        # Incrementar requisições em andamento
        REQUEST_IN_PROGRESS.inc()
        
        # Iniciar timer
        start_time = time.time()
        
        try:
            # Processar requisição
            response = await call_next(request)
            
            # Calcular duração
            duration = time.time() - start_time
            
            # Registrar métricas
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            return response
            
        finally:
            # Decrementar requisições em andamento
            REQUEST_IN_PROGRESS.dec()


