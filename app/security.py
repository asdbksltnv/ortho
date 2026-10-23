from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    path = request.url.path
    if path.startswith("/assets/"):
        # Vite fingerprints these files, so they can be cached for a year.
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    elif not path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")  # index.html, sw.js, manifest
    if not request.url.path.startswith(_DOC_PATHS):  # Swagger UI loads assets from a CDN
        response.headers.setdefault("Content-Security-Policy", CSP)
    return response
