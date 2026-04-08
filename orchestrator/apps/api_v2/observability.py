from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

HEADER_REQUEST_ID = "X-Request-ID"
HEADER_UI_ACTION_ID = "X-UI-Action-ID"
_JSON_CONTENT_TYPES = {"application/json", "application/problem+json"}
_CORRELATION_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(auth|authorization|cookie|csrf|passwd|password|secret|session|token|api[_-]?key|access[_-]?key|stdin)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|authorization|secret|cookie|api[_-]?key|access[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_MAX_DIAGNOSTIC_VALUE_LENGTH = 512
_OMIT = object()
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


def _is_sensitive_key(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    if normalized.endswith("_password") or normalized.endswith("_pwd"):
        return True
    return _SENSITIVE_KEY_PATTERN.search(normalized) is not None


def _sanitize_diagnostic_string(value: Any, *, max_length: int = _MAX_DIAGNOSTIC_VALUE_LENGTH) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    redacted = _SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", normalized)
    if len(redacted) > max_length:
        return f"{redacted[: max_length - 3]}..."
    return redacted


def _sanitize_error_value(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return _OMIT

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for child_key, child_value in value.items():
            sanitized_value = _sanitize_error_value(child_value, key=str(child_key or ""))
            if sanitized_value is _OMIT:
                continue
            sanitized[str(child_key)] = sanitized_value
        return sanitized

    if isinstance(value, list):
        sanitized_list: list[Any] = []
        for item in value:
            sanitized_item = _sanitize_error_value(item)
            if sanitized_item is _OMIT:
                continue
            sanitized_list.append(sanitized_item)
        return sanitized_list

    if isinstance(value, tuple):
        sanitized_tuple: list[Any] = []
        for item in value:
            sanitized_item = _sanitize_error_value(item)
            if sanitized_item is _OMIT:
                continue
            sanitized_tuple.append(sanitized_item)
        return sanitized_tuple

    if isinstance(value, str):
        return _sanitize_diagnostic_string(value)

    return value


def _sanitize_error_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_error_value(payload)
    if isinstance(sanitized, dict):
        return sanitized
    return {}


def sanitize_error_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_error_payload(payload)


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


def with_problem_correlation(
    payload: dict[str, Any],
    correlation: RequestCorrelation | None = None,
) -> dict[str, Any]:
    correlation = correlation or get_request_correlation()
    if correlation is None:
        return _sanitize_error_payload(payload)

    enriched = _sanitize_error_payload(payload)
    enriched["request_id"] = _normalize_correlation_value(enriched.get("request_id")) or correlation.request_id
    ui_action_id = _normalize_correlation_value(enriched.get("ui_action_id")) or correlation.ui_action_id
    if ui_action_id:
        enriched["ui_action_id"] = ui_action_id
    else:
        enriched.pop("ui_action_id", None)
    return enriched


def _should_enrich_error_payload(payload: Any, status_code: int) -> bool:
    if status_code < 400 or not isinstance(payload, dict):
        return False

    if "request_id" in payload or "ui_action_id" in payload:
        return True

    return (
        payload.get("success") is False
        or "error" in payload
        or "code" in payload
        or "title" in payload
        or "detail" in payload
    )


def apply_error_payload_correlation(response, correlation: RequestCorrelation | None = None):
    current = correlation or get_request_correlation()
    if current is None or getattr(response, "streaming", False):
        return response

    status_code = int(getattr(response, "status_code", 0) or 0)
    response_data = getattr(response, "data", None)
    if _should_enrich_error_payload(response_data, status_code):
        enriched = with_problem_correlation(response_data, current)
        response.data = enriched
        if getattr(response, "_is_rendered", False):
            content = json.dumps(enriched, default=str).encode(
                getattr(response, "charset", "utf-8") or "utf-8"
            )
            response.content = content
            if "Content-Length" in response:
                response["Content-Length"] = str(len(content))
        return response

    content_type = str(response.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if content_type not in _JSON_CONTENT_TYPES:
        return response

    try:
        payload = json.loads(response.content)
    except Exception:
        return response

    if not _should_enrich_error_payload(payload, status_code):
        return response

    content = json.dumps(with_problem_correlation(payload, current), default=str).encode(
        getattr(response, "charset", "utf-8") or "utf-8"
    )
    response.content = content
    if "Content-Length" in response:
        response["Content-Length"] = str(len(content))
    return response


def log_problem_response(payload: dict[str, Any]) -> None:
    correlation = get_request_correlation()
    logger.warning(
        "api_problem_response request_id=%s ui_action_id=%s code=%s status=%s path=%s",
        correlation.request_id if correlation else "-",
        correlation.ui_action_id if correlation and correlation.ui_action_id else "-",
        _sanitize_diagnostic_string(payload.get("code") or "-", max_length=120) or "-",
        _sanitize_diagnostic_string(payload.get("status") or "-", max_length=32) or "-",
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

        apply_error_payload_correlation(response, correlation)
        apply_correlation_headers(response, correlation)
        _current_request_correlation.reset(token)
        return response
