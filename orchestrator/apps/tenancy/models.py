import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"
        ordering = ["name"]
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class TenantMember(models.Model):
    ROLE_MEMBER = "member"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_MEMBER, "Member"),
        (ROLE_ADMIN, "Admin"),
    ]

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tenant_members"
        unique_together = [("tenant", "user")]
        verbose_name = "Tenant Member"
        verbose_name_plural = "Tenant Members"

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.tenant_id} ({self.role})"


class UserTenantPreference(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_pref")
    active_tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_tenant_preferences"
        verbose_name = "User Tenant Preference"
        verbose_name_plural = "User Tenant Preferences"

    def __str__(self) -> str:
        return f"{self.user_id}: {self.active_tenant_id}"

