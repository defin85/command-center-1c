"""
HTTP metrics middleware for Prometheus.

Records request counts, latency, and in-flight requests.
"""
import time

from apps.operations.prometheus_metrics import (
    http_requests_total,
    http_request_duration,
    active_workers,
)


class PrometheusMetricsMiddleware:
    """Collect HTTP metrics without django-prometheus."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/metrics" or request.path == "/metrics/":
            return self.get_response(request)

        start = time.monotonic()
        active_workers.inc()
        status_code = "500"
        try:
            response = self.get_response(request)
            status_code = str(getattr(response, "status_code", 500))
            return response
        finally:
            duration = time.monotonic() - start
            http_requests_total.labels(method=request.method, status=status_code).inc()
            http_request_duration.labels(method=request.method, status=status_code).observe(duration)
            active_workers.dec()
