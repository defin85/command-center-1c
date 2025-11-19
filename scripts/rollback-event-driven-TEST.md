# Rollback Script Testing Guide

> Quick guide for testing Event-Driven rollback script functionality

**Script:** `scripts/rollback-event-driven.sh`
**Date:** 2025-11-18

---

## Pre-Testing Checklist

Before testing rollback script:

- [ ] `.env.local` file exists
- [ ] Worker service is running
- [ ] Redis container is running
- [ ] Prometheus is accessible (optional)

```bash
# Check prerequisites
ls -la .env.local                          # Should exist
ps aux | grep cc1c-worker                  # Should show process
docker ps | grep redis                     # Should show running
curl http://localhost:9090/-/healthy       # Should return 200 (optional)
```

---

## Test 1: Dry-Run Mode (Safe)

**Purpose:** Verify script logic without making changes

```bash
cd /c/1CProject/command-center-1c
./scripts/rollback-event-driven.sh --dry-run
```

**Expected Output:**
```
========================================
  🔄 Event-Driven Architecture Rollback
========================================

⚠️  DRY RUN MODE - No changes will be made

[2025-11-18 14:30:00] INFO: Checking prerequisites...
[2025-11-18 14:30:01] ✓ Prerequisites check passed
[2025-11-18 14:30:01] INFO: Step 1/4: Backing up current configuration...
[2025-11-18 14:30:01] DEBUG: DRY RUN: Would backup .env.local to .env.local.backup-YYYYMMDD_HHMMSS
[2025-11-18 14:30:02] INFO: Step 2/4: Updating .env.local...
[2025-11-18 14:30:02] DEBUG: DRY RUN: Would update configuration to:
  ENABLE_EVENT_DRIVEN=false
  EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
  EVENT_DRIVEN_TARGET_DBS=
[2025-11-18 14:30:03] INFO: Step 3/4: Restarting Worker service...
[2025-11-18 14:30:03] DEBUG: DRY RUN: Would restart Worker service
[2025-11-18 14:30:04] INFO: Step 4/4: Verifying rollback...
[2025-11-18 14:30:04] DEBUG: DRY RUN: Would verify rollback via Prometheus
[2025-11-18 14:30:05] INFO: Optional: Flushing Redis event channels...
[2025-11-18 14:30:05] DEBUG: DRY RUN: Would flush Redis event channels

========================================
  ✅ Rollback Complete!
========================================

DRY RUN MODE: No changes were made
Run without --dry-run to execute rollback

✅ Rollback completed in 0 seconds
```

**Success Criteria:**
- [ ] Script runs without errors
- [ ] All steps shown in output
- [ ] No actual changes made to system
- [ ] Exit code 0

---

## Test 2: Help Message

**Purpose:** Verify help output is correct

```bash
./scripts/rollback-event-driven.sh --help
```

**Expected Output:**
```
CommandCenter1C - Event-Driven Architecture Rollback

USAGE:
    ./scripts/rollback-event-driven.sh [OPTIONS]

OPTIONS:
    --dry-run           Preview changes without modifying system
    --skip-redis-flush  Skip Redis event channels cleanup
    --help              Show this help message

EXAMPLES:
    # Normal rollback
    ./scripts/rollback-event-driven.sh
    ...
```

**Success Criteria:**
- [ ] Help message displays correctly
- [ ] All options documented
- [ ] Examples provided
- [ ] Exit code 0

---

## Test 3: Prerequisites Check Failure

**Purpose:** Verify script handles missing prerequisites gracefully

```bash
# Temporarily move .env.local
mv .env.local .env.local.temp

# Run script (should fail)
./scripts/rollback-event-driven.sh --dry-run

# Restore .env.local
mv .env.local.temp .env.local
```

**Expected Output:**
```
[2025-11-18 14:35:00] INFO: Checking prerequisites...
[2025-11-18 14:35:01] ERROR: .env.local not found: /c/1CProject/command-center-1c/.env.local
[2025-11-18 14:35:01] ERROR: Run 'cp .env.local.example .env.local' first
```

**Success Criteria:**
- [ ] Script detects missing .env.local
- [ ] Clear error message shown
- [ ] Exit code 1 (failure)
- [ ] No changes made to system

---

## Test 4: Configuration Backup

**Purpose:** Verify configuration is backed up correctly

```bash
# Add test flag to .env.local
echo "TEST_FLAG=before_rollback" >> .env.local

# Run dry-run
./scripts/rollback-event-driven.sh --dry-run

# Check no backup was created (dry-run)
ls -la .env.local.backup-* 2>/dev/null || echo "No backup (expected in dry-run)"

# Restore original state
sed -i '/TEST_FLAG=before_rollback/d' .env.local
```

**Success Criteria:**
- [ ] Dry-run doesn't create backup
- [ ] Original .env.local unchanged

---

## Test 5: Configuration Update (Dry-Run)

**Purpose:** Verify configuration update logic

```bash
# Add Event-Driven flags to .env.local
cat >> .env.local << 'EOF'
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.5
EVENT_DRIVEN_TARGET_DBS=db1,db2
EVENT_DRIVEN_EXTENSIONS=true
EVENT_DRIVEN_BACKUPS=true
EOF

# Run dry-run
./scripts/rollback-event-driven.sh --dry-run

# Check output shows correct changes
# Should show:
#   Current: ENABLE_EVENT_DRIVEN=true
#   Would update to: ENABLE_EVENT_DRIVEN=false

# Verify .env.local unchanged
grep "ENABLE_EVENT_DRIVEN=true" .env.local

# Cleanup
sed -i '/ENABLE_EVENT_DRIVEN=/d' .env.local
sed -i '/EVENT_DRIVEN_ROLLOUT_PERCENT=/d' .env.local
sed -i '/EVENT_DRIVEN_TARGET_DBS=/d' .env.local
sed -i '/EVENT_DRIVEN_EXTENSIONS=/d' .env.local
sed -i '/EVENT_DRIVEN_BACKUPS=/d' .env.local
```

**Success Criteria:**
- [ ] Script shows current configuration
- [ ] Script shows intended changes
- [ ] No actual changes made
- [ ] Original .env.local preserved

---

## Test 6: Skip Redis Flush

**Purpose:** Verify --skip-redis-flush option works

```bash
./scripts/rollback-event-driven.sh --dry-run --skip-redis-flush
```

**Expected Output:**
```
...
[2025-11-18 14:40:26] INFO: Optional: Flushing Redis event channels...
[2025-11-18 14:40:26] INFO: Skipping Redis flush (--skip-redis-flush flag)
...
```

**Success Criteria:**
- [ ] Redis flush step shows "Skipping"
- [ ] No Redis operations attempted
- [ ] Script completes successfully

---

## Test 7: Execution Time

**Purpose:** Verify script completes within 2 minutes

```bash
time ./scripts/rollback-event-driven.sh --dry-run
```

**Expected Output:**
```
...
✅ Rollback completed in 0 seconds
...

real    0m1.234s
user    0m0.123s
sys     0m0.045s
```

**Success Criteria:**
- [ ] Total execution time < 2 minutes (120s)
- [ ] Typical dry-run: < 5 seconds
- [ ] Script reports execution time

---

## Test 8: Error Handling

**Purpose:** Verify script handles errors gracefully

```bash
# Make restart.sh temporarily unavailable
mv scripts/dev/restart.sh scripts/dev/restart.sh.backup

# Run script (should fail gracefully)
./scripts/rollback-event-driven.sh --dry-run

# Restore restart.sh
mv scripts/dev/restart.sh.backup scripts/dev/restart.sh
```

**Expected Output:**
```
[2025-11-18 14:45:00] INFO: Checking prerequisites...
[2025-11-18 14:45:01] ERROR: restart.sh not found: /c/1CProject/command-center-1c/scripts/dev/restart.sh
```

**Success Criteria:**
- [ ] Script detects missing restart.sh
- [ ] Clear error message
- [ ] Exit code 1
- [ ] No partial changes

---

## Test 9: Multiple Dry-Runs (Idempotency)

**Purpose:** Verify script can be run multiple times safely

```bash
# Run dry-run 3 times
./scripts/rollback-event-driven.sh --dry-run
./scripts/rollback-event-driven.sh --dry-run
./scripts/rollback-event-driven.sh --dry-run
```

**Success Criteria:**
- [ ] All 3 runs complete successfully
- [ ] Identical output each time
- [ ] No side effects
- [ ] Exit code 0 for all runs

---

## Test 10: Invalid Arguments

**Purpose:** Verify script rejects invalid arguments

```bash
./scripts/rollback-event-driven.sh --invalid-option
```

**Expected Output:**
```
ERROR: Unknown option: --invalid-option

CommandCenter1C - Event-Driven Architecture Rollback

USAGE:
    ./scripts/rollback-event-driven.sh [OPTIONS]
...
```

**Success Criteria:**
- [ ] Script detects invalid option
- [ ] Shows error message
- [ ] Displays help
- [ ] Exit code 1

---

## Full Rollback Test (Optional - Use with Caution)

**⚠️  WARNING:** This test will actually modify system state!

Only run if:
- You have Event-Driven mode enabled
- You can afford brief Worker downtime
- You have tested dry-run successfully

```bash
# 1. Enable Event-Driven mode first
cat >> .env.local << 'EOF'
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.1
EOF

# 2. Restart Worker
./scripts/dev/restart.sh worker

# 3. Verify Event-Driven mode active
curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total{mode="event_driven"}' | jq

# 4. Execute rollback
./scripts/rollback-event-driven.sh

# 5. Verify rollback successful
grep "ENABLE_EVENT_DRIVEN=false" .env.local
curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total{mode="http_sync"}' | jq

# 6. Check backup was created
ls -la .env.local.backup-*

# 7. Verify Worker is running
ps aux | grep cc1c-worker
tail -50 logs/worker.log
```

**Success Criteria:**
- [ ] Backup created successfully
- [ ] Configuration updated correctly
- [ ] Worker restarted successfully
- [ ] HTTP Sync mode active
- [ ] No stuck operations
- [ ] Execution time < 2 minutes

---

## Prometheus Alerts Testing

**Purpose:** Verify alerts are syntactically correct

```bash
# If promtool is installed
promtool check rules infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml

# Manual inspection
cat infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml | head -100
```

**Success Criteria:**
- [ ] YAML syntax is valid
- [ ] 8 alert rules defined
- [ ] All required fields present (alert, expr, for, labels, annotations)
- [ ] Queries are syntactically correct

---

## Summary Checklist

After running all tests:

- [ ] Test 1: Dry-run mode works
- [ ] Test 2: Help message displays
- [ ] Test 3: Prerequisites check works
- [ ] Test 4: Configuration backup logic correct
- [ ] Test 5: Configuration update logic correct
- [ ] Test 6: Skip Redis flush works
- [ ] Test 7: Execution time < 2 minutes
- [ ] Test 8: Error handling works
- [ ] Test 9: Idempotency verified
- [ ] Test 10: Invalid arguments rejected
- [ ] Test 11 (Optional): Full rollback successful
- [ ] Prometheus alerts syntax valid

---

## Troubleshooting Test Failures

### Dry-Run Fails

```bash
# Check script permissions
ls -la scripts/rollback-event-driven.sh
chmod +x scripts/rollback-event-driven.sh

# Check bash version
bash --version  # Should be 4.0+

# Run with debug output
bash -x scripts/rollback-event-driven.sh --dry-run
```

### Prerequisites Check Fails

```bash
# Verify .env.local exists
ls -la .env.local
cp .env.local.example .env.local  # If missing

# Verify restart.sh exists
ls -la scripts/dev/restart.sh
```

### Prometheus Verification Fails

```bash
# Check Prometheus is running
curl http://localhost:9090/-/healthy

# If Prometheus down, verification will be skipped
# This is expected and not a failure
```

---

## Next Steps

After successful testing:

1. Document test results
2. Share results with team
3. Schedule full rollback drill with platform team
4. Update runbook based on test findings

---

**Test Completion Sign-Off:**

Date: _______________
Tester: _______________
Tests Passed: ___ / 11
Notes: _______________
Approved: _______________
