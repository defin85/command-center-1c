# Week 4: Deploy & Validate - Executive Summary

**Date:** 2025-11-20
**Status:** ✅ READY FOR EXECUTION
**Timeline:** 2-3 days (11 hours effort)
**Risk Level:** 🟢 LOW

---

## TL;DR (60 seconds)

**Goal:** Deploy RAS Adapter to development, validate performance, deprecate cluster-service + ras-grpc-gw.

**Strategy:**
- ✅ Deploy on **host** (not Docker) - consistent with current dev workflow
- ✅ **Zero Worker changes** - same Redis Pub/Sub channels
- ✅ **Comprehensive validation** - 8 critical smoke tests + performance benchmarks
- ✅ **Rollback ready** - cluster-service binary available, 15-minute rollback

**Expected Results:**
- 📉 Network hops: **2 → 1** (-50%)
- 📉 Services count: **7 → 6** (-14%)
- 📉 Latency P95: **30-50% reduction** (one less hop)
- 📈 Throughput: **> 100 ops/min**

---

## Current Situation

**RAS Adapter Status (Week 3 completion):**
- ✅ Real RAS protocol integrated (khorevaa/ras-client)
- ✅ Binary stable: `bin/cc1c-ras-adapter.exe` (39MB)
- ✅ Integration tests: 37+ scenarios, 1,888 lines
- ✅ Score: 94/100 (no critical blockers)
- 🟡 **Not yet deployed** to development environment

**Old Architecture (to be deprecated):**
```
Worker → Redis → cluster-service (8088) → ras-grpc-gw (9999) → RAS (1545)
                      ↓ gRPC                  ↓ RAS binary
                 (2 network hops)
```

**New Architecture (RAS Adapter):**
```
Worker → Redis → ras-adapter (8088) → RAS (1545)
                      ↓ khorevaa/ras-client (direct)
                 (1 network hop)
```

---

## Key Decisions

### 1. Deployment Strategy: Host-based (Hybrid Mode)

**Decision:** Deploy ras-adapter on host (NOT Docker)

**Rationale:**
- ✅ Consistent with current dev workflow (all Go services run on host via `scripts/dev/start-all.sh`)
- ✅ Fast iteration cycle (build → restart, no Docker rebuild)
- ✅ Easy debugging (direct access to logs, process)
- ✅ Minimal infrastructure changes

**Implementation:**
- Update `scripts/dev/start-all.sh` to start ras-adapter on port 8088
- Use existing binary: `bin/cc1c-ras-adapter.exe`
- Load config from `.env.local` (same as other services)

### 2. Cutover Strategy: Single Service Deployment

**Decision:** Stop cluster-service, deploy ras-adapter (NO parallel deployment)

**Rationale:**
- ✅ Worker uses **same Redis channels** → no code changes needed
- ✅ Avoids duplicate event issues (both services subscribing to same channel)
- ✅ Simpler testing (one service to validate)
- ⚠️ If issues found → rollback to cluster-service (15 min)

**Alternative considered:** Parallel deployment (both services on different ports)
- ❌ Rejected: complexity, duplicate events, no real benefit

### 3. Validation Approach: 8 Critical Tests

**Decision:** Run 8 critical smoke tests before cutover

**Tests:**
1. Health check (REST API)
2. GET /clusters (RAS connection)
3. GET /infobases (infobase enumeration)
4. POST /lock (REST API)
5. POST /unlock (REST API)
6. Redis Pub/Sub Lock (event handler)
7. Redis Pub/Sub Unlock (event handler)
8. End-to-End workflow (Lock → Verify → Unlock)

**Gate condition:** ALL 8 tests must PASS before cutover.

---

## Timeline & Milestones

**Total effort:** 11 hours
**Total calendar time:** 3 days (with 24-hour stability monitoring)

### Day 1: Deployment & Smoke Tests (4 hours)

**Morning (2h):**
- Build ras-adapter binary (10 min)
- Update scripts (start-all.sh, stop-all.sh, restart-all.sh) (50 min)
- Deploy ras-adapter to host (10 min)
- Test restart cycle (10 min)

**Afternoon (2h):**
- Run smoke tests 1-9 (2h)
- Document test results (10 min)

**Deliverable:** ✅ RAS Adapter deployed, all smoke tests PASSED

### Day 2: Performance Validation & Cutover (4 hours)

**Morning (2h):**
- Run baseline benchmarks (cluster-service) (30 min)
- Switch to ras-adapter (10 min)
- Run new benchmarks (ras-adapter) (30 min)
- Compare results (15 min)
- Load testing (Apache Bench) (20 min)

**Afternoon (2h):**
- Document performance comparison (30 min)
- Setup 24-hour stability monitoring (20 min)
- **DECISION GATE:** Cutover or Rollback? (10 min)
- Execute cutover (30 min)

**Deliverable:** ✅ Performance validated, cutover complete OR blockers documented

### Day 3: Documentation & Final Validation (3 hours)

**Morning (2h):**
- Update CLAUDE.md, README.md, roadmap (1h)
- Create deployment guide (40 min)
- Git commit: archive cluster-service (15 min)

**Afternoon (1h):**
- Final smoke test (after 24h stability) (20 min)
- Sign-off validation checklist (10 min)
- Create handover document (20 min)

**Deliverable:** ✅ All docs updated, Week 4 COMPLETE

---

## Success Criteria

**Week 4 is successful if ALL of the following are met:**

### Functional Requirements
- [ ] RAS Adapter deployed to development
- [ ] All 8 smoke tests PASSED
- [ ] REST API works (GET /clusters, /infobases, POST /lock, /unlock)
- [ ] Redis Pub/Sub works (Lock, Unlock event handlers)
- [ ] End-to-End workflow works

### Performance Requirements
- [ ] Lock/Unlock Latency P95 < 2s
- [ ] Success rate > 99% (100 requests)
- [ ] Throughput > 100 ops/min
- [ ] Performance improvement vs cluster-service (30-50% expected)

### Stability Requirements
- [ ] RAS Adapter runs for 24 hours without crashes
- [ ] No memory leaks (RSS stable)
- [ ] No error rate spikes

### Integration Requirements
- [ ] Worker publishes commands successfully
- [ ] Worker receives events successfully
- [ ] Zero Worker code changes needed

### Deprecation Requirements
- [ ] cluster-service stopped and archived
- [ ] ras-grpc-gw stopped (no longer needed)
- [ ] Services count reduced (7 → 6)

### Documentation Requirements
- [ ] CLAUDE.md updated
- [ ] Deployment guide created
- [ ] Scripts updated
- [ ] Rollback procedure documented

**GATE CONDITION for Week 5:** ALL criteria must be met.

---

## Risks & Mitigation

### Top 3 Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **RAS Adapter crashes** | LOW | HIGH | - 37+ integration tests<br>- 24h stability monitoring<br>- Rollback plan ready (15 min) |
| **Performance regression** | LOW | MEDIUM | - Benchmark comparison<br>- Load testing (100+ requests)<br>- P95 < 2s validation |
| **Worker integration issues** | LOW | HIGH | - Same Redis channels<br>- No code changes<br>- Integration tests cover flow |

**Overall Risk Level:** 🟢 **LOW**

**Reason:** Comprehensive testing (Week 3), clear rollback plan, zero Worker changes.

---

## Expected Results

### Before (OLD architecture)

```
┌────────┐
│ Worker │
└───┬────┘
    │ Redis Pub/Sub
    ▼
┌─────────────────┐
│ cluster-service │ (Go, port 8088)
└───┬─────────────┘
    │ gRPC
    ▼
┌─────────────┐
│ ras-grpc-gw │ (Go, port 9999)
└───┬─────────┘
    │ RAS binary protocol
    ▼
┌─────────────┐
│  1C RAS     │ (port 1545)
└─────────────┘

Network hops: 2
Services: 7 total
Latency P95: ~2-3s (estimated)
Complexity: High (3 services in chain)
```

### After (NEW architecture)

```
┌────────┐
│ Worker │
└───┬────┘
    │ Redis Pub/Sub
    ▼
┌─────────────┐
│ ras-adapter │ (Go, port 8088)
└───┬─────────┘
    │ khorevaa/ras-client (direct)
    ▼
┌─────────────┐
│  1C RAS     │ (port 1545)
└─────────────┘

Network hops: 1 (-50%)
Services: 6 total (-14%)
Latency P95: < 2s (30-50% improvement expected)
Complexity: Low (direct connection)
```

### Performance Improvements (Expected)

| Metric | OLD | NEW | Improvement |
|--------|-----|-----|-------------|
| Network Hops | 2 | 1 | -50% |
| Services Count | 7 | 6 | -14% |
| Lock Latency P95 | ~2-3s | < 2s | -30-50% |
| Throughput | ~50 ops/min | > 100 ops/min | +100% |
| Maintenance Overhead | High (3 services) | Low (1 service) | -67% |

---

## Rollback Plan

**If cutover FAILS → rollback in 15 minutes:**

1. Stop RAS Adapter (1 min)
2. Restore cluster-service binary (2 min)
3. Start ras-grpc-gw (2 min)
4. Restart Worker (2 min)
5. Verify rollback (5 min)
6. Document issues (3 min)

**Rollback triggers:**
- ❌ RAS Adapter crashes repeatedly
- ❌ Lock/Unlock operations fail > 10%
- ❌ Worker cannot connect
- ❌ Performance degradation > 50%

**Rollback decision:** Tech Lead or Senior Developer

---

## Next Steps After Week 4

1. **Week 4.5: Manual Testing Gate** (CRITICAL)
   - Comprehensive manual validation
   - ALL REST endpoints tested
   - ALL event handlers tested
   - Sign-off required

2. **Week 5: Terminate Sessions** (if needed)
   - Implement NEW Terminate Sessions (ISessionBase.Close)
   - Replace AdminSession.Terminate
   - Integration with Worker

3. **Production Deployment** (future)
   - Kubernetes manifests
   - CI/CD pipeline
   - Production monitoring

---

## Quick Start Commands

```bash
# ========================================
# Week 4 Deployment - Quick Commands
# ========================================

# 1. Build RAS Adapter
cd go-services/ras-adapter
go build -o ../../bin/cc1c-ras-adapter.exe cmd/main.go

# 2. Verify binary
../../bin/cc1c-ras-adapter.exe --version

# 3. Stop all services
./scripts/dev/stop-all.sh

# 4. Start all services (includes ras-adapter)
./scripts/dev/start-all.sh

# 5. Health check
curl http://localhost:8088/health

# 6. Run smoke tests
./test-lock-unlock-workflow.sh

# 7. View logs
tail -f logs/ras-adapter.log

# 8. Rollback (if needed)
./scripts/dev/stop-all.sh
# Restore cluster-service manually
# See: docs/roadmaps/WEEK4_DEPLOY_VALIDATE_PLAN.md Section 5.3
```

---

## Documentation

**Full Plan:** [WEEK4_DEPLOY_VALIDATE_PLAN.md](./WEEK4_DEPLOY_VALIDATE_PLAN.md)

**Sections:**
- Section 1: Deployment Strategy (Host-based, scripts updates)
- Section 2: Parallel Deployment (OPTIONAL, not recommended)
- Section 3: Smoke Testing Strategy (8 critical tests)
- Section 4: Performance Comparison (benchmarks, load testing)
- Section 5: Cutover Strategy (validation checklist, deprecation steps, rollback)
- Section 6: Documentation Updates (CLAUDE.md, README.md, etc.)
- Section 7: Task Breakdown (Day 1-3, timeline)
- Section 8: Risks & Mitigation (technical, operational, schedule)

**Appendices:**
- Appendix A: Environment Variables Reference
- Appendix B: Quick Reference Commands

---

## Sign-off

**Architect:** _________________________
**Date:** _________________________
**Status:** [ ] ✅ APPROVED   [ ] ⚠️ NEEDS REVISION   [ ] ❌ REJECTED

**Comments:**
_________________________________________
_________________________________________

---

**End of Executive Summary**

**Version:** 1.0
**Date:** 2025-11-20
**Status:** ✅ READY FOR REVIEW
