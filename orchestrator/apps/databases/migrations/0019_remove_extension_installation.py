from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("databases", "0018_add_ib_user_password"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ExtensionInstallation",
        ),
    ]
