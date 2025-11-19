# Production Rollout Scripts

Quick start guide for Event-Driven Architecture phased rollout.

---

## Quick Start

### Phase 1: 10% Rollout

```bash
cd /c/1CProject/command-center-1c
./scripts/rollout/phase1.sh
```

**Duration:** ~4.5 hours (10% traffic + 4h monitoring)

### Phase 2: 50% Rollout

```bash
./scripts/rollout/phase2.sh
```

**Duration:** ~4.5 hours (50% traffic + 4h monitoring)

### Phase 3: 100% Rollout

```bash
./scripts/rollout/phase3.sh
```

**Duration:** ~1 hour (100% traffic + 24h monitoring)

---

## Scripts Overview

| Script | Purpose | Duration | Output |
|--------|---------|----------|--------|
| `phase1.sh` | 10% rollout + monitoring | ~4.5h | GO/NO-GO decision |
| `phase2.sh` | 50% rollout + monitoring | ~4.5h | GO/NO-GO decision |
| `phase3.sh` | 100% rollout + monitoring | ~1h | SUCCESS! 🎉 |
| `preflight-checks.sh` | Pre-deployment validation | < 1min | PASS/FAIL |
| `monitor.sh` | Automated monitoring | configurable | Health status |
| `check-metrics.sh` | Go/No-Go decision | < 30s | GO/NO-GO |
| `common-functions.sh` | Shared utilities | N/A | Library |

---

## Pre-Rollout Checklist

Before starting Phase 1, ensure:

```bash
# 1. Run pre-flight checks
./scripts/rollout/preflight-checks.sh

# 2. Check all services are healthy
./scripts/dev/health-check.sh

# 3. Verify monitoring is working
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3001            # Grafana
```

**Manual checks:**
- [ ] `.env.local` configured
- [ ] Rollback script tested: `./scripts/rollback-event-driven.sh --dry-run`
- [ ] Team notified
- [ ] On-call engineer available
- [ ] Dashboard accessible: http://localhost:3001/d/ab-testing

---

## Rollout Process

### Step-by-Step

```
1. Pre-flight checks → ./scripts/rollout/preflight-checks.sh
   ✓ Services healthy
   ✓ Configuration ready
   ✓ Monitoring working

2. Phase 1 (10%) → ./scripts/rollout/phase1.sh
   ✓ Deploy 10% traffic
   ✓ Monitor 4 hours
   ✓ Check metrics → ./scripts/rollout/check-metrics.sh --phase=1

3. Phase 2 (50%) → ./scripts/rollout/phase2.sh
   ✓ Deploy 50% traffic
   ✓ Monitor 4 hours
   ✓ Check metrics → ./scripts/rollout/check-metrics.sh --phase=2

4. Phase 3 (100%) → ./scripts/rollout/phase3.sh
   ✓ Deploy 100% traffic
   ✓ Monitor 24 hours
   ✓ SUCCESS! 🎉
```

### Timeline

```
Hour 0     → Phase 1 start (10%)
Hour 4.5   → Phase 1 complete, Go/No-Go decision
Hour 4.5   → Phase 2 start (50%)
Hour 9     → Phase 2 complete, Go/No-Go decision
Hour 9     → Phase 3 start (100%)
Hour 10    → Phase 3 deployed (continuous monitoring)
```

**Total:** ~10 hours from 0% to 100%

---

## Monitoring

### Dashboards

- **A/B Testing:** http://localhost:3001/d/ab-testing
- **Prometheus:** http://localhost:9090

### Key Metrics

| Metric | Target | Alert |
|--------|--------|-------|
| Success Rate | ≥ 95% | < 95% |
| P99 Latency | < 1s | ≥ 1s |
| Compensation Rate | < 10% | ≥ 10% |
| Circuit Breaker | 0 trips | > 0 |

### Automated Monitoring

Each phase script includes automated monitoring:

```bash
# Automatic monitoring with auto-rollback
./scripts/rollout/monitor.sh --duration=4h --threshold=0.95 --auto-rollback

# Custom monitoring
./scripts/rollout/monitor.sh --duration=2h --check-interval=30 --max-failures=5
```

**Options:**
- `--duration=DURATION` - Monitoring duration (4h, 30m, 1d, continuous)
- `--threshold=FLOAT` - Success rate threshold (0.0-1.0, default: 0.95)
- `--auto-rollback` - Enable automatic rollback on failure
- `--check-interval=SECONDS` - Time between checks (default: 60)
- `--max-failures=COUNT` - Max consecutive failures before rollback (default: 3)

---

## Go/No-Go Decision

### Automated Check

```bash
# Check Phase 1 metrics
./scripts/rollout/check-metrics.sh --phase=1

# Check Phase 2 metrics
./scripts/rollout/check-metrics.sh --phase=2

# Custom lookback window
./scripts/rollout/check-metrics.sh --phase=1 --lookback=2h
```

**Exit codes:**
- `0` = GO (all criteria met)
- `1` = NO-GO (one or more criteria failed)

### Manual Review

1. Open dashboard: http://localhost:3001/d/ab-testing
2. Check trends:
   - Success rate stable ≥ 95%
   - P99 latency < 1s
   - No sudden spikes/drops
3. Review error logs:
   - `./scripts/dev/logs.sh worker`
4. Team consensus

### Decision Matrix

**GO if:**
- ✅ Success rate ≥ 95%
- ✅ P99 latency < 1s
- ✅ Compensation rate < 10%
- ✅ No circuit breaker trips
- ✅ Redis healthy
- ✅ No critical errors

**NO-GO if:**
- ❌ Success rate < 95% for > 5 minutes
- ❌ P99 latency > 1s consistently
- ❌ Compensation rate > 10%
- ❌ Circuit breaker tripping
- ❌ Critical errors in logs

---

## Rollback

### Automatic Rollback

Monitoring script automatically rolls back if:
- Success rate < 95% for 5 minutes (3 consecutive failures)
- Worker unavailable
- Critical metrics degraded

### Manual Rollback

Rollback at any time:

```bash
./scripts/rollback-event-driven.sh
```

**What it does:**
1. Stops Worker
2. Sets `ENABLE_EVENT_DRIVEN=false`
3. Restarts Worker in HTTP Sync mode
4. Verifies health

**Time:** < 2 minutes

### When to Rollback

**Immediate rollback:**
- Critical production incident
- Success rate < 90%
- P99 latency > 5s
- Redis unavailable

**Consider rollback:**
- Success rate < 95% for > 15 minutes
- Compensation rate > 20%
- Unexpected errors
- Business impact reported

---

## Troubleshooting

### Pre-flight checks fail

```bash
# Check services
./scripts/dev/health-check.sh

# Restart failed service
./scripts/dev/restart.sh <service>

# View logs
./scripts/dev/logs.sh <service>
```

### Rollout fails during deployment

```bash
# Check Worker logs
./scripts/dev/logs.sh worker

# Check configuration
cat .env.local | grep EVENT_DRIVEN

# Manual restart
./scripts/dev/restart.sh worker
```

### Success rate below 95%

1. Check Redis performance
   ```bash
   docker exec redis redis-cli INFO stats
   ```

2. Check Worker load
   ```bash
   ./scripts/dev/logs.sh worker | grep -i "error\|warn"
   ```

3. Review compensation logs
   ```bash
   # Query Prometheus
   curl 'http://localhost:9090/api/v1/query?query=worker_compensation_executed_total'
   ```

### High latency (P99 > 1s)

1. Profile slow operations
   - Check Prometheus latency buckets
   - Identify slow databases

2. Increase concurrency
   ```bash
   # In .env.local
   EVENT_DRIVEN_MAX_CONCURRENT=200
   ```

3. Scale horizontally
   - Add more Worker replicas

---

## Advanced Usage

### Dry Run (Testing)

Test scripts without making changes:

```bash
# Dry run mode (add to scripts if needed)
DRY_RUN=true ./scripts/rollout/phase1.sh
```

### Custom Rollout Percentage

Manually set custom percentage:

```bash
# Edit .env.local
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.25  # 25%

# Restart Worker
./scripts/dev/restart.sh worker
```

### Targeted Rollout

Enable Event-Driven for specific databases only:

```bash
# Edit .env.local
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
EVENT_DRIVEN_TARGET_DBS=db1,db2,db3

# Restart Worker
./scripts/dev/restart.sh worker
```

### Continuous Monitoring

Monitor indefinitely (manual stop):

```bash
./scripts/rollout/monitor.sh --duration=continuous --auto-rollback
```

**Stop:** Ctrl+C

---

## Configuration Reference

### Environment Variables

```bash
# Feature Flags
ENABLE_EVENT_DRIVEN=true|false
EVENT_DRIVEN_ROLLOUT_PERCENT=0.0-1.0  # 0% to 100%

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

### Example Configuration

**Phase 1 (10%):**
```bash
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.10
EVENT_DRIVEN_MAX_CONCURRENT=100
```

**Phase 2 (50%):**
```bash
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=0.50
EVENT_DRIVEN_MAX_CONCURRENT=100
```

**Phase 3 (100%):**
```bash
ENABLE_EVENT_DRIVEN=true
EVENT_DRIVEN_ROLLOUT_PERCENT=1.0
EVENT_DRIVEN_MAX_CONCURRENT=100
```

---

## Post-Rollout

After successful 100% rollout:

1. **Continue monitoring** (Week 1)
   - Dashboard: http://localhost:3001/d/ab-testing
   - Review daily

2. **Collect metrics** (Month 1)
   - Performance vs baseline
   - Cost savings
   - Business impact

3. **Plan cleanup** (Quarter 1)
   - Remove feature flags
   - Deprecate HTTP Sync fallback
   - Code cleanup

---

## Resources

**Documentation:**
- Comprehensive Guide: [docs/EVENT_DRIVEN_PRODUCTION_ROLLOUT.md](../../docs/EVENT_DRIVEN_PRODUCTION_ROLLOUT.md)
- Architecture: [docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md](../../docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md)
- Roadmap: [docs/EVENT_DRIVEN_ROADMAP.md](../../docs/EVENT_DRIVEN_ROADMAP.md)
- Rollback Plan: [scripts/rollback-event-driven.README.md](../rollback-event-driven.README.md)

**Monitoring:**
- A/B Testing Dashboard: http://localhost:3001/d/ab-testing
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

**Support:**
- On-Call Engineer: [Contact]
- Tech Lead: [Contact]
- Escalation: [Manager/Contact]

---

**Version:** 1.0
**Last Updated:** 2025-11-18
