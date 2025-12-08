"""
Migration to rename celery_task_id to task_id.

Celery has been fully removed from the project.
Go Worker is now the single execution engine.
The field name 'celery_task_id' is obsolete and should be renamed to 'task_id'.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('operations', '0007_job_history_models'),
    ]

    operations = [
        migrations.RenameField(
            model_name='batchoperation',
            old_name='celery_task_id',
            new_name='task_id',
        ),
        migrations.RenameField(
            model_name='task',
            old_name='celery_task_id',
            new_name='task_id',
        ),
    ]
