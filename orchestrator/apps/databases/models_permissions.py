from django.contrib.auth.models import Group
from django.db import models


class PermissionLevel(models.IntegerChoices):
    VIEW = 10, "View"
    OPERATE = 20, "Operate"
    MANAGE = 30, "Manage"
    ADMIN = 40, "Admin"


class ClusterPermission(models.Model):
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cluster_permissions",
    )
    cluster = models.ForeignKey(
        "Cluster",
        on_delete=models.CASCADE,
        related_name="user_permissions",
    )
    level = models.IntegerField(choices=PermissionLevel.choices, default=PermissionLevel.VIEW)

    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "databases_cluster_permissions"
        unique_together = ["user", "cluster"]
        indexes = [
            models.Index(fields=["user", "cluster"], name="cp_user_cluster_idx"),
            models.Index(fields=["cluster", "level"], name="cp_cluster_level_idx"),
        ]
        permissions = (("manage_rbac", "Can manage RBAC"),)

    def __str__(self):
        return f"{self.user.username} -> {self.cluster.name} ({self.get_level_display()})"


class DatabasePermission(models.Model):
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="database_permissions",
    )
    database = models.ForeignKey(
        "Database",
        on_delete=models.CASCADE,
        related_name="user_permissions",
    )
    level = models.IntegerField(choices=PermissionLevel.choices, default=PermissionLevel.VIEW)

    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "databases_database_permissions"
        unique_together = ["user", "database"]
        indexes = [
            models.Index(fields=["user", "database"], name="dp_user_db_idx"),
            models.Index(fields=["database", "level"], name="dp_db_level_idx"),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.database.name} ({self.get_level_display()})"


class ClusterGroupPermission(models.Model):
    from django.conf import settings as django_settings

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="cluster_permissions")
    cluster = models.ForeignKey(
        "Cluster",
        on_delete=models.CASCADE,
        related_name="group_permissions",
    )
    level = models.IntegerField(choices=PermissionLevel.choices, default=PermissionLevel.VIEW)

    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "databases_cluster_group_permissions"
        unique_together = ["group", "cluster"]
        indexes = [
            models.Index(fields=["group", "cluster"], name="cgp_group_cluster_idx"),
            models.Index(fields=["cluster", "level"], name="cgp_cluster_level_idx"),
        ]

    def __str__(self):
        return f"{self.group.name} -> {self.cluster.name} ({self.get_level_display()})"


class DatabaseGroupPermission(models.Model):
    from django.conf import settings as django_settings

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="database_permissions")
    database = models.ForeignKey(
        "Database",
        on_delete=models.CASCADE,
        related_name="group_permissions",
    )
    level = models.IntegerField(choices=PermissionLevel.choices, default=PermissionLevel.VIEW)

    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "databases_database_group_permissions"
        unique_together = ["group", "database"]
        indexes = [
            models.Index(fields=["group", "database"], name="dgp_group_db_idx"),
            models.Index(fields=["database", "level"], name="dgp_db_level_idx"),
        ]

    def __str__(self):
        return f"{self.group.name} -> {self.database.name} ({self.get_level_display()})"

