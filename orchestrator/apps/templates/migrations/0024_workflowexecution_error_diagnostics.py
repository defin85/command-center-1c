from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('templates', '0023_operationexposure_system_managed_domain'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowexecution',
            name='error_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Machine-readable error code if failed',
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name='workflowexecution',
            name='error_details',
            field=models.JSONField(
                blank=True,
                default=None,
                help_text='Structured diagnostics payload for failure analysis',
                null=True,
            ),
        ),
    ]
