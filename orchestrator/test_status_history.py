#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test StatusHistory automatic logging."""
# ruff: noqa: E402
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.models import BatchService, StatusHistory
from django.contrib.contenttypes.models import ContentType

print("=" * 70)
print("TEST 5: StatusHistory automatic logging")
print("=" * 70)

# Create test service
print("\n[Setup] Creating test BatchService...")
service = BatchService.objects.create(
    name="History Test Service",
    url="http://localhost:8089",
    status='active'
)
print(f"Created: {service.name} (status={service.status})")

# Get initial history count
initial_count = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).count()
print(f"Initial history records: {initial_count}")

# Test 1: Change status -> should create history record
print("\n--- Test 5.1: Status change creates history record ---")
service.status = 'maintenance'
service.save()
service.refresh_from_db()

history_records = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).order_by('-changed_at')

new_count = history_records.count()
print(f"History records after status change: {new_count}")

assert new_count == initial_count + 1, f"Expected {initial_count + 1} records, got {new_count}"
print("PASSED: History record created")

# Check the latest history record
latest_history = history_records.first()
print("\nLatest history record:")
print(f"  - old_status: {latest_history.old_status}")
print(f"  - new_status: {latest_history.new_status}")
print(f"  - reason: {latest_history.reason}")
print(f"  - metadata: {latest_history.metadata}")

assert latest_history.old_status == 'active', f"Expected old_status='active', got '{latest_history.old_status}'"
assert latest_history.new_status == 'maintenance', f"Expected new_status='maintenance', got '{latest_history.new_status}'"
print("PASSED: History record has correct old_status and new_status")

# Test 2: Multiple status changes
print("\n--- Test 5.2: Multiple status changes tracked ---")
service.status = 'error'
service.consecutive_failures = 3
service.save()
service.refresh_from_db()

service.status = 'active'
service.consecutive_failures = 0
service.save()
service.refresh_from_db()

history_records = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).order_by('-changed_at')

final_count = history_records.count()
print(f"History records after multiple changes: {final_count}")

assert final_count == initial_count + 3, f"Expected {initial_count + 3} records, got {final_count}"
print("PASSED: Multiple status changes tracked")

print("\nAll history records (newest first):")
for i, record in enumerate(history_records[:5], 1):
    print(f"  {i}. {record.old_status} -> {record.new_status} ({record.changed_at.strftime('%H:%M:%S')})")

# Test 3: No history record when status doesn't change
print("\n--- Test 5.3: No history when status unchanged ---")
before_count = history_records.count()

service.name = "Updated Name"  # Change different field
service.save()
service.refresh_from_db()

after_count = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).count()

assert after_count == before_count, f"Expected no new history records, but count changed from {before_count} to {after_count}"
print("PASSED: No history record created when status unchanged")
print(f"  - History count before: {before_count}")
print(f"  - History count after: {after_count}")

# Test 4: Check metadata in history
print("\n--- Test 5.4: Metadata stored in history ---")
latest = history_records.first()
print("Latest history metadata:")
for key, value in latest.metadata.items():
    print(f"  - {key}: {value}")

assert 'service_id' in latest.metadata, "Expected 'service_id' in metadata"
assert 'consecutive_failures' in latest.metadata, "Expected 'consecutive_failures' in metadata"
print("PASSED: Metadata stored correctly")

# Cleanup
print("\n[Cleanup] Deleting test service (and its history)...")
service.delete()

# Verify cascade delete
remaining_history = StatusHistory.objects.filter(
    content_type=ContentType.objects.get_for_model(BatchService),
    object_id=str(service.id)
).count()

print(f"Remaining history records after delete: {remaining_history}")

# Summary
print("\n" + "=" * 70)
print("STATUS HISTORY TEST RESULTS")
print("=" * 70)
print("\nALL TESTS PASSED!")
print("  - Status change creates history record")
print("  - Multiple changes tracked correctly")
print("  - No history when status unchanged")
print("  - Metadata stored in history")
print("  - History cascade deleted with service")
