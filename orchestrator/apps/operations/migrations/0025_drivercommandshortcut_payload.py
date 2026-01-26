from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0024_batchoperation_service_ib_auth_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="drivercommandshortcut",
            name="payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="drivercommandshortcut",
            name="catalog_base_version",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="drivercommandshortcut",
            name="catalog_overrides_version",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

