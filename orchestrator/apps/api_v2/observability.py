from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

HEADER_REQUEST_ID = "X-Request-ID"
HEADER_UI_ACTION_ID = "X-UI-Action-ID"
_CORRELATION_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_current_request_correlation: ContextVar["RequestCorrelation | None"] = ContextVar(
    "api_v2_request_correlation",
    default=None,
)


@dataclass(frozen=True)
class RequestCorrelation:
    request_id: str
    ui_action_id: str | None
    path: str


def _normalize_correlation_value(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if not normalized or not _CORRELATION_VALUE_PATTERN.fullmatch(normalized):
        return None
    return normalized


def ensure_request_correlation(request) -> RequestCorrelation:
    request_id = _normalize_correlation_value(
        request.headers.get(HEADER_REQUEST_ID) or request.META.get("HTTP_X_REQUEST_ID")
    ) or f"req-{uuid4()}"
    ui_action_id = _normalize_correlation_value(
        request.headers.get(HEADER_UI_ACTION_ID) or request.META.get("HTTP_X_UI_ACTION_ID")
    )
    correlation = RequestCorrelation(
        request_id=request_id,
        ui_action_id=ui_action_id,
        path=str(getattr(request, "path", "") or ""),
    )

    request.META["HTTP_X_REQUEST_ID"] = request_id
    if ui_action_id:
        request.META["HTTP_X_UI_ACTION_ID"] = ui_action_id
    else:
        request.META.pop("HTTP_X_UI_ACTION_ID", None)
    request.cc1c_request_correlation = correlation
    return correlation


def get_request_correlation() -> RequestCorrelation | None:
    return _current_request_correlation.get()


def apply_correlation_headers(response, correlation: RequestCorrelation | None = None):
    current = correlation or get_request_correlation()
    if current is None:
        return response

    response[HEADER_REQUEST_ID] = current.request_id
    if current.ui_action_id:
        response[HEADER_UI_ACTION_ID] = current.ui_action_id
    elif HEADER_UI_ACTION_ID in response:
        del response[HEADER_UI_ACTION_ID]
    return response


def with_problem_correlation(payload: dict[str, Any]) -> dict[str, Any]:
    correlation = get_request_correlation()
    if correlation is None:
        return payload

    enriched = dict(payload)
    enriched["request_id"] = correlation.request_id
    if correlation.ui_action_id:
        enriched["ui_action_id"] = correlation.ui_action_id
    return enriched


def log_problem_response(payload: dict[str, Any]) -> None:
    correlation = get_request_correlation()
    logger.warning(
        "api_problem_response request_id=%s ui_action_id=%s code=%s status=%s path=%s",
        correlation.request_id if correlation else "-",
        correlation.ui_action_id if correlation and correlation.ui_action_id else "-",
        str(payload.get("code") or "-"),
        str(payload.get("status") or "-"),
        correlation.path if correlation else "-",
    )


class RequestCorrelationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation = ensure_request_correlation(request)
        token = _current_request_correlation.set(correlation)
        try:
            response = self.get_response(request)
        except Exception:
            _current_request_correlation.reset(token)
            raise

        apply_correlation_headers(response, correlation)
        _current_request_correlation.reset(token)
        return response
