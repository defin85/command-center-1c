# Architectural Decision Record: Event-Driven vs gRPC for RAS Adapter

**Status:** ✅ Accepted
**Date:** 2025-11-19
**Decision Makers:** AI Architect, AI Orchestrator
**Supersedes:** RAS_ADAPTER_ROADMAP v1.x (gRPC Hybrid Protocol Strategy)

---

## Context

During Phase 1 (Week 1-2), Event-Driven State Machine was implemented with Worker communicating to cluster-service via Redis Pub/Sub. When designing RAS Adapter (merger of cluster-service + ras-grpc-gw), we evaluated two architectural approaches:

1. **Hybrid Protocol (v1.x):** gRPC (Worker → RAS Adapter) + REST (external clients)
2. **Event-Driven ONLY (v2.0):** Redis Pub/Sub (Worker) + REST (external clients)

## Decision

✅ **We chose Event-Driven ONLY architecture (v2.0)**

RAS Adapter will:
- ✅ Implement Redis Pub/Sub event handlers (for Worker State Machine)
- ✅ Implement REST API (for external clients)
- ❌ NOT implement gRPC server (Worker will NOT make direct calls)

## Rationale

### 1. Event-Driven State Machine Already Works

**Implemented:** Week 1-2 (100% complete)
- Worker State Machine: 89 unit tests ✅
- cluster-service Event Handlers: 30 unit tests (81.2% coverage) ✅
- Integration tests: 5 tests (Redis event flow) ✅

**Verdict:** Why add gRPC when Redis Pub/Sub already works?

### 2. Loose Coupling

**Event-Driven (v2.0):**
- Worker publishes command → Redis
- RAS Adapter subscribes → Redis
- Worker and RAS Adapter don't know about each other

**gRPC (v1.x):**
- Worker calls RAS Adapter directly
- Tight coupling (Worker must know RAS Adapter address, port, proto definitions)
- Harder to scale (load balancing required)

**Verdict:** Event-Driven provides better decoupling

### 3. Simplicity

**Event-Driven (v2.0):**
- Copy event handlers from cluster-service → RAS Adapter
- No new protocols to learn
- No proto definitions to maintain
- Worker State Machine code: 0 changes ✅

**gRPC (v1.x):**
- Define .proto files
- Generate Go code
- Implement gRPC server in RAS Adapter
- Migrate Worker to gRPC client
- Update error handling, retry logic
- Worker code: significant changes ❌

**Verdict:** Event-Driven is simpler to implement

### 4. Testability

**Event-Driven (v2.0):**
- Integration tests: Publish command → verify event received
- No need for gRPC mocks
- 89 existing Worker tests remain valid ✅

**gRPC (v1.x):**
- Need gRPC mocks/stubs
- More complex integration tests
- Existing tests may need updates ❌

**Verdict:** Event-Driven is easier to test

### 5. Effort

**Event-Driven (v2.0):**
- Week 2: Copy event handlers (1 day)
- Week 3: Integration tests (all existing tests pass)
- Total effort: 5 weeks MVP

**gRPC (v1.x):**
- Week 1: Define protos, generate code
- Week 2: Implement gRPC server in RAS Adapter
- Week 3: Migrate Worker to gRPC client (significant changes)
- Week 4: Fix broken tests
- Total effort: 5.5-6 weeks MVP

**Verdict:** Event-Driven is faster to implement

## Alternatives Considered

### Alternative 1: Hybrid (Both gRPC + Redis Pub/Sub)

**Pros:**
- Flexibility for future clients
- gRPC for performance-critical paths

**Cons:**
- Increased complexity (two protocols)
- Worker confusion: which to use?
- Maintenance burden (2x code paths)

**Rejected because:** Complexity not justified by benefits

### Alternative 2: gRPC ONLY (No Redis Pub/Sub)

**Pros:**
- Single protocol
- Better performance (binary protocol)

**Cons:**
- Requires rewriting Worker State Machine
- 89 existing tests need updates
- Event-Driven already implemented and working

**Rejected because:** Breaks existing implementation

## Consequences

### Positive

- ✅ Worker State Machine: 0 code changes
- ✅ All 149 existing tests remain valid
- ✅ Simpler implementation (copy event handlers as-is)
- ✅ Loose coupling between Worker and RAS Adapter
- ✅ Faster time to production (5 weeks vs 6 weeks)

### Negative

- ❌ No gRPC for future clients (if needed, can add later)
- ❌ Redis Pub/Sub may have higher latency than gRPC (acceptable for our use case)

### Neutral

- REST API still available for external clients (curl, admin, monitoring)
- Event-Driven architecture is industry-proven pattern

## Implementation Notes

**RAS Adapter will implement:**

1. **Redis Pub/Sub Event Handlers:**
   - Subscribe to: `commands:cluster-service:infobase:lock`
   - Subscribe to: `commands:cluster-service:infobase:unlock`
   - Subscribe to: `commands:cluster-service:sessions:terminate`
   - Publish: `events:cluster-service:*` (success/failure events)

2. **REST API (External Clients):**
   - `GET /api/v1/clusters`
   - `GET /api/v1/infobases`
   - `GET /api/v1/sessions`
   - `POST /api/v1/infobases/{id}/lock`
   - `POST /api/v1/infobases/{id}/unlock`
   - `POST /api/v1/sessions/terminate`

3. **RAS Client Integration:**
   - Use v8platform SDK (same as ras-grpc-gw)
   - Connection pooling
   - Circuit breaker
   - NEW: LockInfobase/UnlockInfobase using RegInfoBase (not UpdateInfobase)

## Monitoring

- Track Redis Pub/Sub latency (should be < 50ms p95)
- Track event handler success rate (should be > 99%)
- Compare with cluster-service baseline performance

## Rollback Plan

If Event-Driven approach fails:
- cluster-service remains running until Week 5
- Can revert to cluster-service if RAS Adapter has issues
- No Worker code changes needed for rollback

## Review

**Reviewed by:** AI Architect, AI Orchestrator
**Date:** 2025-11-19
**Status:** ✅ Accepted

---

**Related Documents:**
- [RAS_ADAPTER_ROADMAP.md](../../roadmaps/RAS_ADAPTER_ROADMAP.md) - Current roadmap (v2.0)
- [RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md](../../architecture/RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md) - Full architecture
- [RAS_ADAPTER_ROADMAP_v1_gRPC.md](RAS_ADAPTER_ROADMAP_v1_gRPC.md) - Superseded roadmap
