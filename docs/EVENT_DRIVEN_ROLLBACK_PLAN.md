# Event-Driven Architecture Rollback Plan

> Comprehensive rollback procedure for Event-Driven Architecture implementation in CommandCenter1C Worker

**Last Updated:** 2025-11-18
**Version:** 1.0
**Owner:** Platform Team
**Status:** Active

---

## Table of Contents

1. [Quick Rollback Procedure](#1-quick-rollback-procedure-2-minutes)
2. [Rollback Triggers](#2-rollback-triggers)
3. [Step-by-Step Manual Rollback](#3-step-by-step-manual-rollback)
4. [Verification Checklist](#4-verification-checklist)
5. [Post-Rollback Monitoring](#5-post-rollback-monitoring)
6. [Troubleshooting Common Issues](#6-troubleshooting-common-issues)
7. [Recovery from Failed Rollback](#7-recovery-from-failed-rollback)

---

## 1. Quick Rollback Procedure (< 2 minutes)

### Automated Script (Recommended)

```bash
cd /c/1CProject/command-center-1c
./scripts/rollback-event-driven.sh
```

**Expected Output:**
```
🔄 Starting Event-Driven Architecture Rollback...
[2025-11-18 14:30:00] Step 1/4: Backing up current configuration...
[2025-11-18 14:30:01] Step 2/4: Updating .env.local...
[2025-11-18 14:30:02] Step 3/4: Restarting Worker services...
[2025-11-18 14:30:15] Step 4/4: Verifying rollback...
✅ Rollback complete! HTTP Sync mode active.
```

**Execution Time:** ~15-30 seconds (target: < 2 minutes)

### Dry-Run (No Changes)

```bash
./scripts/rollback-event-driven.sh --dry-run
```

Use this to preview changes without modifying configuration or restarting services.

### Manual Steps (If Script Fails)

1. **Update Configuration**
   ```bash
   cd /c/1CProject/command-center-1c

   # Edit .env.local
   sed -i 's/^ENABLE_EVENT_DRIVEN=true/ENABLE_EVENT_DRIVEN=false/' .env.local
   sed -i 's/^EVENT_DRIVEN_ROLLOUT_PERCENT=.*/EVENT_DRIVEN_ROLLOUT_PERCENT=0.0/' .env.local

   # Or manually edit:
   # ENABLE_EVENT_DRIVEN=false
   # EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
   ```

2. **Restart Worker Services**
   ```bash
   ./scripts/dev/restart.sh worker
   ```

3. **Verify Rollback**
   ```bash
   # Check metrics endpoint
   curl -s http://localhost:9090/api/v1/query?query=worker_execution_mode_total | grep http_sync

   # Expected: http_sync mode should be incrementing
   ```

4. **Optional: Flush Redis Event Channels**
   ```bash
   docker exec -it redis redis-cli
   > DEL events:operation:*
   > DEL events:locks:*
   > exit
   ```

---

## 2. Rollback Triggers

### Automatic Triggers (Circuit Breaker)

These conditions will trigger automatic alerts (manual rollback still required):

| Trigger | Condition | Duration | Severity | Action |
|---------|-----------|----------|----------|--------|
| **Low Success Rate** | Success rate < 95% | 5 minutes | CRITICAL | Immediate rollback |
| **High Latency** | P99 latency > 1 second | 3 minutes | CRITICAL | Immediate rollback |
| **Compensation Spike** | Compensation rate > 10% | 5 minutes | WARNING | Investigate + rollback |
| **Redis Unavailable** | Redis connection failures | 1 minute | CRITICAL | Immediate rollback |

**Prometheus Queries:**

```promql
# Success Rate
(
  rate(worker_execution_success_total{mode="event_driven"}[5m])
  /
  rate(worker_execution_mode_total{mode="event_driven"}[5m])
) < 0.95

# P99 Latency
histogram_quantile(0.99,
  rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m])
) > 1

# Compensation Rate
(
  rate(worker_compensation_executed_total{mode="event_driven"}[5m])
  /
  rate(worker_execution_mode_total{mode="event_driven"}[5m])
) > 0.10

# Redis Unavailable
up{job="redis"} == 0
```

### Manual Decision Criteria

Consider rollback if you observe:

1. **User Reports**
   - Multiple reports of stuck operations
   - Operations not completing
   - Incorrect operation status in UI

2. **Database Issues**
   - Increasing number of locks not releasing
   - PostgreSQL connection pool exhaustion
   - Long-running queries (> 15 seconds)

3. **Resource Spikes**
   - Memory usage > 200% of baseline
   - CPU usage > 200% of baseline
   - Disk I/O saturation

4. **Error Rate Increase**
   - Error rate increase > 5% compared to HTTP Sync baseline
   - New error types appearing in logs
   - Retry rate > 15%

5. **Operational Issues**
   - Redis memory usage > 80%
   - Event queue depth growing unbounded
   - Worker processes crashing or restarting frequently

**Decision Matrix:**

| Criteria | Threshold | Action | Priority |
|----------|-----------|--------|----------|
| Success rate < 95% | 5 min | ROLLBACK | P0 |
| P99 latency > 1s | 3 min | ROLLBACK | P0 |
| Compensation > 10% | 5 min | ROLLBACK | P1 |
| User reports > 3 | Any time | INVESTIGATE | P1 |
| Resource spike > 200% | 10 min | ROLLBACK | P1 |

---

## 3. Step-by-Step Manual Rollback

### Phase 1: Pre-Rollback (5 minutes)

#### Step 1.1: Document Current State

```bash
# Capture current metrics
curl -s http://localhost:9090/api/v1/query?query=worker_execution_mode_total > /tmp/pre-rollback-metrics.txt

# Capture configuration
cp .env.local .env.local.pre-rollback-$(date +%Y%m%d_%H%M%S)

# Check active operations
docker exec -it postgres psql -U commandcenter -d commandcenter -c \
  "SELECT status, COUNT(*) FROM operations_operation GROUP BY status;"
```

#### Step 1.2: Notify Team

Send notification to:
- Platform team on Slack (#platform-alerts)
- On-call engineer via PagerDuty
- Engineering manager

**Template:**
```
🚨 ROLLBACK IN PROGRESS
Feature: Event-Driven Architecture
Trigger: [describe reason]
Impact: [describe current impact]
ETA: 5-10 minutes
Status: Pre-rollback checks complete
```

### Phase 2: Execute Rollback (2 minutes)

#### Step 2.1: Stop Worker Services

```bash
cd /c/1CProject/command-center-1c
./scripts/dev/stop.sh worker
```

Wait for graceful shutdown (30 seconds max).

#### Step 2.2: Update Configuration

**Option A: Using sed (automated)**
```bash
sed -i 's/^ENABLE_EVENT_DRIVEN=.*/ENABLE_EVENT_DRIVEN=false/' .env.local
sed -i 's/^EVENT_DRIVEN_ROLLOUT_PERCENT=.*/EVENT_DRIVEN_ROLLOUT_PERCENT=0.0/' .env.local
sed -i 's/^EVENT_DRIVEN_TARGET_DBS=.*/EVENT_DRIVEN_TARGET_DBS=/' .env.local
```

**Option B: Manual edit**

Edit `.env.local`:
```bash
# Event-Driven Feature Flags
ENABLE_EVENT_DRIVEN=false
EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
EVENT_DRIVEN_TARGET_DBS=

# Safety switches
EVENT_DRIVEN_EXTENSIONS=false
EVENT_DRIVEN_BACKUPS=false
```

Verify changes:
```bash
cat .env.local | grep EVENT_DRIVEN
```

#### Step 2.3: Restart Worker Services

```bash
./scripts/dev/restart.sh worker
```

Monitor logs during startup:
```bash
tail -f logs/worker.log
```

Expected log output:
```
INFO feature flags loaded enable_event_driven=false rollout=0.0
INFO worker started mode=http_sync pool_size=50
```

### Phase 3: Verification (3 minutes)

#### Step 3.1: Check Worker Health

```bash
# Worker should be running
ps aux | grep cc1c-worker

# Check PID file
cat pids/worker.pid
```

#### Step 3.2: Verify HTTP Sync Mode Active

```bash
# Query Prometheus for execution mode
curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_mode_total[1m])' | jq '.data.result[] | select(.metric.mode == "http_sync")'

# Should show non-zero rate for http_sync
```

#### Step 3.3: Verify No Event-Driven Operations

```bash
# No event_driven metrics should increment
curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_mode_total{mode="event_driven"}[1m])' | jq '.data.result'

# Should return empty or zero rate
```

#### Step 3.4: Check Redis Event Channels

```bash
docker exec -it redis redis-cli

# Check for remaining events
> KEYS events:operation:*
> KEYS events:locks:*

# Should return empty or minimal results
```

### Phase 4: Post-Rollback (10 minutes)

#### Step 4.1: Monitor Success Rate

```bash
# Watch success rate for HTTP Sync mode
watch -n 5 'curl -s "http://localhost:9090/api/v1/query?query=rate(worker_execution_success_total{mode=\"http_sync\"}[5m]) / rate(worker_execution_mode_total{mode=\"http_sync\"}[5m])" | jq ".data.result[0].value[1]"'
```

Target: > 95% success rate

#### Step 4.2: Monitor Latency

```bash
# P99 latency for HTTP Sync
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket{mode="http_sync"}[5m]))' | jq '.data.result[0].value[1]'
```

Target: < 500ms (HTTP Sync baseline)

#### Step 4.3: Check for Stuck Operations

```bash
docker exec -it postgres psql -U commandcenter -d commandcenter -c \
  "SELECT id, operation_type, status, created_at
   FROM operations_operation
   WHERE status IN ('processing', 'pending')
   AND created_at < NOW() - INTERVAL '10 minutes';"
```

Should return empty result (no stuck operations).

---

## 4. Verification Checklist

Use this checklist to verify successful rollback:

### Immediate Verification (< 5 minutes)

- [ ] **Configuration Updated**
  ```bash
  grep "ENABLE_EVENT_DRIVEN=false" .env.local
  grep "EVENT_DRIVEN_ROLLOUT_PERCENT=0.0" .env.local
  ```

- [ ] **Worker Restarted**
  ```bash
  ps aux | grep cc1c-worker
  cat pids/worker.pid
  ```

- [ ] **HTTP Sync Mode Active**
  ```bash
  curl -s 'http://localhost:9090/api/v1/query?query=worker_execution_mode_total{mode="http_sync"}' | jq '.data.result[0].value[1]'
  # Should be incrementing
  ```

- [ ] **No Event-Driven Operations**
  ```bash
  curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_mode_total{mode="event_driven"}[1m])' | jq '.data.result'
  # Should be empty or zero
  ```

### Short-Term Verification (10-30 minutes)

- [ ] **Success Rate Restored**
  ```bash
  # Target: > 95%
  curl -s 'http://localhost:9090/api/v1/query?query=rate(worker_execution_success_total{mode="http_sync"}[5m]) / rate(worker_execution_mode_total{mode="http_sync"}[5m])'
  ```

- [ ] **Latency Normal**
  ```bash
  # Target: < 500ms
  curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket{mode="http_sync"}[5m]))'
  ```

- [ ] **No Stuck Operations**
  ```bash
  docker exec -it postgres psql -U commandcenter -d commandcenter -c \
    "SELECT COUNT(*) FROM operations_operation WHERE status IN ('processing', 'pending') AND created_at < NOW() - INTERVAL '10 minutes';"
  # Should return 0
  ```

- [ ] **Redis Queue Empty**
  ```bash
  docker exec -it redis redis-cli
  > LLEN operations_queue
  # Should return 0 or minimal value
  ```

- [ ] **No Active Locks**
  ```bash
  docker exec -it redis redis-cli
  > KEYS events:locks:*
  # Should return empty
  ```

### Long-Term Verification (1-24 hours)

- [ ] **No User Reports** - Zero reports of stuck operations or errors

- [ ] **Resource Usage Normal**
  ```bash
  # CPU usage < 80%
  # Memory usage < 80%
  # No memory leaks
  ```

- [ ] **Error Rate Baseline**
  ```bash
  # Error rate back to pre-Event-Driven baseline (< 2%)
  ```

- [ ] **Database Health**
  ```bash
  # No long-running queries
  # No lock contention
  # Connection pool utilization < 80%
  ```

### Sign-Off

After all checks pass:

```
Rollback Complete - Sign-Off

Date: _______________
Engineer: _______________
Success Rate: _______________
P99 Latency: _______________
Stuck Operations: 0
Duration: _______________ minutes

Approved By: _______________
```

---

## 5. Post-Rollback Monitoring

### Monitoring Dashboard

Access Grafana dashboard:
```
http://localhost:3001/d/ab-testing-event-driven
```

**Key Panels to Watch:**

1. **Execution Mode Distribution**
   - Should show 100% HTTP Sync
   - Event-Driven should be 0%

2. **Success Rate by Mode**
   - HTTP Sync should be > 95%

3. **P99 Latency by Mode**
   - HTTP Sync should be < 500ms

4. **Compensation Actions**
   - Should drop to zero

5. **Circuit Breaker Trips**
   - Should stop incrementing

### Prometheus Alerts

Post-rollback, these alerts should clear:

- `EventDrivenSuccessRateLow` - Should resolve within 5 minutes
- `EventDrivenLatencyHigh` - Should resolve within 3 minutes
- `EventDrivenCompensationHigh` - Should resolve within 5 minutes

### Monitoring Period

**Phase 1: Intensive (First 30 minutes)**
- Check dashboard every 5 minutes
- Monitor success rate and latency
- Watch for stuck operations

**Phase 2: Active (1-4 hours)**
- Check dashboard every 30 minutes
- Verify no regressions
- Monitor resource usage

**Phase 3: Passive (4-24 hours)**
- Automated alerts only
- Daily check of metrics
- Review incident post-mortem

---

## 6. Troubleshooting Common Issues

### Issue 1: Worker Won't Start After Rollback

**Symptoms:**
- Worker process exits immediately
- Error in logs: "failed to load configuration"

**Solution:**
```bash
# Check .env.local syntax
cat .env.local | grep EVENT_DRIVEN

# Verify no syntax errors
source .env.local

# Restart with verbose logging
cd go-services/worker
LOG_LEVEL=debug go run cmd/main.go
```

### Issue 2: Redis Event Channels Not Clearing

**Symptoms:**
- `KEYS events:*` shows many entries
- Operations still in Redis but not in PostgreSQL

**Solution:**
```bash
# Manual cleanup
docker exec -it redis redis-cli

# Delete all event-related keys
> DEL events:operation:*
> DEL events:locks:*

# Verify cleanup
> KEYS events:*
# Should return empty
```

### Issue 3: Operations Still Using Event-Driven Mode

**Symptoms:**
- Metrics show event_driven mode still active
- Configuration shows `ENABLE_EVENT_DRIVEN=false`

**Solution:**
```bash
# Force kill worker process
pkill -9 -f cc1c-worker

# Delete PID file
rm pids/worker.pid

# Clear Go build cache
cd go-services/worker
go clean -cache

# Rebuild and restart
go build -o ../../bin/cc1c-worker.exe cmd/main.go
cd ../..
./scripts/dev/restart.sh worker
```

### Issue 4: Success Rate Still Low After Rollback

**Symptoms:**
- HTTP Sync success rate < 95%
- No improvement after rollback

**Solution:**
```bash
# This indicates a deeper issue (not related to Event-Driven)

# Check database health
docker exec -it postgres psql -U commandcenter -d commandcenter -c \
  "SELECT pid, state, query FROM pg_stat_activity WHERE state != 'idle';"

# Check Redis health
docker exec -it redis redis-cli INFO

# Check orchestrator logs
tail -100 logs/orchestrator.log | grep ERROR

# Contact platform team for deeper investigation
```

### Issue 5: Rollback Script Fails Mid-Execution

**Symptoms:**
- Script exits with error code 1
- Partial configuration update

**Solution:**
```bash
# Restore from backup
cp .env.local.pre-rollback-* .env.local

# Run rollback script again
./scripts/rollback-event-driven.sh

# If script still fails, manual rollback
# Follow "Step-by-Step Manual Rollback" section above
```

---

## 7. Recovery from Failed Rollback

### Scenario: Complete Rollback Failure

If rollback fails completely and system is unstable:

#### Emergency Recovery Steps

1. **Stop All Workers**
   ```bash
   pkill -9 -f cc1c-worker
   rm pids/worker.pid
   ```

2. **Restore Configuration from Git**
   ```bash
   # If .env.local is in git history
   git checkout HEAD~10 -- .env.local

   # Or restore from backup
   cp .env.local.backup .env.local
   ```

3. **Clear All State**
   ```bash
   # Clear Redis
   docker exec -it redis redis-cli FLUSHALL

   # Reset stuck operations in PostgreSQL
   docker exec -it postgres psql -U commandcenter -d commandcenter -c \
     "UPDATE operations_operation SET status='failed', error='Rollback recovery' WHERE status IN ('processing', 'pending');"
   ```

4. **Rebuild Worker from Clean State**
   ```bash
   cd go-services/worker
   go clean -modcache
   go clean -cache
   go mod download
   go build -o ../../bin/cc1c-worker.exe cmd/main.go
   ```

5. **Start with Minimal Configuration**
   ```bash
   # Use bare minimum .env.local
   cat > .env.local << EOF
   ENABLE_EVENT_DRIVEN=false
   EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
   LOG_LEVEL=debug
   EOF

   ./scripts/dev/restart.sh worker
   ```

#### Escalation Path

If emergency recovery fails:

1. **Contact Platform Team Lead** - Slack #platform-emergency
2. **Page On-Call Engineer** - PagerDuty "P0 - System Down"
3. **Consider Full System Restart**
   ```bash
   ./scripts/dev/stop-all.sh
   docker-compose down
   docker-compose up -d postgres redis
   ./scripts/dev/start-all.sh --force-rebuild
   ```

---

## Appendix A: Related Documentation

- [Event-Driven Architecture Design](./EVENT_DRIVEN_ARCHITECTURE.md)
- [Feature Flags Configuration](../go-services/worker/internal/config/feature_flags.go)
- [A/B Testing Metrics](../go-services/worker/internal/metrics/ab_testing.go)
- [Worker State Machine](../go-services/worker/internal/statemachine/)
- [Prometheus Alerts](../infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml)

## Appendix B: Runbook Links

- **Success Rate Low**: https://wiki.commandcenter1c.local/runbooks/success-rate-low
- **Latency High**: https://wiki.commandcenter1c.local/runbooks/latency-high
- **Redis Unavailable**: https://wiki.commandcenter1c.local/runbooks/redis-unavailable
- **Worker Crash Loop**: https://wiki.commandcenter1c.local/runbooks/worker-crash-loop

## Appendix C: Contact Information

- **Platform Team**: #platform-team (Slack)
- **On-Call Engineer**: PagerDuty "Platform On-Call"
- **Engineering Manager**: manager@commandcenter1c.local
- **SRE Team**: #sre-support (Slack)

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-18 | Platform Team | Initial version |

**Next Review Date:** 2025-12-18
