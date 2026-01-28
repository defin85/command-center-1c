import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="command_schemas_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    permission = Permission.objects.get(codename="manage_driver_catalogs", content_type__app_label="operations")
    user.user_permissions.add(permission)
    return user


@pytest.fixture
def client(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c

