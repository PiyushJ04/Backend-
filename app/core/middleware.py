import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error request_id=%s path=%s", request_id, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    logger.info("%s %s -> %s %.2fms request_id=%s", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
    return response


async def body_limit_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body exceeds the configured size limit"},
                    headers={"X-Request-ID": getattr(request.state, "request_id", "")},
                )
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


async def rate_limit_middleware(request: Request, call_next):
    if not settings.rate_limit_enabled or request.url.path.endswith("/health") or request.url.path.endswith("/health/ready"):
        return await call_next(request)

    redis: Redis | None = getattr(request.app.state, "redis_client", None)
    if redis is None:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    is_auth = request.url.path.startswith(f"{settings.api_v1_prefix}/auth/")
    limit = settings.auth_rate_limit_per_minute if is_auth else settings.rate_limit_per_minute
    bucket = int(time.time() // 60)
    key = f"ratelimit:{client_ip}:{'auth' if is_auth else 'api'}:{bucket}"

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 70)
        if count > limit:
            retry_after = 60 - (int(time.time()) % 60)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )
    except Exception:
        # Redis outage must not make the application unusable. Readiness will still
        # report the dependency failure and operators can act on it.
        logger.warning("Rate limiter unavailable; allowing request", exc_info=True)

    return await call_next(request)
