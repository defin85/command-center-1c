from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("artifacts", "0004_rename_artifacts_a_kind_68a1d8_idx_artifacts_a_kind_e85de3_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="artifact",
            name="kind",
            field=models.CharField(
                choices=[
                    ("extension", "Extension"),
                    ("config_cf", "Config CF"),
                    ("config_xml", "Config XML"),
                    ("dt_backup", "DT Backup"),
                    ("epf", "EPF"),
                    ("erf", "ERF"),
                    ("ibcmd_package", "IBCMD Package"),
                    ("ras_script", "RAS Script"),
                    ("other", "Other"),
                ],
                max_length=64,
            ),
        ),
    ]
