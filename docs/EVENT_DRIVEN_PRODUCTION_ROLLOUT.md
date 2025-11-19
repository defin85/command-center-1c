# Event-Driven Architecture: Production Rollout Guide

> Comprehensive guide for phased rollout of Event-Driven Architecture in CommandCenter1C

**Version:** 1.0
**Date:** 2025-11-18
**Status:** Ready for Production

---

## Table of Contents

1. [Overview](#overview)
2. [Rollout Strategy](#rollout-strategy)
3. [Pre-Rollout Checklist](#pre-rollout-checklist)
4. [Phase 1: 10% Rollout](#phase-1-10-rollout)
5. [Phase 2: 50% Rollout](#phase-2-50-rollout)
6. [Phase 3: 100% Rollout](#phase-3-100-rollout)
7. [Monitoring & Observability](#monitoring--observability)
8. [Go/No-Go Decision Criteria](#gono-go-decision-criteria)
9. [Rollback Procedures](#rollback-procedures)
10. [Troubleshooting](#troubleshooting)
11. [Post-Rollout Tasks](#post-rollout-tasks)

---

## Overview

### What is Event-Driven Architecture?

Event-Driven Architecture for CommandCenter1C replaces synchronous HTTP operations with asynchronous event-based processing using Redis streams, enabling:

- **41.6x throughput improvement** (93 ops/s → 3,867 ops/s)
- **Parallel processing** of 700+ databases
- **Saga pattern** with automatic compensation
- **Circuit breaker** for resilience
- **Better scalability** and observability

### Rollout Philosophy

**Phased rollout** minimizes risk by gradually introducing Event-Driven mode:
- Start small (10%), validate, then scale
- Continuous monitoring with automatic rollback
- Go/No-Go decision gates between phases
- Always safe to rollback

### Timeline

| Phase | Traffic | Duration | Total Time |
|-------|---------|----------|------------|
| Phase 1 | 10% | ~4.5 hours | 4.5h |
| Phase 2 | 50% | ~4.5 hours | 9h |
| Phase 3 | 100% | ~1 hour | 10h |

**Total:** ~10 hours from 0% to 100%

---

## Rollout Strategy

### Three-Phase Approach

```
Phase 1: 10% Rollout  →  4h monitoring  →  Go/No-Go
    ↓ (if GO)
Phase 2: 50% Rollout  →  4h monitoring  →  Go/No-Go
    ↓ (if GO)
Phase 3: 100% Rollout  →  24h monitoring  →  SUCCESS! 🎉
```

### Phase 1: 10% Rollout

**Goal:** Validate Event-Driven in production with minimal risk

**Configuration:**
- `ENABLE_EVENT_DRIVEN=true`
- `EVENT_DRIVEN_ROLLOUT_PERCENT=0.10`

**Traffic Split:**
- 10% → Event-Driven mode
- 90% → HTTP Sync mode (fallback)

**Monitoring:**
- 4 hours intensive monitoring
- Automated health checks every 60 seconds
- Auto-rollback on failure (3 consecutive failures)

**Success Criteria:**
- Success rate ≥ 95%
- P99 latency < 1s
- Compensation rate < 10%
- No circuit breaker trips
- Redis healthy

### Phase 2: 50% Rollout

**Goal:** Scale to majority traffic, continue validation

**Prerequisites:**
- Phase 1 success criteria met
- Manual Go/No-Go decision

**Configuration:**
- `ENABLE_EVENT_DRIVEN=true`
- `EVENT_DRIVEN_ROLLOUT_PERCENT=0.50`

**Traffic Split:**
- 50% → Event-Driven mode
- 50% → HTTP Sync mode (fallback)

**Monitoring:**
- Same as Phase 1 (4 hours)

**Success Criteria:**
- Same as Phase 1

### Phase 3: 100% Rollout

**Goal:** Full deployment, retire HTTP Sync fallback

**Prerequisites:**
- Phase 2 success criteria met
- Manual Go/No-Go decision

**Configuration:**
- `ENABLE_EVENT_DRIVEN=true`
- `EVENT_DRIVEN_ROLLOUT_PERCENT=1.0`

**Traffic Split:**
- 100% → Event-Driven mode

**Monitoring:**
- 24 hours continuous monitoring
- Can be interrupted if stable

**Result:**
- Full Event-Driven deployment 🎉

---

## Pre-Rollout Checklist

### Before Starting Phase 1

Run automated pre-flight checks:

```bash
cd /c/1CProject/command-center-1c
./scripts/rollout/preflight-checks.sh
```

**Manual Checklist:**

- [ ] All services running and healthy
  - [ ] Worker: http://localhost:9091/health
  - [ ] Orchestrator: http://localhost:8000/health
  - [ ] PostgreSQL: `docker exec postgres pg_isready`
  - [ ] Redis: `docker exec redis redis-cli ping`
  - [ ] Prometheus: http://localhost:9090/-/healthy
  - [ ] Grafana: http://localhost:3001

- [ ] Feature flags configured in `.env.local`
  - [ ] `ENABLE_EVENT_DRIVEN=false` (will be set to true by scripts)
  - [ ] `EVENT_DRIVEN_ROLLOUT_PERCENT=0.0` (will be updated by scripts)

- [ ] Monitoring setup
  - [ ] Prometheus collecting metrics
  - [ ] Grafana dashboard accessible: http://localhost:3001/d/ab-testing
  - [ ] Alert rules configured (optional)

- [ ] Rollback plan ready
  - [ ] Rollback script exists: `./scripts/rollback-event-driven.sh`
  - [ ] Rollback script tested

- [ ] Backup
  - [ ] `.env.local` backup created (automatic)

- [ ] Team communication
  - [ ] Notify team about rollout start
  - [ ] On-call engineer available
  - [ ] Rollback contact ready

---

## Phase 1: 10% Rollout

### Execution

```bash
cd /c/1CProject/command-center-1c
./scripts/rollout/phase1.sh
```

### What Happens

1. **Pre-flight checks** (automated)
   - Services health
   - Feature flags config
   - Metrics collection
   - Rollback script availability

2. **User confirmation**
   - Manual approval required

3. **Configuration update**
   - `ENABLE_EVENT_DRIVEN=true`
   - `EVENT_DRIVEN_ROLLOUT_PERCENT=0.10`
   - Backup created automatically

4. **Worker restart**
   - Graceful restart with new config
   - Health check after restart

5. **Monitoring period (4 hours)**
   - Automated health checks every 60s
   - Auto-rollback on 3 consecutive failures
   - Metrics tracked:
     - Success rate
     - P99 latency
     - Compensation rate
     - Circuit breaker trips

6. **Go/No-Go decision**
   - Review dashboard
   - Run: `./scripts/rollout/check-metrics.sh --phase=1`

### Manual Monitoring

**Dashboard:** http://localhost:3001/d/ab-testing

**Key Metrics to Watch:**

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Success Rate | ≥ 95% | < 95% |
| P99 Latency | < 1s | ≥ 1s |
| Compensation Rate | < 10% | ≥ 10% |
| Circuit Breaker Trips | 0 | > 0 |

**PromQL Queries:**

```promql
# Success Rate (5min window)
rate(worker_execution_success_total{mode="event_driven"}[5m]) /
rate(worker_execution_mode_total{mode="event_driven"}[5m])

# P99 Latency
histogram_quantile(0.99,
  rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m])
)

# Compensation Rate
rate(worker_compensation_executed_total[5m]) /
rate(worker_execution_mode_total{mode="event_driven"}[5m])

# Circuit Breaker Trips
increase(worker_circuit_breaker_trips_total{mode="event_driven"}[1h])
```

### Success Criteria

All criteria must be met:

- ✅ Success rate ≥ 95%
- ✅ P99 latency < 1s
- ✅ Compensation rate < 10%
- ✅ No circuit breaker trips
- ✅ Redis healthy

### Next Steps

If **GO:**
```bash
./scripts/rollout/phase2.sh
```

If **NO-GO:**
```bash
./scripts/rollback-event-driven.sh
```

---

## Phase 2: 50% Rollout

### Prerequisites

Validate Phase 1 success:

```bash
./scripts/rollout/check-metrics.sh --phase=1
```

Expected output:
```
✅ Phase 1: GO for next phase!
```

### Execution

```bash
cd /c/1CProject/command-center-1c
./scripts/rollout/phase2.sh
```

### What Happens

1. **Pre-flight checks**
2. **Phase 1 validation** (automated)
3. **User confirmation**
4. **Configuration update** (50%)
5. **Worker restart**
6. **Monitoring period (4 hours)**
7. **Go/No-Go decision**

### Monitoring

Same as Phase 1, but with higher traffic volume:
- 50% of operations using Event-Driven
- Monitor for degradation at scale

### Success Criteria

Same as Phase 1

### Next Steps

If **GO:**
```bash
./scripts/rollout/phase3.sh
```

If **NO-GO:**
```bash
./scripts/rollback-event-driven.sh
```

---

## Phase 3: 100% Rollout

### Prerequisites

Validate Phase 2 success:

```bash
./scripts/rollout/check-metrics.sh --phase=2
```

### Execution

```bash
cd /c/1CProject/command-center-1c
./scripts/rollout/phase3.sh
```

### What Happens

1. **Pre-flight checks**
2. **Phase 2 validation** (automated)
3. **User confirmation** (FINAL!)
4. **Configuration update** (100%)
5. **Worker restart**
6. **Monitoring period (24 hours)**
7. **SUCCESS! 🎉**

### Monitoring

- 24 hours continuous monitoring (recommended)
- Can be interrupted if stable (Ctrl+C)
- Continue manual monitoring via dashboard

### Success

When complete, you'll see:

```
🎉🎉🎉 Event-Driven Architecture Fully Deployed! 🎉🎉🎉

100% of traffic is now using Event-Driven mode
```

---

## Monitoring & Observability

### Dashboards

**A/B Testing Dashboard:**
- URL: http://localhost:3001/d/ab-testing
- Panels:
  - Execution Mode Distribution (pie chart)
  - Success Rate by Mode (gauge)
  - P99 Latency by Mode (graph)
  - Compensation Rate (graph)
  - Circuit Breaker Trips (counter)
  - Queue Depth (graph)

**Prometheus:**
- URL: http://localhost:9090
- Explore metrics: `worker_*`

### Key Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `worker_execution_mode_total` | Counter | Executions by mode (event_driven, http_sync) |
| `worker_execution_success_total` | Counter | Successful executions by mode |
| `worker_execution_failure_total` | Counter | Failed executions by mode |
| `worker_execution_duration_seconds` | Histogram | Execution time by mode |
| `worker_compensation_executed_total` | Counter | Compensation actions (saga rollback) |
| `worker_circuit_breaker_trips_total` | Counter | Circuit breaker activations |
| `worker_retry_attempts_total` | Counter | Retry attempts |
| `worker_queue_depth` | Gauge | Current queue depth |

### Alerts (Optional)

Create alert rules in `infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml`:

```yaml
groups:
  - name: event_driven_rollout
    interval: 30s
    rules:
      - alert: EventDrivenSuccessRateLow
        expr: |
          rate(worker_execution_success_total{mode="event_driven"}[5m]) /
          rate(worker_execution_mode_total{mode="event_driven"}[5m]) < 0.95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Event-Driven success rate below 95%"

      - alert: EventDrivenLatencyHigh
        expr: |
          histogram_quantile(0.99,
            rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m])
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Event-Driven P99 latency above 1s"

      - alert: CompensationRateHigh
        expr: |
          rate(worker_compensation_executed_total[5m]) /
          rate(worker_execution_mode_total{mode="event_driven"}[5m]) > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Compensation rate above 10%"
```

---

## Go/No-Go Decision Criteria

### Automated Check

```bash
./scripts/rollout/check-metrics.sh --phase=<1|2>
```

**Exit codes:**
- `0` = GO (all criteria met)
- `1` = NO-GO (one or more criteria failed)

### Manual Review

If automated check passes, manually review:

1. **Dashboard trends**
   - Stable metrics over time
   - No sudden spikes/drops
   - Consistent success rate

2. **Error logs**
   - No new error patterns
   - Compensation reasons acceptable

3. **Business impact**
   - User complaints
   - Operation success from business perspective

4. **Team consensus**
   - On-call engineer approval
   - Tech lead sign-off

### Decision Matrix

| Criteria | Weight | Pass Threshold | Action if Fail |
|----------|--------|----------------|----------------|
| Success Rate | CRITICAL | ≥ 95% | NO-GO → Rollback |
| P99 Latency | HIGH | < 1s | NO-GO → Investigate |
| Compensation Rate | MEDIUM | < 10% | Investigate → Consider NO-GO |
| Circuit Breaker | HIGH | 0 trips | Investigate → Consider NO-GO |
| Redis Health | CRITICAL | Healthy | NO-GO → Fix Redis |

**GO Decision:**
- All CRITICAL criteria pass
- HIGH criteria pass or have mitigation
- MEDIUM criteria pass or acceptable reason

**NO-GO Decision:**
- Any CRITICAL criterion fails
- Multiple HIGH criteria fail
- Trend degrading

---

## Rollback Procedures

### Automatic Rollback

Monitoring script (`monitor.sh`) automatically rolls back if:
- Success rate < 95% for 5 minutes (3 consecutive failures)
- Worker service unavailable
- P99 latency > 1s consistently

### Manual Rollback

Rollback at any time:

```bash
cd /c/1CProject/command-center-1c
./scripts/rollback-event-driven.sh
```

**What it does:**
1. Stops Worker service
2. Sets `ENABLE_EVENT_DRIVEN=false`
3. Restores backup configuration (optional)
4. Restarts Worker in HTTP Sync mode
5. Verifies Worker is healthy

**Time:** < 2 minutes

### Rollback Decision Factors

**Immediate rollback if:**
- Critical production incident
- Success rate < 90%
- P99 latency > 5s
- Redis unavailable
- Circuit breaker tripping constantly

**Consider rollback if:**
- Success rate < 95% for > 15 minutes
- Compensation rate > 20%
- Unexpected errors in logs
- Business impact reported

### After Rollback

1. Preserve metrics data (don't restart Prometheus)
2. Export logs for analysis
3. Review dashboard for patterns
4. Identify root cause
5. Fix issue
6. Re-test in staging
7. Schedule new rollout attempt

---

## Troubleshooting

### Issue: Pre-flight checks fail

**Symptom:** `./scripts/rollout/preflight-checks.sh` returns errors

**Solutions:**

1. **Services not healthy**
   ```bash
   # Check all services
   ./scripts/dev/health-check.sh

   # Restart failed services
   ./scripts/dev/restart.sh <service-name>
   ```

2. **Feature flags not configured**
   ```bash
   # Add to .env.local
   echo "ENABLE_EVENT_DRIVEN=false" >> .env.local
   echo "EVENT_DRIVEN_ROLLOUT_PERCENT=0.0" >> .env.local
   ```

3. **Prometheus not responding**
   ```bash
   # Check Prometheus
   docker ps | grep prometheus
   curl http://localhost:9090/-/healthy
   ```

### Issue: Rollout fails during deployment

**Symptom:** Worker restart fails, rollback triggered

**Solutions:**

1. **Check Worker logs**
   ```bash
   ./scripts/dev/logs.sh worker
   ```

2. **Check Redis connection**
   ```bash
   docker exec redis redis-cli ping
   ```

3. **Verify configuration**
   ```bash
   cat .env.local | grep EVENT_DRIVEN
   ```

### Issue: Success rate below 95%

**Symptom:** Metrics check fails, NO-GO decision

**Possible causes:**

1. **Redis performance issues**
   - Check Redis CPU/memory
   - Monitor queue depth
   - Check for slow commands

2. **Worker overload**
   - Check Worker CPU/memory
   - Increase worker pool size
   - Scale horizontally (add replicas)

3. **Network issues**
   - Check latency to 1C databases
   - Monitor connection errors

4. **Business logic errors**
   - Check compensation logs
   - Review error patterns
   - Fix bugs in event handlers

### Issue: P99 latency > 1s

**Symptom:** Latency too high for comfort

**Solutions:**

1. **Profile slow operations**
   - Check Prometheus latency buckets
   - Identify slow databases
   - Optimize queries

2. **Increase concurrency**
   - Tune `EVENT_DRIVEN_MAX_CONCURRENT`
   - Scale Worker replicas

3. **Database issues**
   - Check 1C database health
   - Monitor OData response times
   - Investigate lock contention

### Issue: Compensation rate > 10%

**Symptom:** High saga rollback rate

**Causes:**

1. **Lock acquisition failures**
   - Increase lock timeout
   - Optimize lock strategy
   - Reduce contention

2. **Transient errors**
   - Increase retry count
   - Add exponential backoff
   - Improve error handling

3. **Configuration issues**
   - Validate 1C credentials
   - Check database accessibility

---

## Post-Rollout Tasks

### Immediate (Day 1)

- [ ] Monitor dashboard for 24 hours
- [ ] Review final metrics vs baseline
- [ ] Document any issues encountered
- [ ] Notify team of successful rollout

### Short-term (Week 1)

- [ ] Collect performance data
- [ ] Analyze cost savings
- [ ] Measure business impact
- [ ] Update runbooks

### Mid-term (Month 1)

- [ ] Plan removal of HTTP Sync fallback code
- [ ] Optimize Event-Driven performance
- [ ] Scale out Worker replicas if needed
- [ ] Review circuit breaker thresholds

### Long-term (Quarter 1)

- [ ] Remove feature flags (100% rollout permanent)
- [ ] Deprecate HTTP Sync mode
- [ ] Plan Phase 2 features (if any)
- [ ] Knowledge sharing session

---

## Appendix

### A. Script Reference

| Script | Purpose | Duration |
|--------|---------|----------|
| `preflight-checks.sh` | Pre-deployment validation | < 1 min |
| `phase1.sh` | 10% rollout + monitoring | ~4.5 hours |
| `phase2.sh` | 50% rollout + monitoring | ~4.5 hours |
| `phase3.sh` | 100% rollout + monitoring | ~1 hour |
| `monitor.sh` | Automated monitoring | Configurable |
| `check-metrics.sh` | Go/No-Go decision | < 30 seconds |
| `rollback-event-driven.sh` | Rollback to HTTP Sync | < 2 minutes |

### B. Configuration Reference

**Environment Variables:**

```bash
# Feature Flags
ENABLE_EVENT_DRIVEN=true|false
EVENT_DRIVEN_ROLLOUT_PERCENT=0.0-1.0

# Targeting (optional)
EVENT_DRIVEN_TARGET_DBS=db1,db2,db3
EVENT_DRIVEN_EXTENSIONS=true
EVENT_DRIVEN_BACKUPS=false

# Safety
EVENT_DRIVEN_MAX_CONCURRENT=100
EVENT_DRIVEN_CB_THRESHOLD=0.95

# A/B Testing
EVENT_DRIVEN_EXPERIMENT_ID=rollout-2025-11
```

### C. Contact Information

**On-Call Engineer:**
- [Name/Contact]

**Tech Lead:**
- [Name/Contact]

**Escalation:**
- [Manager/Contact]

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Next Review:** 2025-12-18
