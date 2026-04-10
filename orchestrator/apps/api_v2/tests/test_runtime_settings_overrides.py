import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.runtime_settings.effective import get_effective_runtime_setting
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant


RUNTIME_SCHEDULER_ENABLED_KEY = "runtime.scheduler.enabled"
RUNTIME_POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY = "runtime.scheduler.job.pool_factual_active_sync.enabled"
TENANT_OVERRIDE_KEY = "pools.master_data.sync.enabled"


@pytest.fixture
def staff_user():
    return User.objects.create_user(username="runtime_settings_staff", password="pass", is_staff=True)


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def tenant():
    return Tenant.objects.create(slug="runtime-settings", name="Runtime Settings")


@pytest.mark.django_db
def test_list_runtime_setting_overrides_excludes_global_only_keys(staff_client, tenant):
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=RUNTIME_POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY,
        value=False,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=TENANT_OVERRIDE_KEY,
        value=False,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )

    response = staff_client.get(
        "/api/v2/settings/runtime-overrides/",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "key": TENANT_OVERRIDE_KEY,
            "value": False,
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
        }
    ]


@pytest.mark.django_db
def test_update_runtime_setting_override_rejects_global_only_key(staff_client, tenant):
    response = staff_client.patch(
        f"/api/v2/settings/runtime-overrides/{RUNTIME_POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY}/",
        {"value": False, "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "GLOBAL_ONLY_SETTING"
    assert not TenantRuntimeSettingOverride.objects.filter(
        tenant=tenant,
        key=RUNTIME_POOL_FACTUAL_ACTIVE_SYNC_ENABLED_KEY,
    ).exists()


@pytest.mark.django_db
def test_effective_runtime_setting_ignores_tenant_override_for_global_only_key(tenant):
    RuntimeSetting.objects.create(key=RUNTIME_SCHEDULER_ENABLED_KEY, value=False)
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=RUNTIME_SCHEDULER_ENABLED_KEY,
        value=True,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )

    effective = get_effective_runtime_setting(RUNTIME_SCHEDULER_ENABLED_KEY, str(tenant.id))

    assert effective.value is False
    assert effective.source == "global"
