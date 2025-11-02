import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('commandcenter')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Celery Beat Schedule для periodic tasks
app.conf.beat_schedule = {
    # Проверка кластеров каждые 60 секунд
    'cluster-health-check': {
        'task': 'apps.databases.tasks.periodic_cluster_health_check',
        'schedule': 60.0,  # секунды
        'options': {'expires': 50.0}
    },

    # Проверка баз данных каждые 60 секунд
    'database-health-check': {
        'task': 'apps.databases.tasks.periodic_database_health_check',
        'schedule': 60.0,
        'options': {'expires': 55.0}
    },

    # Проверка BatchService каждые 30 секунд
    'batch-service-health-check': {
        'task': 'apps.databases.tasks.periodic_batch_service_health_check',
        'schedule': 30.0,
        'options': {'expires': 25.0}
    },

    # Очистка старых записей истории (раз в день в 3:00 UTC)
    'cleanup-status-history': {
        'task': 'apps.databases.tasks.cleanup_old_status_history',
        'schedule': crontab(hour=3, minute=0),
    },
}

# Timezone для beat schedule
app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
