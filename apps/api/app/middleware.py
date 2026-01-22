"""
Production Middleware
=====================

Rate limiting and request logging for production deployments.

Usage:
    from app.middleware import setup_middleware
    setup_middleware(app)
"""

import time
import logging
import uuid
from datetime import datetime
from typing import Callable, Dict, Optional
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST LOGGING
# =============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all requests with timing and metadata.
    
    Log format:
    {timestamp} {method} {path} {status} {duration_ms} {request_id} {client_ip}
    """
    
    # Paths to exclude from logging (health checks, etc.)
    EXCLUDE_PATHS = {"/health", "/ready", "/favicon.ico"}
    
    # Headers to exclude from logging (sensitive data)
    EXCLUDE_HEADERS = {"authorization", "x-api-key", "cookie"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)
        
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Get client IP (handle proxies)
        client_ip = self._get_client_ip(request)
        
        # Start timing
        start_time = time.perf_counter()
        
        # Process request
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            status_code = response.status_code if response else 500
            
            # Log request
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", "")[:100],
            }
            
            # Log level based on status
            if status_code >= 500:
                logger.error(f"Request: {log_data}")
            elif status_code >= 400:
                logger.warning(f"Request: {log_data}")
            else:
                logger.info(f"Request: {log_data}")
            
            # Add request ID to response headers
            if response:
                response.headers["X-Request-ID"] = request_id
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        # Check X-Forwarded-For header (set by load balancers/proxies)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First IP in the list is the original client
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection IP
        if request.client:
            return request.client.host
        
        return "unknown"


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please slow down.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window.
    
    For production with multiple instances, use Redis-based limiter.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_limit: int = 100,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_seconds = 60
        
        # Store: {client_key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """
        Check if request is allowed.
        
        Returns:
            (is_allowed, requests_remaining)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Get requests in current window
        requests = self._requests[client_key]
        
        # Remove old requests outside window
        requests[:] = [r for r in requests if r > window_start]
        
        # Count requests in window
        request_count = len(requests)
        
        # Check burst limit (absolute max)
        if request_count >= self.burst_limit:
            return False, 0
        
        # Check rate limit
        if request_count >= self.requests_per_minute:
            return False, 0
        
        # Allow request
        requests.append(now)
        remaining = self.requests_per_minute - len(requests)
        
        return True, max(0, remaining)
    
    def cleanup(self):
        """Remove old entries to prevent memory growth."""
        now = time.time()
        window_start = now - self.window_seconds * 2
        
        for key in list(self._requests.keys()):
            self._requests[key] = [
                r for r in self._requests[key] if r > window_start
            ]
            if not self._requests[key]:
                del self._requests[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    
    Limits requests per client IP (or API key if authenticated).
    """
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json"}
    
    def __init__(
        self,
        app: FastAPI,
        requests_per_minute: int = 60,
        burst_limit: int = 100,
    ):
        super().__init__(app)
        self.limiter = InMemoryRateLimiter(
            requests_per_minute=requests_per_minute,
            burst_limit=burst_limit,
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Get client key (API key if present, otherwise IP)
        client_key = self._get_client_key(request)
        
        # Check rate limit
        is_allowed, remaining = self.limiter.is_allowed(client_key)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_key}")
            raise RateLimitExceeded(retry_after=60)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier for rate limiting."""
        # Check for API key (authenticated clients)
        api_key = request.headers.get("x-api-key")
        if api_key:
            # Hash the key for privacy
            return f"apikey:{hash(api_key) % 10**8}"
        
        # Fall back to IP
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        if request.client:
            return f"ip:{request.client.host}"
        
        return "ip:unknown"


# =============================================================================
# CORS CONFIGURATION
# =============================================================================

def get_cors_origins() -> list[str]:
    """Get CORS origins from settings."""
    return settings.cors_origins_list


# =============================================================================
# SETUP FUNCTION
# =============================================================================

def setup_middleware(app: FastAPI) -> None:
    """
    Configure all production middleware.
    
    Call this in your FastAPI app setup:
        from app.middleware import setup_middleware
        app = FastAPI()
        setup_middleware(app)
    """
    # Get configuration
    rate_limit = settings.rate_limit_requests
    rate_limit_burst = settings.rate_limit_burst
    cors_origins = get_cors_origins()
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )
    
    # Add rate limiting (if enabled)
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=int(rate_limit),
            burst_limit=int(rate_limit_burst),
        )
    
    # Add request logging (outermost - logs everything)
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info(
        f"Middleware configured: "
        f"rate_limit={'enabled' if settings.rate_limit_enabled else 'disabled'} "
        f"({rate_limit}/min), "
        f"cors_origins={len(cors_origins)} origins"
    )


# =============================================================================
# REDIS RATE LIMITER (FOR MULTI-INSTANCE DEPLOYMENTS)
# =============================================================================

class RedisRateLimiter:
    """
    Redis-based rate limiter for distributed deployments.
    
    Usage:
        limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
        is_allowed, remaining = await limiter.is_allowed("client_key")
    """
    
    def __init__(
        self,
        redis_url: str,
        requests_per_minute: int = 60,
        burst_limit: int = 100,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_seconds = 60
        self._redis = None
        self._redis_url = redis_url
    
    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._redis_url)
        return self._redis
    
    async def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """Check if request is allowed using Redis sliding window."""
        redis = await self._get_redis()
        
        now = time.time()
        window_key = f"ratelimit:{client_key}"
        
        # Use Redis pipeline for atomic operations
        async with redis.pipeline() as pipe:
            # Remove old entries
            pipe.zremrangebyscore(window_key, 0, now - self.window_seconds)
            # Add current request
            pipe.zadd(window_key, {str(now): now})
            # Count requests in window
            pipe.zcard(window_key)
            # Set expiry
            pipe.expire(window_key, self.window_seconds * 2)
            
            results = await pipe.execute()
        
        request_count = results[2]
        
        # Check limits
        if request_count > self.burst_limit:
            return False, 0
        
        if request_count > self.requests_per_minute:
            return False, 0
        
        remaining = self.requests_per_minute - request_count
        return True, max(0, remaining)
