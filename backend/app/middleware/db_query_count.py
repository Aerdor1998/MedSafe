"""
DB Query Count Middleware (N+1 detection)

Fase 1.5 (Queries N+1):
- Conta queries SQL por request (via SQLAlchemy engine events)
- Exibe header X-DB-Queries em DEBUG/TESTING
- Emite warning quando o número de queries sugere N+1
"""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Any, Callable, Optional

from sqlalchemy import event
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.db.database import engine

logger = logging.getLogger(__name__)

_query_count: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "db_query_count", default=None
)
_listener_installed: bool = False


def _ensure_listener_installed() -> None:
    global _listener_installed
    if _listener_installed:
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(  # type: ignore[no-redef]
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        current = _query_count.get()
        if current is None:
            return
        _query_count.set(current + 1)

    _listener_installed = True


class DBQueryCountMiddleware(BaseHTTPMiddleware):
    """
    Counts SQL queries per request to help detect N+1 problems.

    Enabled only in DEBUG/TESTING via middleware registration.
    """

    def __init__(self, app, warn_threshold: int = 50) -> None:
        super().__init__(app)
        self.warn_threshold = warn_threshold
        _ensure_listener_installed()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        token = _query_count.set(0)
        try:
            response: Response = await call_next(request)
        finally:
            count = _query_count.get() or 0
            _query_count.reset(token)

        # Only add header in debug-like scenarios
        if os.getenv("DEBUG", "").lower() in {"1", "true", "yes"} or os.getenv(
            "TESTING", ""
        ).lower() in {"1", "true", "yes"}:
            response.headers["X-DB-Queries"] = str(count)

        if count >= self.warn_threshold:
            logger.warning(
                "High DB query count (possible N+1)",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "query_count": count,
                },
            )

        return response
