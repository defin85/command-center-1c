from django.db import models
from django.db.models import Q
from encrypted_model_fields.fields import EncryptedCharField


class InfobaseAuthType(models.TextChoices):
    LOCAL = "local", "Local"
    AD = "ad", "Active Directory"
    SERVICE = "service", "Service"
    OTHER = "other", "Other"


class InfobaseUserMapping(models.Model):
    from django.conf import settings as django_settings

    database = models.ForeignKey("Database", on_delete=models.CASCADE, related_name="ib_user_mappings")
    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ib_user_mappings",
    )
    ib_username = models.CharField(max_length=128)
    ib_display_name = models.CharField(max_length=255, blank=True)
    ib_roles = models.JSONField(default=list, blank=True)
    ib_password = EncryptedCharField(max_length=255, blank=True)
    auth_type = models.CharField(
        max_length=32,
        choices=InfobaseAuthType.choices,
        default=InfobaseAuthType.LOCAL,
    )
    is_service = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ib_user_mappings_created",
    )
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ib_user_mappings_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databases_ib_user_mappings"
        unique_together = ["database", "ib_username"]
        indexes = [
            models.Index(fields=["database", "ib_username"], name="ib_user_db_name_idx"),
            models.Index(fields=["database", "auth_type"], name="ib_user_db_auth_idx"),
        ]

    def __str__(self):
        return f"{self.database.name}: {self.ib_username}"


class DbmsAuthType(models.TextChoices):
    LOCAL = "local", "Local"
    SERVICE = "service", "Service"
    OTHER = "other", "Other"


class DbmsUserMapping(models.Model):
    from django.conf import settings as django_settings

    database = models.ForeignKey("Database", on_delete=models.CASCADE, related_name="dbms_user_mappings")
    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dbms_user_mappings",
    )
    db_username = models.CharField(max_length=128)
    db_password = EncryptedCharField(max_length=255, blank=True)
    auth_type = models.CharField(
        max_length=32,
        choices=DbmsAuthType.choices,
        default=DbmsAuthType.LOCAL,
    )
    is_service = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dbms_user_mappings_created",
    )
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dbms_user_mappings_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databases_dbms_user_mappings"
        indexes = [
            models.Index(fields=["database", "is_service"], name="dbms_map_db_svc_idx"),
            models.Index(fields=["database", "user"], name="dbms_map_db_user_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["database", "user"],
                name="dbms_map_unique_user",
                condition=Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["database"],
                name="dbms_map_unique_service",
                condition=Q(is_service=True),
            ),
            models.CheckConstraint(
                condition=Q(user__isnull=False) | Q(is_service=True),
                name="dbms_map_user_or_service",
            ),
        ]

    def __str__(self) -> str:
        if self.is_service:
            return f"{self.database.name}: DBMS service"
        if self.user_id:
            return f"{self.database.name}: {self.user_id}"
        return f"{self.database.name}: {self.db_username}"


class DatabaseExtensionsSnapshot(models.Model):
    database = models.OneToOneField(
        "Database",
        on_delete=models.CASCADE,
        related_name="extensions_snapshot",
        primary_key=True,
    )
    snapshot = models.JSONField(default=dict, blank=True)
    source_operation_id = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "databases_extensions_snapshot"
        indexes = [
            models.Index(fields=["-updated_at"]),
        ]

    def __str__(self):
        return f"{self.database.name}: extensions snapshot"

