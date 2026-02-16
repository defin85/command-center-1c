from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0022_backfill_pools_execution_tenant_linkage"),
    ]

    operations = [
        migrations.AddField(
            model_name="operationexposure",
            name="domain",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="operationexposure",
            name="system_managed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="operationexposure",
            index=models.Index(fields=["system_managed", "domain"], name="op_exp_sys_domain_idx"),
        ),
    ]
