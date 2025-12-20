from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databases", "0014_add_rbac_permissions"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BatchService",
        ),
    ]
