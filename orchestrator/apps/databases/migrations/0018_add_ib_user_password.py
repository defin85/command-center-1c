from django.db import migrations
from encrypted_model_fields.fields import EncryptedCharField


class Migration(migrations.Migration):

    dependencies = [
        ("databases", "0017_add_infobase_user_mapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="infobaseusermapping",
            name="ib_password",
            field=EncryptedCharField(blank=True, max_length=255),
        ),
    ]
