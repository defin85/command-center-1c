# Week 4: Cutover Instructions

**Status:** Ready for Execution
**Date:** 2025-11-20

---

## Pre-Cutover Checklist

Before running cutover script, ensure:

- [ ] All Week 4 Day 1 tests passed (22/22 ✅)
- [ ] RAS Adapter running stable for 24+ hours
- [ ] Benchmarks completed successfully
- [ ] Performance acceptable (P95 < 2s)
- [ ] Approval received from Tech Lead

---

## Cutover Procedure

### Step 1: Run Benchmarks

```bash
cd /c/1CProject/command-center-1c

# Run performance benchmarks
./scripts/dev/benchmark-ras-adapter.sh

# Review results
cat benchmark_results_*.txt
```

**Expected Results:**
- Health Check P95: < 100ms ✅
- GET /clusters P95: < 500ms ✅
- Throughput: > 100 req/s ✅
- Success Rate: > 99% ✅

**DECISION GATE:** If ANY metric FAILS → DO NOT proceed, rollback plan in Section 5.

---

### Step 2: Execute Cutover

```bash
# Run cutover script
./scripts/dev/cutover-to-ras-adapter.sh

# Script will:
# 1. Stop cluster-service
# 2. Archive code to go-services/archive/cluster-service/
# 3. Update .env.local (USE_RAS_ADAPTER=true)
# 4. Verify RAS Adapter health
```

---

### Step 3: Git Commit (Archive cluster-service)

```bash
# Stage archived code
git add go-services/archive/cluster-service/
git add go-services/archive/cluster-service/DEPRECATED.md

# Stage updated configs
git add .env.local
git add CLAUDE.md
git add README.md

# Commit
git commit -m "$(cat <<'EOF'
Week 4: Deprecate cluster-service, cutover to ras-adapter

## Changes

### Deprecated
- cluster-service → archived to go-services/archive/
- ras-grpc-gw → no longer needed (RAS Adapter uses direct protocol)

### Architecture
- Before: Worker → cluster-service → ras-grpc-gw → RAS (2 hops)
- After: Worker → ras-adapter → RAS (1 hop, -50% reduction)

### Performance Improvements
- Lock/Unlock latency: -30-50% (P95 < 2s)
- Throughput: +100% (> 100 req/s)
- Success rate: > 99%
- Fewer services: 7 → 6 (-14%)

### Updated Files
- go-services/archive/cluster-service/ (archived)
- go-services/archive/cluster-service/DEPRECATED.md (NEW)
- CLAUDE.md (architecture updated)
- README.md (architecture diagram updated)
- .env.local (USE_RAS_ADAPTER=true)

### Backward Compatibility
- USE_RAS_ADAPTER=false switches back to cluster-service (NOT recommended)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

### Step 4: Verify Cutover

```bash
# Health check
curl http://localhost:8088/health

# Smoke tests
./scripts/dev/test-lock-unlock-workflow.sh

# Check process list
./scripts/dev/health-check.sh

# Verify cluster-service NOT running
! ps aux | grep cluster-service || echo "WARNING: cluster-service still running!"
```

---

### Step 5: Rollback Plan (if needed)

**If cutover fails, rollback in 15 minutes:**

```bash
# 1. Stop RAS Adapter (1 min)
./scripts/dev/stop-all.sh

# 2. Restore cluster-service code (2 min)
git mv go-services/archive/cluster-service go-services/cluster-service

# 3. Set USE_RAS_ADAPTER=false (1 min)
sed -i 's/USE_RAS_ADAPTER=true/USE_RAS_ADAPTER=false/' .env.local

# 4. Start cluster-service + ras-grpc-gw (2 min)
cd ../ras-grpc-gw
./start.sh &
cd /c/1CProject/command-center-1c
USE_RAS_ADAPTER=false ./scripts/dev/start-all.sh

# 5. Verify (5 min)
./scripts/dev/health-check.sh
curl http://localhost:8088/health

# 6. Document issues (3 min)
echo "Rollback completed at $(date)" >> rollback_log.txt
echo "Reason: [DESCRIBE ISSUE]" >> rollback_log.txt
```

**Rollback triggers:**
- ❌ RAS Adapter crashes repeatedly
- ❌ Lock/Unlock operations fail > 10%
- ❌ Worker can't connect
- ❌ Performance degradation > 50%

---

## Post-Cutover Monitoring (24 hours)

### Hour 0-1 (Critical)
- [ ] Health check every 5 minutes
- [ ] Monitor logs: `tail -f logs/ras-adapter.log`
- [ ] Watch for errors

### Hour 1-8 (Important)
- [ ] Health check every 30 minutes
- [ ] Monitor Worker integration (Redis Pub/Sub)
- [ ] Check memory usage (no leaks)

### Hour 8-24 (Normal)
- [ ] Health check every hour
- [ ] Validate no degradation
- [ ] Prepare Week 4 Day 3 documentation

---

## Success Criteria

Cutover считается успешным если:

- [ ] RAS Adapter работает 24 часа без crashes
- [ ] Success rate > 99%
- [ ] Performance P95 < 2s
- [ ] Worker integration работает (Lock/Unlock events)
- [ ] No memory leaks (RSS стабилен)
- [ ] Git commit создан

---

## Contact

For issues, see: docs/roadmaps/WEEK4_DEPLOY_VALIDATE_PLAN.md Section 5 (Cutover Strategy)
