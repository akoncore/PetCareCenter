import logging
import time
import uuid

from .logging import request_id

logger = logging.getLogger("petcare.http")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate locally instead of trusting arbitrary client header contents.
        correlation_id = uuid.uuid4().hex
        context = request_id.set(correlation_id)
        started = time.monotonic()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = correlation_id
            match = getattr(request, "resolver_match", None)
            logger.log(logging.ERROR if response.status_code >= 500 else logging.INFO,
                       "http_request", extra={
                           "method": request.method,
                           "route": getattr(match, "route", None),
                           "status": response.status_code,
                           "duration_ms": round((time.monotonic() - started) * 1000, 2),
                       })
            return response
        finally:
            request_id.reset(context)

    def process_exception(self, request, exception):
        logger.error("request_failed", exc_info=(type(exception), exception, exception.__traceback__))
