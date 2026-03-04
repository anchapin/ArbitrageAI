"""
Security Headers Middleware for FastAPI.

Issue #149: Add security headers middleware to FastAPI application

This middleware adds essential security headers to all HTTP responses
to protect against common web vulnerabilities.

Security Headers Implemented:
1. Strict-Transport-Security (HSTS) - Force HTTPS
2. Content-Security-Policy (CSP) - Prevent XSS
3. X-Content-Type-Options - Prevent MIME sniffing
4. X-Frame-Options - Prevent clickjacking
5. X-XSS-Protection - Legacy XSS filter
6. Referrer-Policy - Control referrer information
7. Permissions-Policy - Control browser features
8. Cache-Control - Prevent sensitive data caching
9. X-Permitted-Cross-Domain-Policies - Restrict cross-domain access
10. Cross-Origin-Embedder-Policy - Isolation
11. Cross-Origin-Opener-Policy - Isolation
12. Cross-Origin-Resource-Policy - Resource protection

References:
- OWASP Secure Headers Project: https://owasp.org/www-project-secure-headers/
- MDN Web Security: https://developer.mozilla.org/en-US/docs/Web/Security
"""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    This middleware implements defense-in-depth by adding multiple
    layers of security through HTTP response headers.

    Example:
        from fastapi import FastAPI
        from src.api.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
    """

    def __init__(
        self,
        app,
        # HSTS Configuration
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,

        # CSP Configuration
        csp_report_uri: str | None = None,
        csp_report_only: bool = False,

        # Feature Policy Configuration
        allow_camera: bool = False,
        allow_microphone: bool = False,
        allow_geolocation: bool = False,
        allow_payment: bool = True,

        # Environment
        is_development: bool = False,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI application
            hsts_max_age: Max age for HSTS in seconds
            hsts_include_subdomains: Include subdomains in HSTS
            hsts_preload: Enable HSTS preload
            csp_report_uri: URI for CSP violation reports
            csp_report_only: Use Content-Security-Policy-Report-Only
            allow_camera: Allow camera access
            allow_microphone: Allow microphone access
            allow_geolocation: Allow geolocation access
            allow_payment: Allow payment handler API
            is_development: Development mode (relaxes some headers)
        """
        super().__init__(app)

        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.csp_report_uri = csp_report_uri
        self.csp_report_only = csp_report_only
        self.is_development = is_development

        # Build feature policy
        feature_permissions = []
        if allow_camera:
            feature_permissions.append("camera")
        if allow_microphone:
            feature_permissions.append("microphone")
        if allow_geolocation:
            feature_permissions.append("geolocation")
        if allow_payment:
            feature_permissions.append("payment")

        self.feature_policy = "; ".join(feature_permissions) if feature_permissions else "()"

        logger.info("Security Headers Middleware initialized")
        if is_development:
            logger.warning("Development mode: Some security headers relaxed")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add security headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response with security headers added
        """
        try:
            response = await call_next(request)
            return self._add_security_headers(response, request)
        except Exception as e:
            logger.error(f"Security headers middleware error: {e}", exc_info=True)
            # Don't block requests on middleware errors
            return await call_next(request)

    def _add_security_headers(self, response: Response, request: Request) -> Response:
        """
        Add security headers to response.

        Args:
            response: HTTP response
            request: Original HTTP request

        Returns:
            Response with security headers
        """
        # 1. Strict-Transport-Security (HSTS)
        # Forces HTTPS connections to prevent man-in-the-middle attacks
        if not self.is_development:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # 2. Content-Security-Policy (CSP)
        # Prevents XSS by controlling resource loading
        csp_policy = self._build_csp_policy(request)
        header_name = (
            "Content-Security-Policy-Report-Only"
            if self.csp_report_only
            else "Content-Security-Policy"
        )
        response.headers[header_name] = csp_policy

        # 3. X-Content-Type-Options
        # Prevents MIME type sniffing attacks
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 4. X-Frame-Options
        # Prevents clickjacking by disallowing framing
        response.headers["X-Frame-Options"] = "DENY"

        # 5. X-XSS-Protection
        # Legacy XSS filter (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 6. Referrer-Policy
        # Controls referrer information sent with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 7. Permissions-Policy (formerly Feature-Policy)
        # Controls browser features and APIs
        if self.feature_policy:
            response.headers["Permissions-Policy"] = self.feature_policy

        # 8. Cache-Control
        # Prevents caching of sensitive API responses
        # Only add to non-static, non-public endpoints
        if not SecurityHeadersMiddleware._is_cacheable_endpoint(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # 9. X-Permitted-Cross-Domain-Policies
        # Restricts Adobe Flash and PDF cross-domain access
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # 10. Cross-Origin-Embedder-Policy
        # Prevents loading cross-origin resources without explicit permission
        if not self.is_development:
            response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        # 11. Cross-Origin-Opener-Policy
        # Isolates browsing context
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # 12. Cross-Origin-Resource-Policy
        # Protects resources from cross-origin requests
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # 13. Server header removal
        # Remove server identification
        if "server" in response.headers:
            del response.headers["server"]

        # 14. X-Powered-By removal
        # Remove technology identification
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        logger.debug(f"Security headers added to {request.method} {request.url.path}")

        return response

    def _build_csp_policy(self, request: Request) -> str:
        """
        Build Content-Security-Policy header value.

        Args:
            request: HTTP request for context

        Returns:
            CSP policy string
        """
        # Base directives
        policy = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # Needed for some CSS frameworks
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self' https://api.stripe.com",  # Stripe API
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        # Add report URI if configured
        if self.csp_report_uri:
            policy.append(f"report-uri {self.csp_report_uri}")
            policy.append("report-to csp-endpoint")

        # Development mode: relax CSP for hot reload
        if self.is_development:
            policy = [
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "connect-src 'self' ws: wss: https://api.stripe.com",
                "img-src 'self' data: https: blob:",
            ]

        return "; ".join(policy)

    @staticmethod
    def _is_cacheable_endpoint(path: str) -> bool:
        """
        Check if endpoint should be cached.

        Static assets and public endpoints can be cached.
        API endpoints with sensitive data should not be cached.

        Args:
            path: URL path

        Returns:
            True if cacheable, False otherwise
        """
        # Static assets can be cached
        cacheable_prefixes = [
            "/static/",
            "/assets/",
            "/favicon",
        ]

        return any(path.startswith(prefix) for prefix in cacheable_prefixes)


def create_security_headers_middleware(
    is_development: bool = False,
) -> SecurityHeadersMiddleware:
    """
    Factory function to create security headers middleware with config-based settings.

    Args:
        is_development: Whether running in development mode

    Returns:
        Configured SecurityHeadersMiddleware instance
    """
    # Load configuration
    hsts_max_age = ConfigManager.get("SECURITY_HSTS_MAX_AGE", 31536000)
    hsts_include_subdomains = ConfigManager.get("SECURITY_HSTS_INCLUDE_SUBDOMAINS", True)
    hsts_preload = ConfigManager.get("SECURITY_HSTS_PRELOAD", True)
    csp_report_uri = ConfigManager.get("SECURITY_CSP_REPORT_URI", None)
    csp_report_only = ConfigManager.get("SECURITY_CSP_REPORT_ONLY", False)

    # Feature permissions
    allow_camera = ConfigManager.get("SECURITY_ALLOW_CAMERA", False)
    allow_microphone = ConfigManager.get("SECURITY_ALLOW_MICROPHONE", False)
    allow_geolocation = ConfigManager.get("SECURITY_ALLOW_GEOLOCATION", False)
    allow_payment = ConfigManager.get("SECURITY_ALLOW_PAYMENT", True)

    middleware = SecurityHeadersMiddleware(
        app=None,  # Will be set by FastAPI
        hsts_max_age=hsts_max_age,
        hsts_include_subdomains=hsts_include_subdomains,
        hsts_preload=hsts_preload,
        csp_report_uri=csp_report_uri,
        csp_report_only=csp_report_only,
        allow_camera=allow_camera,
        allow_microphone=allow_microphone,
        allow_geolocation=allow_geolocation,
        allow_payment=allow_payment,
        is_development=is_development,
    )

    logger.info("Security Headers Middleware created with config-based settings")

    return middleware


# Convenience function for easy integration
def setup_security_headers(app, is_development: bool = False):
    """
    Setup security headers middleware for FastAPI application.

    Usage:
        from fastapi import FastAPI
        from src.api.security_headers import setup_security_headers

        app = FastAPI()
        setup_security_headers(app, is_development=True)

    Args:
        app: FastAPI application
        is_development: Whether running in development mode
    """
    create_security_headers_middleware(is_development)
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware added to application")
