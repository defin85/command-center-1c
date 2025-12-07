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
