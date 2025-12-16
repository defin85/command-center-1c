# RAS Adapter & State Machine - Compatibility Analysis

**Version:** 2.0
**Date:** 2025-11-19
**Status:** Architecture Analysis - FINAL

## TL;DR (30 секунд)

**Вопрос:** Совместим ли новый RAS Adapter roadmap с существующей Event-Driven State Machine?

**Ответ:** ✅ **FULLY COMPATIBLE** - минимальные изменения

**Решение:**
- RAS Adapter реализует **ТОЛЬКО Redis Pub/Sub** event handlers (для Worker State Machine)
- REST API **ТОЛЬКО для external clients** (curl, admin, monitoring)
- **НЕТ gRPC** - Worker не должен делать прямые вызовы к RAS Adapter
- State Machine работает без изменений
- Чистая event-driven архитектура

**Effort:** MVP 5 weeks (было 4.5 weeks в исходном roadmap)

---

## Table of Contents

1. [Current State](#current-state)
2. [Target Architecture](#target-architecture)
3. [Compatibility Analysis](#compatibility-analysis)
4. [Implementation Plan](#implementation-plan)
5. [Migration Timeline](#migration-timeline)
6. [Risk Analysis](#risk-analysis)

---

## Current State

### Event-Driven State Machine (Implemented)

**Status:** ✅ Week 1-2 ЗАВЕРШЕНЫ (100%)

**Architecture:**
```
Worker State Machine
  │
  │ Publish command
  ├─► Redis Pub/Sub: commands:cluster-service:infobase:lock
  │   │
  │   └─► cluster-service Event Handler
  │       │ (Subscribed to commands:*)
  │       │
  │       │ Execute gRPC to ras-grpc-gw
  │       │
  │       └─► Publish: events:cluster-service:infobase:locked
  │           │
  │           └─► Worker State Machine (Wait)
  │
  │ Transition: Init → JobsLocked
```

**Key Components:**
- `go-services/worker/internal/statemachine/` - State Machine orchestrator
- `go-services/cluster-service/internal/eventhandlers/` - Redis Pub/Sub handlers
- Redis Streams/Pub/Sub для message broker

**Commands Published by State Machine:**
```go
const (
	CommandLockInfobase      = "commands:cluster-service:infobase:lock"
	CommandTerminateSessions = "commands:cluster-service:sessions:terminate"
	CommandUnlockInfobase    = "commands:cluster-service:infobase:unlock"
	CommandInstallExtension  = "commands:batch-service:extension:install"
)
```

**Events Expected by State Machine:**
```go
const (
	EventInfobaseLocked      = "events:cluster-service:infobase:locked"
	EventSessionsClosed      = "events:cluster-service:sessions:closed"
	EventInfobaseUnlocked    = "events:cluster-service:infobase:unlocked"
	EventExtensionInstalled  = "events:batch-service:extension:installed"
)
```

**Test Coverage:**
- ✅ 30 unit tests (cluster-service handlers, 81.2% coverage)
- ✅ 16 unit tests (batch-service handlers, 86.5% coverage)
- ✅ 5 integration tests (Redis event flow, State Machine Happy Path)

---

## Target Architecture

### RAS Adapter - Event-Driven Only

**Architecture:**
```
┌──────────────────────────────────────────────────────────┐
│                    RAS Adapter                           │
│                  (Unified Service)                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────┐          ┌────────────────┐         │
│  │ REST Server    │          │ Event Handlers │         │
│  │ (port 8088)    │          │ (Redis Pub/Sub)│         │
│  │                │          │                │         │
│  │ External       │          │ Worker State   │         │
│  │ clients ONLY   │          │ Machine        │         │
│  │ (curl, admin)  │          │ (Event-Driven) │         │
│  └───────┬────────┘          └────────┬───────┘         │
│          │                            │                 │
│          └────────────┬───────────────┘                 │
│                       ▼                                 │
│          ┌────────────────────────┐                     │
│          │   Business Logic       │                     │
│          │   (Service Layer)      │                     │
│          │                        │                     │
│          │ ✓ LockInfobase()       │  ◄─── NEW IMPL     │
│          │ ✓ UnlockInfobase()     │  ◄─── NEW IMPL     │
│          │ ✓ TerminateSessions()  │                     │
│          └────────────┬───────────┘                     │
│                       │                                 │
│                       ▼                                 │
│          ┌────────────────────────┐                     │
│          │   RAS Client           │                     │
│          │   (v8platform SDK)     │                     │
│          │                        │                     │
│          │ ✓ Connection pooling   │                     │
│          │ ✓ Retry logic          │                     │
│          │ ✓ Circuit breaker      │                     │
│          └────────────┬───────────┘                     │
└──────────────────────┼──────────────────────────────────┘
                       │ RAS binary protocol
                       ▼
            ┌──────────────────────┐
            │   1C RAS Server      │
            └──────────────────────┘
```

**Key Points:**
- ✅ Worker общается ТОЛЬКО через Redis Pub/Sub (event-driven)
- ✅ REST API ТОЛЬКО для external clients (debugging, admin, monitoring)
- ❌ НЕТ gRPC - Worker не делает прямых вызовов
- ✅ Loose coupling - Worker не знает про RAS Adapter

### Data Flow

**Worker State Machine → RAS Adapter:**
```
Worker State Machine
  │
  │ 1. Publish command
  └─► Redis: commands:cluster-service:infobase:lock
      │
      │ 2. RAS Adapter subscribes
      └─► RAS Adapter Event Handler
          │
          │ 3. Execute business logic
          └─► service.LockInfobase(clusterID, infobaseID)
              │
              │ 4. Call RAS Server
              └─► RAS Server (RegInfoBase command)
                  │
                  │ 5. Success
                  └─► RAS Adapter publishes event
                      │
                      └─► Redis: events:cluster-service:infobase:locked
                          │
                          └─► Worker State Machine receives event
```

**External Client → RAS Adapter:**
```
Admin / curl
  │
  │ HTTP POST /api/v2/lock-infobase?cluster_id=...&infobase_id=...
  └─► RAS Adapter REST API
      │
      └─► service.LockInfobase(clusterID, infobaseID)
          │
          └─► RAS Server
              │
              └─► HTTP 200 OK (synchronous response)
```

---

## Compatibility Analysis

### ✅ FULLY COMPATIBLE

| Component | Required Interface | RAS Adapter Provides | Compatible? |
|-----------|-------------------|----------------------|-------------|
| **Worker State Machine** | Redis Pub/Sub commands | ✅ Event Handlers subscribe | ✅ YES |
| **State Machine expects events** | `events:cluster-service:*` | ✅ Event Handlers publish | ✅ YES |
| **External clients (admin)** | REST API | ✅ REST Server (port 8088) | ✅ YES |
| **Worker direct calls** | NOT NEEDED | ❌ No gRPC (intentional) | ✅ YES |

**Вывод:** RAS Adapter полностью совместим с State Machine БЕЗ ИЗМЕНЕНИЙ в Worker коде!

### What Does NOT Change

✅ **Worker State Machine** - 0 строк кода изменений
✅ **89 unit tests** State Machine - все проходят
✅ **5 integration tests** - все проходят
✅ **Event flow** - работает так же как с cluster-service

### What Changes

**RAS Adapter (new service):**
- ✅ Copy event handlers from cluster-service
- ✅ Copy business logic from cluster-service
- ✅ Copy RAS client from ras-grpc-gw
- ✅ Add REST API for external clients
- ✅ New Lock/Unlock implementation (RegInfoBase)

**Deprecated:**
- ❌ cluster-service (заменен на RAS Adapter)
- ❌ ras-grpc-gw (слит в RAS Adapter)

---

## Implementation Plan

### Updated RAS Adapter Roadmap (MVP 5 weeks)

#### Week 1: RAS Adapter Foundation

**Goal:** Create RAS Adapter with basic structure

**Tasks:**
- [ ] Create `go-services/ras-adapter` project structure
- [ ] Copy business logic from cluster-service (service layer)
- [ ] Copy RAS client wrapper from ras-grpc-gw
- [ ] Implement REST server (Gin, port 8088)
- [ ] Add health check endpoints
- [ ] Unit tests (coverage > 70%)

**Deliverable:** RAS Adapter runs standalone, REST API works

#### Week 2: New Lock/Unlock Implementation + Event Handlers

**Goal:** Fix LockInfobase/UnlockInfobase + add Redis Pub/Sub handlers

**Day 1-2: Technical Spike**
- [ ] Research RAS RegInfoBase command
- [ ] Test Lock/Unlock with RegInfoBase on real RAS server
- [ ] Validate: Lock → Verify → Unlock workflow works

**Day 3-4: New Implementation**
- [ ] Implement LockInfobase() using RegInfoBase (не UpdateInfobase)
- [ ] Implement UnlockInfobase() using RegInfoBase
- [ ] Unit tests для new implementation

**Day 5: Event Handlers**
- [ ] Copy event handlers from cluster-service
  - `lock_handler.go`
  - `unlock_handler.go`
  - `terminate_handler.go`
- [ ] Update imports to use RAS Adapter service layer
- [ ] Copy 30 unit tests from cluster-service
- [ ] Integration test: Redis command → RAS Adapter → Redis event

**Deliverable:** Lock/Unlock работает + Event handlers respond to Redis

#### Week 3: Integration & Testing

**Goal:** Integrate with Worker State Machine, run all tests

**Tasks:**
- [ ] Deploy RAS Adapter to development
- [ ] Configure Redis Pub/Sub channels
- [ ] Run Worker State Machine integration tests (должны PASS без изменений!)
- [ ] Test extension install end-to-end workflow
- [ ] Performance testing (latency, throughput)

**Deliverable:** Worker State Machine работает с RAS Adapter

#### Week 4: Deploy & Validate

**Goal:** Replace cluster-service with RAS Adapter

**Tasks:**
- [ ] Update docker-compose.yml (remove cluster-service, add ras-adapter)
- [ ] Deploy RAS Adapter
- [ ] Smoke tests (all endpoints)
- [ ] Performance comparison (old vs new)
- [ ] Stop cluster-service and ras-grpc-gw
- [ ] Update documentation

**Deliverable:** RAS Adapter deployed to development, old services deprecated

#### Week 4.5: Manual Testing Gate ⭐ CRITICAL

**Goal:** Comprehensive manual validation before production

**⚠️ GATE CONDITION:** ALL tests must PASS before production rollout

**Tasks:**
- [ ] Run [RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md)
- [ ] Test v2 REST API endpoints (`/api/v2/list-clusters`, `/api/v2/list-infobases`, `/api/v2/lock-infobase`, `/api/v2/unlock-infobase`)
- [ ] Test Redis Pub/Sub event handlers
  - Publish command → verify event received
  - Test all 3 handlers (lock, unlock, terminate)
- [ ] Test State Machine Happy Path end-to-end
- [ ] Test State Machine failure scenarios (7 tests)
- [ ] Performance validation (latency < 50ms for event flow)
- [ ] Error handling validation
- [ ] Sign-off form

**Deliverable:**
- ✅ All tests PASSED
- ✅ Sign-off received
- ✅ Ready for production

---

### Code Structure

```
go-services/ras-adapter/
├── cmd/
│   └── main.go                      # Entry point
├── internal/
│   ├── api/
│   │   ├── generated/               # oapi-codegen server/types
│   │   └── rest/
│   │       ├── router.go            # Gin REST API
│   │       └── v2/                  # /api/v2/* handlers + docs
│   ├── eventhandlers/               # Redis Pub/Sub handlers
│   │   ├── lock_handler.go          # Lock command handler
│   │   ├── unlock_handler.go        # Unlock command handler
│   │   └── terminate_handler.go     # Terminate sessions handler
│   ├── service/
│   │   ├── cluster_service.go       # GetClusters, GetInfobases
│   │   ├── infobase_service.go      # Lock, Unlock (NEW IMPL)
│   │   └── session_service.go       # GetSessions, Terminate
│   ├── ras/
│   │   ├── client.go                # RAS client wrapper
│   │   ├── pool.go                  # Connection pool
│   │   └── circuit_breaker.go       # Circuit breaker
│   └── config/
│       └── config.go                # Configuration
└── go.mod
```

### Main.go Implementation

```go
// go-services/ras-adapter/cmd/main.go
package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/commandcenter1c/go-services/shared/events"
	"github.com/commandcenter1c/ras-adapter/internal/api/rest"
	"github.com/commandcenter1c/ras-adapter/internal/eventhandlers"
	"github.com/commandcenter1c/ras-adapter/internal/service"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
	"golang.org/x/sync/errgroup"
)

func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	// Initialize Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr: os.Getenv("REDIS_HOST") + ":6379",
	})

	// Initialize services
	infobaseSvc := service.NewInfobaseService(...)
	sessionSvc := service.NewSessionService(...)
	clusterSvc := service.NewClusterService(...)

	// Initialize event infrastructure
	publisher := events.NewPublisher(redisClient, "ras-adapter")
	subscriber := events.NewSubscriber(redisClient, nil)

	// Initialize event handlers
	lockHandler := eventhandlers.NewLockHandler(infobaseSvc, publisher, redisClient, logger)
	unlockHandler := eventhandlers.NewUnlockHandler(infobaseSvc, publisher, redisClient, logger)
	terminateHandler := eventhandlers.NewTerminateHandler(sessionSvc, publisher, redisClient, logger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	g, ctx := errgroup.WithContext(ctx)

	// Start Redis Pub/Sub subscribers (for Worker State Machine)
	g.Go(func() error {
		logger.Info("Starting Redis Pub/Sub subscribers")

		subscriber.Subscribe(ctx,
			"commands:cluster-service:infobase:lock",
			lockHandler.Handle,
		)

		subscriber.Subscribe(ctx,
			"commands:cluster-service:infobase:unlock",
			unlockHandler.Handle,
		)

		subscriber.Subscribe(ctx,
			"commands:cluster-service:sessions:terminate",
			terminateHandler.Handle,
		)

		return subscriber.Run(ctx)
	})

	// Start REST server (for external clients)
	restServer := rest.NewServer(clusterSvc, infobaseSvc, sessionSvc, logger)
	httpServer := &http.Server{
		Addr:    ":8088",
		Handler: restServer.Router(),
	}

	g.Go(func() error {
		logger.Info("Starting REST server", zap.String("addr", ":8088"))
		return httpServer.ListenAndServe()
	})

	// Wait for interrupt signal
	g.Go(func() error {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
		<-sigChan

		logger.Info("Shutting down servers...")

		// Shutdown REST server
		if err := httpServer.Shutdown(context.Background()); err != nil {
			logger.Error("REST server shutdown error", zap.Error(err))
		}

		// Cancel context to stop subscribers
		cancel()

		return nil
	})

	if err := g.Wait(); err != nil && err != http.ErrServerClosed {
		logger.Fatal("Server error", zap.Error(err))
	}
}
```

### Event Handler Example

```go
// go-services/ras-adapter/internal/eventhandlers/lock_handler.go
package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/go-services/shared/events"
	"github.com/commandcenter1c/ras-adapter/internal/service"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

type LockHandler struct {
	infobaseSvc *service.InfobaseService
	publisher   *events.Publisher
	redisClient *redis.Client
	logger      *zap.Logger
}

func NewLockHandler(
	infobaseSvc *service.InfobaseService,
	publisher *events.Publisher,
	redisClient *redis.Client,
	logger *zap.Logger,
) *LockHandler {
	return &LockHandler{
		infobaseSvc: infobaseSvc,
		publisher:   publisher,
		redisClient: redisClient,
		logger:      logger,
	}
}

func (h *LockHandler) Handle(ctx context.Context, envelope events.Envelope) error {
	h.logger.Info("handling lock command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("message_id", envelope.MessageID))

	// Parse payload
	var payload struct {
		ClusterID  string `json:"cluster_id"`
		InfobaseID string `json:"infobase_id"`
		DatabaseID string `json:"database_id"`
	}

	if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
		return h.publishFailure(ctx, envelope, fmt.Errorf("invalid payload: %w", err))
	}

	// Idempotency check using Redis SetNX
	lockKey := fmt.Sprintf("locked:%s", payload.InfobaseID)
	alreadyLocked, err := h.redisClient.SetNX(ctx, lockKey, "true", 24*time.Hour).Result()

	if err == nil && !alreadyLocked {
		// Already locked - return success (idempotent)
		h.logger.Info("infobase already locked (idempotent)",
			zap.String("infobase_id", payload.InfobaseID))
		return h.publishSuccess(ctx, envelope, payload)
	}

	// Execute lock via RAS Adapter service (NEW IMPLEMENTATION)
	err = h.infobaseSvc.LockInfobase(ctx, payload.ClusterID, payload.InfobaseID)

	if err != nil {
		// Clean up Redis key on failure
		h.redisClient.Del(ctx, lockKey)
		return h.publishFailure(ctx, envelope, err)
	}

	return h.publishSuccess(ctx, envelope, payload)
}

func (h *LockHandler) publishSuccess(ctx context.Context, envelope events.Envelope, payload interface{}) error {
	return h.publisher.Publish(ctx,
		"events:cluster-service:infobase:locked",
		"cluster.infobase.locked",
		payload,
		envelope.CorrelationID,
	)
}

func (h *LockHandler) publishFailure(ctx context.Context, envelope events.Envelope, err error) error {
	return h.publisher.Publish(ctx,
		"events:cluster-service:infobase:lock:failed",
		"cluster.infobase.lock.failed",
		map[string]interface{}{
			"error": err.Error(),
		},
		envelope.CorrelationID,
	)
}
```

---

## Migration Timeline

### Phase 1: Development (Week 1-3)
```
Week 1: RAS Adapter Foundation
Week 2: Lock/Unlock + Event Handlers
Week 3: Integration Testing
```

### Phase 2: Validation (Week 4-4.5)
```
Week 4: Deploy + Validate
Week 4.5: Manual Testing Gate ⭐
```

### Phase 3: Production (Week 5)
```
Gradual rollout:
- 10% traffic → RAS Adapter
- Monitor 4 hours
- 50% traffic → RAS Adapter
- Monitor 4 hours
- 100% traffic → RAS Adapter
```

### Phase 4: Cleanup (After Week 5)
```
- Deprecate cluster-service
- Deprecate ras-grpc-gw
- Archive old code
- Update documentation
```

---

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Event handlers don't work in RAS Adapter** | Very Low | High | Copy exact code from cluster-service, port all 30 unit tests |
| **State Machine breaks** | Very Low | Critical | NO code changes in Worker, run all 89 existing tests |
| **Redis Pub/Sub reliability** | Low | Medium | Already proven in Week 1-2, fail-open behavior exists |
| **RegInfoBase doesn't work** | Low | Critical | Technical spike Week 2 Day 1-2 on real RAS |

### Integration Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **REST API conflicts with event handlers** | Very Low | Low | Separate concerns, independent goroutines |
| **Performance degradation** | Low | Medium | Load testing Week 3, compare with cluster-service baseline |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Confusion about interfaces** | Low | Low | Documentation: Worker uses Redis ONLY, admins use REST |
| **Rollback difficulty** | Low | Medium | Keep cluster-service running until Week 5 complete |

---

## Success Criteria

### Week 4.5 Validation

- [ ] All REST API endpoints работают (GET /clusters, /infobases, POST /lock, /unlock)
- [ ] All Redis Pub/Sub event handlers работают (lock, unlock, terminate)
- [ ] State Machine integration tests PASS без изменений (5 tests)
- [ ] Worker Event-Driven mode работает end-to-end
- [ ] Extension install успешно через State Machine
- [ ] Performance: Event flow latency < 50ms (p95)
- [ ] No regressions в 149 existing unit tests
- [ ] Sign-off received

### Production Validation (Week 5)

- [ ] 100% traffic через RAS Adapter
- [ ] Success rate >= 95%
- [ ] Zero errors в Redis Pub/Sub event flow
- [ ] cluster-service и ras-grpc-gw deprecated
- [ ] Documentation updated

---

## Conclusion

**Вердикт:** ✅ **RAS Adapter ПОЛНОСТЬЮ СОВМЕСТИМ с Event-Driven State Machine**

**Архитектурное решение:**
- RAS Adapter = REST API (external) + Redis Pub/Sub (Worker)
- NO gRPC - Worker не делает прямых вызовов
- Clean event-driven architecture
- Loose coupling между сервисами

**Изменения:**
- Worker State Machine: **0 строк кода** ✅
- RAS Adapter: Новый сервис (копирование из cluster-service + новая Lock/Unlock реализация)
- Effort: **5 weeks** MVP

**Риск:** 🟢 **VERY LOW** - State Machine работает без изменений, event handlers копируются as-is

---

## References

- [EVENT_DRIVEN_ROADMAP.md](../../EVENT_DRIVEN_ROADMAP.md) - Event-Driven State Machine (Week 1-2 DONE)
- [RAS_ADAPTER_ROADMAP.md](../../roadmaps/RAS_ADAPTER_ROADMAP.md) - RAS Adapter unified architecture (v2.0) ⭐
- [WHY_EVENT_DRIVEN_NOT_GRPC.md](../../archive/roadmap_variants/WHY_EVENT_DRIVEN_NOT_GRPC.md) - Architectural decision (v2.0)
- [RAS_ADAPTER_ROADMAP_v1_gRPC.md](../../archive/roadmap_variants/RAS_ADAPTER_ROADMAP_v1_gRPC.md) - Historical roadmap (superseded)
- [RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md) - Week 4.5 testing
- [OBSERVABILITY_QUICKSTART.md](OBSERVABILITY_QUICKSTART.md) - Strategy selection guide
- `go-services/worker/internal/statemachine/` - State Machine implementation
- `go-services/cluster-service/internal/eventhandlers/` - Event handlers to copy

---

**Version History:**

- v2.0 (2025-11-19): **ARCHITECTURE CHANGE** - Removed gRPC completely
  - RAS Adapter = REST (external) + Redis Pub/Sub (Worker) ONLY
  - NO direct Worker → RAS Adapter calls (clean event-driven)
  - Simplified architecture, lower risk
  - Effort: 5 weeks (было 5.5 weeks)

- v1.0 (2025-11-19): Initial version (Hybrid gRPC + Redis)

**Authors:** AI Orchestrator + AI Architect

**Status:** ✅ Ready for Implementation
