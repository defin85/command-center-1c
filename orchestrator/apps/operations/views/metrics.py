"""
Prometheus metrics endpoint.

Provides /metrics for Orchestrator without django-prometheus.
"""
from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from apps.operations import prometheus_metrics  # noqa: F401


def metrics(request):
    data = generate_latest()
    return HttpResponse(data, content_type=CONTENT_TYPE_LATEST)
