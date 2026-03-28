from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("intercompany_pools", "0032_poolbatchpublicationattempt_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="poolfactualsynccheckpoint",
            name="operation_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="poolfactualsynccheckpoint",
            name="workflow_execution_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="poolfactualsynccheckpoint",
            name="workflow_status",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
    ]
