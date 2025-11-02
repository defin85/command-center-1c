#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test BatchService model and mark_health_check() method."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.models import BatchService

print("=" * 70)
print("TEST 4: BatchService model and mark_health_check()")
print("=" * 70)

# Create test service
print("\n[Setup] Creating test BatchService...")
service = BatchService.objects.create(
    name="Test Service",
    url="http://localhost:8088",
    status=BatchService.STATUS_ACTIVE
)
print(f"Created: {service.name} (status={service.status})")

# Test 1: Initial state
print("\n--- Test 4.1: Check initial state ---")
assert service.status == 'active', f"Expected status='active', got '{service.status}'"
assert service.consecutive_failures == 0, f"Expected consecutive_failures=0, got {service.consecutive_failures}"
assert service.last_health_status == 'unknown', f"Expected last_health_status='unknown', got '{service.last_health_status}'"
print("PASSED: Initial state correct")
print(f"  - status: {service.status}")
print(f"  - consecutive_failures: {service.consecutive_failures}")
print(f"  - last_health_status: {service.last_health_status}")

# Test 2: mark_health_check(success=True)
print("\n--- Test 4.2: mark_health_check(success=True) ---")
service.mark_health_check(success=True)
service.refresh_from_db()

assert service.status == 'active', f"Expected status='active', got '{service.status}'"
assert service.consecutive_failures == 0, f"Expected consecutive_failures=0, got {service.consecutive_failures}"
assert service.last_health_status == 'healthy', f"Expected last_health_status='healthy', got '{service.last_health_status}'"
print("PASSED: Successful health check")
print(f"  - status: {service.status}")
print(f"  - consecutive_failures: {service.consecutive_failures}")
print(f"  - last_health_status: {service.last_health_status}")

# Test 3: First failure (consecutive_failures=1, status still active)
print("\n--- Test 4.3: First failure (consecutive_failures=1) ---")
service.mark_health_check(success=False, error_message="Connection timeout")
service.refresh_from_db()

assert service.consecutive_failures == 1, f"Expected consecutive_failures=1, got {service.consecutive_failures}"
assert service.status == 'active', f"Expected status='active' (not ERROR yet), got '{service.status}'"
assert service.last_health_status == 'unhealthy', f"Expected last_health_status='unhealthy', got '{service.last_health_status}'"
print("PASSED: First failure tracked correctly")
print(f"  - status: {service.status} (still active)")
print(f"  - consecutive_failures: {service.consecutive_failures}")
print(f"  - last_health_status: {service.last_health_status}")

# Test 4: Second failure (consecutive_failures=2, status still active)
print("\n--- Test 4.4: Second failure (consecutive_failures=2) ---")
service.mark_health_check(success=False)
service.refresh_from_db()

assert service.consecutive_failures == 2, f"Expected consecutive_failures=2, got {service.consecutive_failures}"
assert service.status == 'active', f"Expected status='active' (not ERROR yet), got '{service.status}'"
print("PASSED: Second failure tracked correctly")
print(f"  - status: {service.status} (still active)")
print(f"  - consecutive_failures: {service.consecutive_failures}")

# Test 5: Third failure (consecutive_failures=3, status -> ERROR)
print("\n--- Test 4.5: Third failure -> AUTO ERROR status ---")
service.mark_health_check(success=False)
service.refresh_from_db()

assert service.consecutive_failures == 3, f"Expected consecutive_failures=3, got {service.consecutive_failures}"
assert service.status == 'error', f"Expected status='error' (auto-change), got '{service.status}'"
assert service.last_health_status == 'unhealthy', f"Expected last_health_status='unhealthy', got '{service.last_health_status}'"
print("PASSED: Auto-transition to ERROR after 3 failures")
print(f"  - status: {service.status} (AUTO CHANGED to error)")
print(f"  - consecutive_failures: {service.consecutive_failures}")
print(f"  - last_health_status: {service.last_health_status}")

# Test 6: Auto-recovery (ERROR -> ACTIVE on success)
print("\n--- Test 4.6: Auto-recovery (ERROR -> ACTIVE) ---")
service.mark_health_check(success=True)
service.refresh_from_db()

assert service.status == 'active', f"Expected status='active' (auto-recovery), got '{service.status}'"
assert service.consecutive_failures == 0, f"Expected consecutive_failures=0 (reset), got {service.consecutive_failures}"
assert service.last_health_status == 'healthy', f"Expected last_health_status='healthy', got '{service.last_health_status}'"
print("PASSED: Auto-recovery from ERROR to ACTIVE")
print(f"  - status: {service.status} (AUTO RECOVERED)")
print(f"  - consecutive_failures: {service.consecutive_failures} (reset)")
print(f"  - last_health_status: {service.last_health_status}")

# Test 7: Check metadata error message storage
print("\n--- Test 4.7: Error message storage in metadata ---")
service.mark_health_check(success=False, error_message="Test error message")
service.refresh_from_db()

assert 'last_error' in service.metadata, "Expected 'last_error' in metadata"
assert service.metadata['last_error'] == "Test error message", f"Expected error message in metadata"
print("PASSED: Error message stored in metadata")
print(f"  - metadata['last_error']: {service.metadata.get('last_error')}")

# Test 8: Error cleared on success
print("\n--- Test 4.8: Error message cleared on success ---")
service.mark_health_check(success=True)
service.refresh_from_db()

assert 'last_error' not in service.metadata, "Expected 'last_error' removed from metadata on success"
print("PASSED: Error message cleared on success")
print(f"  - metadata: {service.metadata}")

# Cleanup
print("\n[Cleanup] Deleting test service...")
service.delete()
print("Test service deleted")

# Summary
print("\n" + "=" * 70)
print("BATCHSERVICE MODEL TEST RESULTS")
print("=" * 70)
print("\nALL TESTS PASSED!")
print("  - Initial state correct")
print("  - Health check success works")
print("  - Consecutive failures tracked (1, 2, 3)")
print("  - Auto-transition to ERROR after 3 failures")
print("  - Auto-recovery from ERROR to ACTIVE")
print("  - Error messages stored/cleared in metadata")
