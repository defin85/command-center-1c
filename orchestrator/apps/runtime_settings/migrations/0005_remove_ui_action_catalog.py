from django.db import migrations


LEGACY_ACTION_CATALOG_KEY = "ui.action_catalog"


def remove_legacy_action_catalog_key(apps, schema_editor):
    RuntimeSetting = apps.get_model("runtime_settings", "RuntimeSetting")
    TenantRuntimeSettingOverride = apps.get_model("runtime_settings", "TenantRuntimeSettingOverride")

    RuntimeSetting.objects.filter(key=LEGACY_ACTION_CATALOG_KEY).delete()
    TenantRuntimeSettingOverride.objects.filter(key=LEGACY_ACTION_CATALOG_KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("runtime_settings", "0004_tenant_runtime_setting_overrides"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_action_catalog_key, migrations.RunPython.noop),
    ]

