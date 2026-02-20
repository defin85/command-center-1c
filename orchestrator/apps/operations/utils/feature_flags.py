"""
Feature flags for Go Worker components.

Используется для постепенного rollout Go компонентов вместо Celery:
- Go Scheduler вместо Celery Beat
- Go Template Engine вместо Django templates
- Go Workflow Engine вместо Celery tasks

Usage:
    from apps.operations.utils.feature_flags import (
        is_go_scheduler_enabled,
        is_go_template_engine_enabled,
        is_go_workflow_engine_enabled,
    )

    if is_go_scheduler_enabled():
        # Use Go Scheduler
        pass
    else:
        # Use Celery Beat
        pass
"""
import os

from django.conf import settings


def is_go_scheduler_enabled() -> bool:
    """
    Проверяет, включен ли Go Scheduler вместо Celery Beat.

    Returns:
        bool: True если Go Scheduler включен, False если используется Celery Beat
    """
    return getattr(settings, 'ENABLE_GO_SCHEDULER', False)


def is_go_template_engine_enabled() -> bool:
    """
    Проверяет, включен ли Go Template Engine вместо Django templates.

    Returns:
        bool: True если Go Template Engine включен, False если используется Django
    """
    return getattr(settings, 'ENABLE_GO_TEMPLATE_ENGINE', False)


def is_go_workflow_engine_enabled() -> bool:
    """
    Проверяет, включен ли Go Workflow Engine вместо Celery tasks.

    Returns:
        bool: True если Go Workflow Engine включен, False если используется Celery
    """
    return getattr(settings, 'ENABLE_GO_WORKFLOW_ENGINE', False)


def get_execution_profile() -> str:
    """
    Возвращает активный execution profile из environment variables.
    """
    return (
        os.environ.get("WORKFLOW_EXECUTION_PROFILE")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("DJANGO_ENV")
        or ""
    ).strip().lower()


def is_production_execution_profile() -> bool:
    """
    True только для production-профиля выполнения.
    """
    return get_execution_profile() in {"prod", "production"}


def is_workflow_debug_fallback_enabled() -> bool:
    """
    Явный флаг для локального debug fallback workflow execution.
    """
    return bool(getattr(settings, "WORKFLOW_EXECUTION_DEBUG_FALLBACK_ENABLED", False))
