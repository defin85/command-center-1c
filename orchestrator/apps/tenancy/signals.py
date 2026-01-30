from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant, TenantMember, UserTenantPreference


@receiver(post_save, sender=get_user_model())
def _ensure_user_tenancy(sender, instance, created: bool, **kwargs):
    if not created:
        return

    default_tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    role = TenantMember.ROLE_ADMIN if instance.is_staff else TenantMember.ROLE_MEMBER

    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=instance,
        defaults={"role": role},
    )
    UserTenantPreference.objects.get_or_create(user=instance, defaults={"active_tenant": default_tenant})

