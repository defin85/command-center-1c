from django.db import migrations


DEFAULT_UI_ACTION_CATALOG = {
    "catalog_version": 1,
    "extensions": {"actions": []},
}


def seed_ui_action_catalog(apps, schema_editor):
    RuntimeSetting = apps.get_model("runtime_settings", "RuntimeSetting")
    RuntimeSetting.objects.get_or_create(
        key="ui.action_catalog",
        defaults={"value": DEFAULT_UI_ACTION_CATALOG},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("runtime_settings", "0002_seed_defaults"),
    ]

    operations = [
        migrations.RunPython(seed_ui_action_catalog, migrations.RunPython.noop),
    ]
