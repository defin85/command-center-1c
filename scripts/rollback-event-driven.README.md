# Event-Driven Architecture Rollback Script

> Automated rollback script for Event-Driven Architecture implementation

**Script:** `scripts/rollback-event-driven.sh`
**Execution Time:** < 2 minutes (typical: 15-30 seconds)
**Version:** 1.0

---

## Quick Start

### Normal Rollback
```bash
cd /c/1CProject/command-center-1c
./scripts/rollback-event-driven.sh
```

### Dry Run (Preview Changes)
```bash
./scripts/rollback-event-driven.sh --dry-run
```

### Rollback Without Redis Cleanup
```bash
./scripts/rollback-event-driven.sh --skip-redis-flush
```

---

## What It Does

The rollback script performs the following steps:

1. **Backup Configuration** (Step 1/4)
   - Creates timestamped backup of `.env.local`
   - Backup location: `.env.local.backup-YYYYMMDD_HHMMSS`

2. **Update Configuration** (Step 2/4)
   - Sets `ENABLE_EVENT_DRIVEN=false`
   - Sets `EVENT_DRIVEN_ROLLOUT_PERCENT=0.0`
   - Clears `EVENT_DRIVEN_TARGET_DBS`
   - Disables operation type targeting

3. **Restart Worker Service** (Step 3/4)
   - Gracefully stops Worker process
   - Starts Worker with new configuration
   - Verifies Worker is running in HTTP Sync mode

4. **Verify Rollback** (Step 4/4)
   - Queries Prometheus for execution mode metrics
   - Confirms HTTP Sync mode is active
   - Verifies Event-Driven mode is disabled

5. **Flush Redis Channels** (Optional)
   - Cleans up event-related Redis keys
   - Removes `events:operation:*` keys
   - Removes `events:locks:*` keys

---

## Usage Examples

### Example 1: Normal Rollback

```bash
$ ./scripts/rollback-event-driven.sh

========================================
  🔄 Event-Driven Architecture Rollback
========================================

[2025-11-18 14:30:00] INFO: Checking prerequisites...
[2025-11-18 14:30:01] ✓ Prerequisites check passed
[2025-11-18 14:30:01] INFO: Step 1/4: Backing up current configuration...
[2025-11-18 14:30:01] ✓ Configuration backed up to: .env.local.backup-20251118_143001
[2025-11-18 14:30:02] INFO: Step 2/4: Updating .env.local...
[2025-11-18 14:30:02] ✓ Configuration updated
[2025-11-18 14:30:03] INFO: Step 3/4: Restarting Worker service...
[2025-11-18 14:30:15] ✓ Worker service restarted (PID: 12345)
[2025-11-18 14:30:15] ✓ Worker started in HTTP Sync mode
[2025-11-18 14:30:20] INFO: Step 4/4: Verifying rollback...
[2025-11-18 14:30:25] ✓ HTTP Sync mode verified via Prometheus
[2025-11-18 14:30:26] INFO: Optional: Flushing Redis event channels...
[2025-11-18 14:30:28] ✓ Redis event channels flushed

========================================
  ✅ Rollback Complete!
========================================

Summary:
  ✓ Configuration backed up: .env.local.backup-20251118_143001
  ✓ ENABLE_EVENT_DRIVEN=false
  ✓ EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
  ✓ Worker service restarted
  ✓ HTTP Sync mode active

✅ Rollback completed in 28 seconds
```

### Example 2: Dry Run (No Changes)

```bash
$ ./scripts/rollback-event-driven.sh --dry-run

========================================
  🔄 Event-Driven Architecture Rollback
========================================

⚠️  DRY RUN MODE - No changes will be made

[2025-11-18 14:35:00] INFO: Checking prerequisites...
[2025-11-18 14:35:01] ✓ Prerequisites check passed
[2025-11-18 14:35:01] INFO: Step 1/4: Backing up current configuration...
[2025-11-18 14:35:01] DEBUG: DRY RUN: Would backup .env.local to .env.local.backup-20251118_143501
[2025-11-18 14:35:02] INFO: Step 2/4: Updating .env.local...
[2025-11-18 14:35:02] DEBUG: DRY RUN: Would update configuration to:
  ENABLE_EVENT_DRIVEN=false
  EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
  EVENT_DRIVEN_TARGET_DBS=
[2025-11-18 14:35:03] INFO: Step 3/4: Restarting Worker service...
[2025-11-18 14:35:03] DEBUG: DRY RUN: Would restart Worker service
[2025-11-18 14:35:04] INFO: Step 4/4: Verifying rollback...
[2025-11-18 14:35:04] DEBUG: DRY RUN: Would verify rollback via Prometheus
[2025-11-18 14:35:05] INFO: Optional: Flushing Redis event channels...
[2025-11-18 14:35:05] DEBUG: DRY RUN: Would flush Redis event channels

========================================
  ✅ Rollback Complete!
========================================

DRY RUN MODE: No changes were made
Run without --dry-run to execute rollback
```

### Example 3: Rollback Without Redis Cleanup

```bash
$ ./scripts/rollback-event-driven.sh --skip-redis-flush

(same output as Example 1, but skips Redis flush step)

[2025-11-18 14:40:26] INFO: Optional: Flushing Redis event channels...
[2025-11-18 14:40:26] INFO: Skipping Redis flush (--skip-redis-flush flag)
```

---

## Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without modifying system. Safe to run anytime. |
| `--skip-redis-flush` | Skip Redis event channels cleanup. Use if Redis is unavailable or you want to preserve events. |
| `--help` | Show help message with usage information. |

---

## Prerequisites

The script checks for these prerequisites automatically:

1. **`.env.local` file exists** - Configuration file for environment variables
2. **`scripts/dev/restart.sh` exists** - Worker restart script
3. **`curl` available** (optional) - For Prometheus verification
4. **`docker` available** (optional) - For Redis flush

If prerequisites are missing, the script will:
- Exit with error for critical prerequisites (.env.local, restart.sh)
- Skip optional steps with warning (curl, docker)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - rollback completed successfully |
| 1 | Failure - check error messages and logs |

---

## Verification Commands

After rollback, verify success using these commands:

### Check Worker Logs
```bash
tail -f logs/worker.log | grep "enable_event_driven"
# Should show: enable_event_driven=false
```

### Query Prometheus Metrics
```bash
# Check HTTP Sync mode is active
curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total{mode="http_sync"}' | jq

# Check Event-Driven mode is NOT active
curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_mode_total{mode="event_driven"}[1m])' | jq
# Should return empty or zero rate
```

### Check Success Rate
```bash
# Success rate should be > 95%
curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_success_total{mode="http_sync"}[5m]) / rate(worker_execution_mode_total{mode="http_sync"}[5m])' | jq '.data.result[0].value[1]'
```

### Check for Stuck Operations
```bash
docker exec -it postgres psql -U commandcenter -d commandcenter -c \
  "SELECT COUNT(*) FROM operations_operation WHERE status IN ('processing', 'pending') AND created_at < NOW() - INTERVAL '10 minutes';"
# Should return 0
```

### Check Redis Queue
```bash
docker exec -it redis redis-cli LLEN operations_queue
# Should return 0 or minimal value
```

---

## Troubleshooting

### Issue: Worker Won't Start

**Symptoms:**
- Script exits with "Failed to restart Worker service"
- Worker logs show configuration errors

**Solution:**
```bash
# Check .env.local syntax
cat .env.local | grep EVENT_DRIVEN

# Manually restart with debug logging
cd go-services/worker
LOG_LEVEL=debug go run cmd/main.go
```

### Issue: Prometheus Verification Fails

**Symptoms:**
- Warning: "Failed to query Prometheus"
- Script completes but verification skipped

**Solution:**
```bash
# Check Prometheus is running
curl http://localhost:9090/-/healthy

# Manually verify metrics
curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total' | jq

# If Prometheus is down, verification can be skipped
# Script will complete successfully
```

### Issue: Redis Flush Fails

**Symptoms:**
- Warning: "docker not available - skipping Redis flush"
- Warning: "Redis container not running"

**Solution:**
```bash
# Check Docker is running
docker ps

# Check Redis container
docker ps | grep redis

# Manual flush if needed
docker exec redis redis-cli --scan --pattern "events:*" | xargs docker exec redis redis-cli DEL
```

### Issue: Configuration Backup Not Created

**Symptoms:**
- Error: "Failed to backup configuration"

**Solution:**
```bash
# Check .env.local exists and is readable
ls -la .env.local

# Check write permissions in project root
touch .env.local.test && rm .env.local.test

# Manual backup
cp .env.local .env.local.backup-manual
```

---

## Recovery from Failed Rollback

If rollback fails mid-execution, the script has error handling:

1. **Automatic rollback** - Restores configuration from backup
2. **Error messages** - Shows detailed error information
3. **Manual recovery** - Follow docs/EVENT_DRIVEN_ROLLBACK_PLAN.md

### Manual Recovery Steps

```bash
# 1. Restore configuration from backup
cp .env.local.backup-YYYYMMDD_HHMMSS .env.local

# 2. Stop worker manually
pkill -9 -f cc1c-worker
rm pids/worker.pid

# 3. Restart worker
./scripts/dev/restart.sh worker

# 4. Verify worker is running
ps aux | grep cc1c-worker
tail -f logs/worker.log
```

---

## Performance

### Execution Time Breakdown

| Step | Typical | Maximum |
|------|---------|---------|
| Prerequisites check | 1s | 2s |
| Backup configuration | 1s | 2s |
| Update configuration | 1s | 2s |
| Restart worker | 10-15s | 30s |
| Verify rollback | 5-10s | 20s |
| Flush Redis (optional) | 2-5s | 10s |
| **Total** | **20-35s** | **68s** |

**Target:** < 2 minutes (120 seconds)
**Average:** 25-30 seconds

### Optimization Tips

- Use `--skip-redis-flush` to save 2-5 seconds if Redis cleanup is not critical
- Pre-check prerequisites before running (reduces failures)
- Ensure Worker graceful shutdown timeout is not too long

---

## Related Documentation

- **Rollback Plan**: [docs/EVENT_DRIVEN_ROLLBACK_PLAN.md](../docs/EVENT_DRIVEN_ROLLBACK_PLAN.md)
- **Feature Flags**: [go-services/worker/internal/config/feature_flags.go](../go-services/worker/internal/config/feature_flags.go)
- **A/B Testing Metrics**: [go-services/worker/internal/metrics/ab_testing.go](../go-services/worker/internal/metrics/ab_testing.go)
- **Prometheus Alerts**: [infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml](../infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml)

---

## Support

- **Documentation**: docs/EVENT_DRIVEN_ROLLBACK_PLAN.md
- **Slack**: #platform-team
- **PagerDuty**: "Platform On-Call"
- **Runbooks**: https://wiki.commandcenter1c.local/runbooks/

---

## FAQ

**Q: Can I run this script multiple times?**
A: Yes, the script is idempotent. Running it multiple times will not cause issues.

**Q: Will this script cause downtime?**
A: Minimal downtime during Worker restart (10-15 seconds). Operations in progress may fail or be retried.

**Q: What happens to operations in progress?**
A: Operations in Event-Driven mode will fail gracefully. Operations will be retried in HTTP Sync mode automatically.

**Q: Can I rollback only specific databases?**
A: No, this script performs full rollback. For partial rollback, manually adjust `EVENT_DRIVEN_ROLLOUT_PERCENT` in `.env.local`.

**Q: How do I restore Event-Driven mode after rollback?**
A: Restore configuration from backup or manually set:
```bash
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.1  # Start with 10%
./scripts/dev/restart.sh worker
```

**Q: Is rollback reversible?**
A: Yes, configuration backup is created. Restore from backup to undo rollback.

**Q: What if the script fails?**
A: Script has automatic error handling and rollback. If complete failure, follow "Recovery from Failed Rollback" section above.

---

**Last Updated:** 2025-11-18
**Maintainer:** Platform Team
**Version:** 1.0
