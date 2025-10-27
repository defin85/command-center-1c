# Generated manually for code review fix

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('databases', '0002_extension_installation'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='extensioninstallation',
            constraint=models.UniqueConstraint(
                fields=['database', 'extension_name'],
                condition=models.Q(status__in=['pending', 'in_progress']),
                name='unique_active_installation'
            ),
        ),
    ]
