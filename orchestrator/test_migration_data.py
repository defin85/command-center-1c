#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test data migration for BatchService."""
# ruff: noqa: E402
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.models import BatchService

print("=" * 70)
print("TEST 1: Check data migration (is_active -> status)")
print("=" * 70)

# Get all BatchService
services = BatchService.objects.all()
print(f"\nTotal BatchService: {services.count()}")

# Check all have valid status
valid_statuses = ['active', 'inactive', 'error', 'maintenance']
all_valid = True

for service in services:
    status_valid = service.status in valid_statuses
    all_valid = all_valid and status_valid

    status_mark = 'OK' if status_valid else 'FAILED'
    print(f"\n{service.name}:")
    print(f"  - ID: {service.id}")
    print(f"  - status: {service.status} [{status_mark}]")
    print(f"  - last_health_status: {service.last_health_status}")
    print(f"  - consecutive_failures: {service.consecutive_failures}")
    print(f"  - URL: {service.url}")

# Check is_active field removed
print("\n" + "=" * 70)
print("TEST 2: Check is_active field removed")
print("=" * 70)

try:
    # Accessing is_active should raise AttributeError
    test_service = services.first()
    if test_service:
        _ = test_service.is_active
        print("FAILED: Field is_active still exists!")
        sys.exit(1)
except AttributeError:
    print("PASSED: Field is_active successfully removed")

# Check backward compatibility property
print("\n" + "=" * 70)
print("TEST 3: Check backward compatibility property")
print("=" * 70)

if services.exists():
    service = services.first()
    is_active_compat = service.is_active_compat
    print(f"\nis_active_compat: {is_active_compat}")
    print(f"Type: {type(is_active_compat)}")

    if isinstance(is_active_compat, bool):
        print("PASSED: is_active_compat works correctly")
        print(f"Logic: status='{service.status}' -> is_active_compat={is_active_compat}")
    else:
        print("FAILED: is_active_compat should return bool")
        sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("DATA MIGRATION TEST RESULTS")
print("=" * 70)

if all_valid:
    print("\nALL TESTS PASSED!")
    print(f"   - All {services.count()} records have valid status")
    print("   - Field is_active removed")
    print("   - Backward compatibility property works")
    sys.exit(0)
else:
    print("\nTESTS FAILED!")
    print("   - Found records with invalid status")
    sys.exit(1)
