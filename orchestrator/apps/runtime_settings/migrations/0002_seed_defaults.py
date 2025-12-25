from django.db import migrations


def seed_defaults(apps, schema_editor):
    RuntimeSetting = apps.get_model('runtime_settings', 'RuntimeSetting')
    defaults = [
        ("ui.operations.max_live_streams", 10),
    ]
    for key, value in defaults:
        RuntimeSetting.objects.get_or_create(
            key=key,
            defaults={"value": value},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('runtime_settings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
