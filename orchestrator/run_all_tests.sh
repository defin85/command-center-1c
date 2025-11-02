#!/bin/bash
# Run all BatchService migration tests

echo "=============================================================="
echo "BatchService Migration Test Suite"
echo "Migration: 0010_migrate_batch_service_to_status"
echo "=============================================================="
echo ""

# Test 1: Data Migration
echo "[1/4] Running data migration tests..."
python test_migration_data.py
if [ $? -ne 0 ]; then
    echo "FAILED: Data migration test failed"
    exit 1
fi
echo ""

# Test 2: Model Tests
echo "[2/4] Running BatchService model tests..."
python test_batch_service_model.py
if [ $? -ne 0 ]; then
    echo "FAILED: Model test failed"
    exit 1
fi
echo ""

# Test 3: StatusHistory Tests
echo "[3/4] Running StatusHistory tests..."
python test_status_history.py
if [ $? -ne 0 ]; then
    echo "FAILED: StatusHistory test failed"
    exit 1
fi
echo ""

# Test 4: Integration Tests
echo "[4/4] Running integration tests..."
python test_integration_full.py
if [ $? -ne 0 ]; then
    echo "FAILED: Integration test failed"
    exit 1
fi
echo ""

echo "=============================================================="
echo "ALL TESTS PASSED!"
echo "=============================================================="
echo ""
echo "Test Report: MIGRATION_TEST_REPORT.md"
echo ""
echo "Migration is ready for production deployment"
echo ""
