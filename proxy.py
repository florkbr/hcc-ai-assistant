"""Reverse proxy that strips the /api/ai-assistant prefix before forwarding
requests to the lightspeed-stack backend running on an internal port."""

import logging
import os
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("PROXY_BACKEND_URL", "http://localhost:8080")
STRIP_PREFIX = os.getenv("PROXY_STRIP_PREFIX", "/api/ai-assistant")

# Hop-by-hop headers that should not be forwarded
SKIP_REQUEST_HEADERS = frozenset({"host", "transfer-encoding"})
SKIP_RESPONSE_HEADERS = frozenset({"transfer-encoding", "content-length"})


@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient(timeout=300.0)
    yield
    await app.state.client.aclose()


async def proxy_request(request: Request) -> Response:
    """Forward a request to the backend, stripping the path prefix."""
    path = request.url.path
    if path.startswith(STRIP_PREFIX):
        path = path[len(STRIP_PREFIX):] or "/"

    url = f"{BACKEND_URL}{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    body = await request.body()

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in SKIP_REQUEST_HEADERS
    }

    client = request.app.state.client

    try:
        backend_request = client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

        backend_response = await client.send(backend_request, stream=True)
    except httpx.ConnectError:
        logger.error("Backend unavailable at %s", BACKEND_URL)
        return Response("Backend unavailable", status_code=502)

    response_headers = {
        k: v
        for k, v in backend_response.headers.items()
        if k.lower() not in SKIP_RESPONSE_HEADERS
    }

    async def stream_body():
        try:
            async for chunk in backend_response.aiter_bytes():
                yield chunk
        finally:
            await backend_response.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=backend_response.status_code,
        headers=response_headers,
    )


# Catch-all routes — forwards everything to the backend
_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", proxy_request, methods=_methods),
        Route("/{path:path}", proxy_request, methods=_methods),
    ],
)
