"""
Request ID / Correlation ID middleware.

Goals:
- Ensure every request has a stable request_id for logging and debugging
- Propagate request_id via response header (X-Request-ID)

Behavior:
- If client provides X-Request-ID, reuse it (trimmed, length-limited)
- Otherwise generate a UUID4
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    header_name: str = "X-Request-ID"
    max_len: int = 128

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(self.header_name)
        if incoming:
            request_id = incoming.strip()[: self.max_len]
        else:
            request_id = str(uuid.uuid4())

        # Store on request state for other middlewares/handlers
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[self.header_name] = request_id
        return response
