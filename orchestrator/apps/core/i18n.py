from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import translation
from django.utils.cache import patch_vary_headers


LOCALE_HEADER = "X-CC1C-Locale"
LOCALE_META_HEADER = "HTTP_X_CC1C_LOCALE"


def _normalize_public_locale(value: str | None | object) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().lower().replace("_", "-")
    if not normalized:
        return None

    language = normalized.split("-", 1)[0]
    return language or None


def normalize_supported_locale(value: str | None | object) -> str | None:
    normalized = _normalize_public_locale(value)
    if not normalized:
        return None

    supported = get_supported_locale_codes()
    if normalized in supported:
        return normalized
    return None


def get_supported_locale_codes() -> tuple[str, ...]:
    languages = getattr(settings, "LANGUAGES", ()) or ()
    supported = []
    for code, _label in languages:
        normalized = _normalize_public_locale(code)
        if normalized and normalized not in supported:
            supported.append(normalized)
    return tuple(supported)


def get_default_locale() -> str:
    return normalize_supported_locale(getattr(settings, "LANGUAGE_CODE", None)) or "ru"


def get_requested_locale(request: Any) -> str | None:
    cached = getattr(request, "cc1c_requested_locale", None)
    if cached is not None:
        return normalize_supported_locale(cached)
    return normalize_supported_locale(request.META.get(LOCALE_META_HEADER))


def get_effective_locale(request: Any) -> str:
    cached = getattr(request, "cc1c_effective_locale", None)
    if cached is not None:
        normalized = normalize_supported_locale(cached)
        if normalized:
            return normalized

    language_code = getattr(request, "LANGUAGE_CODE", None) or translation.get_language()
    return normalize_supported_locale(language_code) or get_default_locale()


def build_i18n_summary_payload(request: Any) -> dict[str, object]:
    return {
        "supported_locales": list(get_supported_locale_codes()),
        "default_locale": get_default_locale(),
        "requested_locale": get_requested_locale(request),
        "effective_locale": get_effective_locale(request),
    }


class RequestLocaleOverrideMiddleware:
    """
    Allows SPA/admin requests to explicitly override the locale via X-CC1C-Locale.

    LocaleMiddleware still owns browser Accept-Language handling. This middleware only
    applies the explicit app-level override after LocaleMiddleware has resolved the
    request language and patches the response vary/content-language headers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        requested_locale = normalize_supported_locale(request.META.get(LOCALE_META_HEADER))
        if requested_locale:
            translation.activate(requested_locale)
            request.LANGUAGE_CODE = requested_locale

        request.cc1c_requested_locale = requested_locale
        request.cc1c_effective_locale = get_effective_locale(request)

        response = self.get_response(request)

        effective_locale = get_effective_locale(request)
        request.cc1c_effective_locale = effective_locale

        patch_vary_headers(response, (LOCALE_HEADER,))
        response["Content-Language"] = effective_locale
        return response
