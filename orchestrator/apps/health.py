"""
Health check endpoints для мониторинга состояния сервиса
"""

from django.http import JsonResponse
from django.db import connection
from django.conf import settings
import redis


def health_check(request):
    """
    Простой health check - возвращает 200 OK если сервис работает
    """
    return JsonResponse({
        'status': 'ok',
        'service': 'commandcenter-orchestrator',
        'environment': 'development' if settings.DEBUG else 'production',
    })


def health_check_detailed(request):
    """
    Детальный health check - проверяет все зависимости
    """
    status = {
        'status': 'ok',
        'service': 'commandcenter-orchestrator',
        'checks': {}
    }

    # Проверка БД
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        status['checks']['database'] = 'ok'
    except Exception as e:
        status['checks']['database'] = f'error: {str(e)}'
        status['status'] = 'degraded'

    # Проверка Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        status['checks']['redis'] = 'ok'
    except Exception as e:
        status['checks']['redis'] = f'error: {str(e)}'
        status['status'] = 'degraded'

    return JsonResponse(status)
