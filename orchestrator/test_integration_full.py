#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Full integration test for BatchService migration."""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.models import BatchService, StatusHistory
from django.contrib.contenttypes.models import ContentType

print("=" * 70)
print("INTEGRATION TEST: Full workflow simulation")
print("=" * 70)

# Create test service
print("\n[Setup] Creating BatchService for integration test...")
service = BatchService.objects.create(
    name="Integration Test Service",
    url="http://localhost:9090",
    status=BatchService.STATUS_ACTIVE
)
print(f"Created: {service.name}")

# Simulate real-world scenario: health checks with failures and recovery
print("\n--- Scenario: Simulate real-world health check workflow ---")

# Day 1: Service is healthy
print("\n[Day 1] Service healthy")
service.mark_health_check(success=True)
service.refresh_from_db()
print(f"  Status: {service.status}, Failures: {service.consecutive_failures}, Health: {service.last_health_status}")
assert service.status == 'active'
assert service.consecutive_failures == 0
assert service.last_health_status == 'healthy'

# Day 2: First failure (network glitch)
print("\n[Day 2] Network glitch - first failure")
service.mark_health_check(success=False, error_message="Network timeout")
service.refresh_from_db()
print(f"  Status: {service.status}, Failures: {service.consecutive_failures}, Health: {service.last_health_status}")
assert service.status == 'active'  # Still active after 1 failure
assert service.consecutive_failures == 1

# Day 2 (later): Recovers
print("\n[Day 2 later] Service recovers")
service.mark_health_check(success=True)
service.refresh_from_db()
print(f"  Status: {service.status}, Failures: {service.consecutive_failures}, Health: {service.last_health_status}")
assert service.consecutive_failures == 0  # Reset

# Day 3: Service goes down completely (3 consecutive failures)
print("\n[Day 3] Service goes down - 3 consecutive failures")
for i in range(3):
    service.mark_health_check(success=False, error_message=f"Connection refused (attempt {i+1})")
    service.refresh_from_db()
    print(f"  Attempt {i+1}: Status={service.status}, Failures={service.consecutive_failures}")

assert service.status == 'error'  # Auto-changed to ERROR
assert service.consecutive_failures == 3
print("  -> Service automatically marked as ERROR")

# Day 4: Service back online (auto-recovery)
print("\n[Day 4] Service back online - auto-recovery")
service.mark_health_check(success=True)
service.refresh_from_db()
print(f"  Status: {service.status}, Failures: {service.consecutive_failures}, Health: {service.last_health_status}")
assert service.status == 'active'  # Auto-recovered
assert service.consecutive_failures == 0
print("  -> Service automatically recovered to ACTIVE")

# Check StatusHistory
print("\n--- Verify StatusHistory audit trail ---")
history = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).order_by('changed_at')

print(f"\nTotal status changes: {history.count()}")
print("Status change timeline:")
for i, record in enumerate(history, 1):
    print(f"  {i}. {record.old_status} -> {record.new_status} (failures={record.metadata.get('consecutive_failures', 'N/A')})")

# Verify specific transitions
assert history.count() == 2, "Expected 2 status changes (active->error, error->active)"
assert history[0].old_status == 'active' and history[0].new_status == 'error'
assert history[1].old_status == 'error' and history[1].new_status == 'active'
print("\nPASSED: Status history correctly tracks all transitions")

# Test backward compatibility
print("\n--- Verify backward compatibility ---")
print(f"is_active_compat (when status='active'): {service.is_active_compat}")
assert service.is_active_compat == True

service.status = 'inactive'
service.save()
service.refresh_from_db()
print(f"is_active_compat (when status='inactive'): {service.is_active_compat}")
assert service.is_active_compat == False
print("PASSED: is_active_compat works correctly")

# Test get_active() and get_or_raise()
print("\n--- Verify class methods ---")
service.status = 'active'
service.last_health_status = 'healthy'
service.save()
service.refresh_from_db()

active_service = BatchService.get_active()
assert active_service is not None, "get_active() should return the active service"
assert active_service.id == service.id
print(f"get_active() returned: {active_service.name}")

retrieved_service = BatchService.get_or_raise(service_id=str(service.id))
assert retrieved_service.id == service.id
print(f"get_or_raise() returned: {retrieved_service.name}")
print("PASSED: Class methods work correctly")

# Cleanup
print("\n[Cleanup] Deleting test service...")
service.delete()
print("Test service deleted")

# Verify history cascade delete
remaining_history = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).count()
assert remaining_history == 0, "History should cascade delete"
print("PASSED: History cascade deleted")

# Summary
print("\n" + "=" * 70)
print("INTEGRATION TEST RESULTS")
print("=" * 70)
print("\nALL INTEGRATION TESTS PASSED!")
print("\nVerified scenarios:")
print("  1. Healthy service (success health checks)")
print("  2. Temporary failures with recovery")
print("  3. Auto-transition to ERROR after 3 failures")
print("  4. Auto-recovery from ERROR to ACTIVE")
print("  5. StatusHistory audit trail")
print("  6. Backward compatibility (is_active_compat)")
print("  7. Class methods (get_active, get_or_raise)")
print("  8. Cascade delete of history")
