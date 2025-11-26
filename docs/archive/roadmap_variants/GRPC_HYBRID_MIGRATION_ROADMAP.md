# gRPC Hybrid Migration Roadmap - CommandCenter1C

**Version:** 1.0
**Date:** 2025-11-24
**Status:** 📋 PLANNING
**Duration:** 8-10 недель (Sprint 2.3 - Sprint 4.4)
**Architecture:** REST для Frontend, gRPC для Internal Microservices
**Related:** [GRPC_MIGRATION_ANALYSIS.md](../GRPC_MIGRATION_ANALYSIS.md)

---

## 🎯 Executive Summary

### Goal

Мигрировать внутреннюю коммуникацию микросервисов с REST/HTTP на gRPC для максимального performance при сохранении REST API для Frontend:

- **+107% throughput** для small payload операций
- **-48% latency** для Lock/Unlock operations
- **-34% memory** footprint (больше capacity без доп. затрат)
- **Native streaming** для batch операций и real-time events
- **Contract-First** через Proto files (единый источник истины)

### Why gRPC Hybrid?

**Проблема:** При 700+ базах 1С текущая REST архитектура достигает пределов:
- Lock/Unlock латентность ~250ms (JSON serialization overhead)
- Batch операции ограничены HTTP/1.1 throughput
- Нет native streaming для progress updates

**Решение:** gRPC для internal, REST для external
- **Frontend DX сохраняется:** React команда продолжает работать с REST
- **Internal performance:** 10x throughput для batch операций
- **Proven at scale:** Netflix, LinkedIn, Uber используют идентичный подход

### Current vs Target

**Current (Week 2.5):**
```
Frontend → REST → API Gateway → REST → Orchestrator → REST → Worker → REST → ras-adapter
```

**Target (Week 12.5):**
```
Frontend → REST → API Gateway → gRPC → Orchestrator → gRPC → Worker → gRPC → ras-adapter
                                    ↓ Redis Pub/Sub (сохраняется)
                              Frontend WebSocket (real-time events)
```

### Effort & ROI

| Метрика | Значение |
|---------|----------|
| **Duration** | 8-10 недель |
| **Team size** | 3 developers |
| **Effort** | 24-30 человеко-недель |
| **Performance gain** | 3-10x (зависит от операции) |
| **Infrastructure savings** | -34% RAM, -19% CPU |
| **ROI payback** | 6-9 месяцев при 700+ базах |

---

## 🏗️ Target Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React:5173)                      │
│                 TypeScript + REST API client                 │
└────────────────────┬────────────────────────────────────────┘
                     │ REST/JSON (HTTP/1.1)
                     │ OpenAPI Contract
                     ↓
┌─────────────────────────────────────────────────────────────┐
│              API Gateway (Go:8080)                           │
│  • JWT auth, Rate limiting                                   │
│  • REST → gRPC translation                                   │
│  • Protocol detection & routing                              │
└────────────────────┬────────────────────────────────────────┘
                     │ gRPC (HTTP/2)
                     │ Proto Contract
                     ↓
┌─────────────────────────────────────────────────────────────┐
│           Orchestrator (FastAPI:8001 + Django:8000)         │
│  • FastAPI: gRPC server для internal APIs                   │
│  • Django: Admin Panel, ORM, Celery                         │
│  • Redis Pub/Sub: Event broadcasting (сохраняется)          │
└────┬─────────────────────┬──────────────────────────────────┘
     │ gRPC                 │ Redis Pub/Sub
     │                      │ (для Frontend WebSocket)
     ↓                      ↓
┌─────────────────┐   ┌─────────────────────┐
│  Worker (Go)    │   │ Frontend WebSocket  │
│  • gRPC client  │   │ • Real-time events  │
│  • Task exec    │   └─────────────────────┘
└────┬────────────┘
     │ gRPC
     │ + Redis Pub/Sub
     ↓
┌─────────────────────────────────────────────────────────────┐
│              ras-adapter (Go:8088)                           │
│  • gRPC server для Lock/Unlock/Sessions                     │
│  • REST API для external clients (curl, monitoring)         │
│  • Redis Pub/Sub для event broadcasting                     │
│  • RAS protocol integration                                  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Examples

**Lock Database (gRPC RPC + Redis Pub/Sub):**
```
1. Frontend → REST → API Gateway: POST /api/v1/databases/{id}/lock
2. API Gateway → gRPC → Orchestrator: LockDatabaseRequest
3. Orchestrator → Celery → Redis Queue → Worker
4. Worker → gRPC → ras-adapter: LockDatabase(db-123, EXCLUSIVE)
5. ras-adapter → RAS protocol → 1C Cluster (блокировка)
6. ras-adapter → Redis Pub/Sub → "database.locked" event
7. Frontend WebSocket ← Redis Sub (real-time UI update)
8. Worker ← gRPC Response: LockResponse{success: true, lock_id: "..."}
9. API Gateway ← gRPC → REST translation
10. Frontend ← REST Response: 200 OK
```

**Batch Operations (gRPC Streaming):**
```
1. Worker → gRPC Bidirectional Stream → ras-adapter
2. Worker sends: LockRequest stream (100 databases)
3. ras-adapter processes each:
   - Lock via RAS
   - Send LockResponse to stream (real-time)
   - Publish progress to Redis Pub/Sub (for Frontend)
4. Worker receives: Stream of LockResponse (as they complete)
5. Frontend sees: Real-time progress bar (via WebSocket)
```

### Technology Stack

| Component | Current | Target | Change |
|-----------|---------|--------|--------|
| **api-gateway** | REST/Gin | REST + gRPC gateway | Add gRPC client |
| **orchestrator** | Django DRF | FastAPI gRPC + Django ORM | Add FastAPI app |
| **worker** | REST client | gRPC client | Replace HTTP with gRPC |
| **ras-adapter** | REST only | gRPC + REST | Add gRPC server |
| **Frontend** | REST/Axios | REST/Axios | NO CHANGE |
| **Contracts** | OpenAPI YAML | Proto files + OpenAPI | Add .proto files |

---

## 📅 10-Week Timeline

### Overview

```
Sprint 2.3-2.4: Foundation (Week 1-2)       ━━━━━━━━ 20%
Sprint 3.1-3.2: Core Migration (Week 3-5)  ━━━━━━━━━━━━ 30%
Sprint 3.3-3.4: API Gateway (Week 6-7)     ━━━━━━ 15%
Sprint 4.1-4.2: Integration (Week 8-9)     ━━━━━━━━ 20%
Sprint 4.3-4.4: Production (Week 10)       ━━━ 15%
```

---

## Week 1-2: Foundation & Proto Contracts 🏗️

**Sprint:** 2.3-2.4
**Dates:** Current + 0-2 weeks
**Goal:** Setup tooling, create Proto contracts, validate approach

### Deliverables

#### 1. Proto Repository Setup

**Structure:**
```
contracts/
├── proto/
│   ├── buf.yaml                        # Buf build config
│   ├── buf.gen.yaml                    # Code generation
│   ├── cc1c/
│   │   ├── common/v1/
│   │   │   ├── types.proto             # Shared types
│   │   │   └── errors.proto            # Error codes
│   │   ├── databases/v1/
│   │   │   └── database_service.proto  # Database CRUD
│   │   ├── ras/v1/
│   │   │   └── ras_adapter.proto       # Lock/Unlock/Sessions
│   │   ├── worker/v1/
│   │   │   └── worker_service.proto    # Task execution
│   │   └── operations/v1/
│   │       └── operation_service.proto # Operation management
│   └── third_party/
│       └── google/                     # Well-known types
└── scripts/
    ├── generate-proto.sh               # Generate all
    └── validate-proto.sh               # Buf lint + breaking
```

**Tasks:**
- [ ] Install Buf CLI (`go install github.com/bufbuild/buf/cmd/buf@latest`)
- [ ] Create buf.yaml with lint rules
- [ ] Create buf.gen.yaml for Go/Python/TypeScript generation
- [ ] Setup CI/CD pipeline for proto validation
- [ ] Write initial proto files (copy from GRPC_MIGRATION_ANALYSIS.md examples)

**Example buf.gen.yaml:**
```yaml
version: v1
managed:
  enabled: true
plugins:
  # Go generation
  - plugin: go
    out: ../go-services/shared/proto
    opt: paths=source_relative
  - plugin: go-grpc
    out: ../go-services/shared/proto
    opt: paths=source_relative

  # Python generation
  - plugin: python
    out: ../orchestrator/apps/core/proto
  - plugin: grpc-python
    out: ../orchestrator/apps/core/proto

  # TypeScript generation (optional for Frontend)
  - plugin: es
    out: ../frontend/src/proto
    opt: target=ts
```

#### 2. Development Environment

**Install dependencies:**
```bash
# Go services
cd go-services/api-gateway
go get google.golang.org/grpc@latest
go get google.golang.org/protobuf@latest

# Python/Django
cd orchestrator
pip install grpcio grpcio-tools grpcio-reflection

# Validation
buf --version
protoc --version
```

**Update docker-compose.yml:**
```yaml
services:
  # Add gRPC ports
  orchestrator-grpc:
    build: ./orchestrator
    command: python manage.py run_grpc_server
    ports:
      - "50051:50051"  # gRPC port
    networks:
      - backend

  ras-adapter:
    ports:
      - "8088:8088"   # REST API
      - "50052:50052" # gRPC server
```

#### 3. Proof of Concept

**Minimal gRPC implementation:**

```go
// ras-adapter/internal/grpc/server.go
type Server struct {
    pb.UnimplementedRASAdapterServiceServer
    rasClient *ras.Client
}

func (s *Server) Ping(ctx context.Context, req *pb.PingRequest) (*pb.PongResponse, error) {
    return &pb.PongResponse{
        Message: "pong",
        Timestamp: timestamppb.Now(),
    }, nil
}
```

```go
// worker/internal/grpc/client.go
func NewRASAdapterClient(addr string) (pb.RASAdapterServiceClient, error) {
    conn, err := grpc.Dial(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
    if err != nil {
        return nil, err
    }
    return pb.NewRASAdapterServiceClient(conn), nil
}
```

**Test PoC:**
```bash
# Start ras-adapter gRPC server
cd go-services/ras-adapter
go run cmd/main.go --grpc-port=50052

# Test with grpcurl
grpcurl -plaintext localhost:50052 cc1c.ras.v1.RASAdapterService/Ping

# Expected:
{
  "message": "pong",
  "timestamp": "2025-11-24T14:30:00Z"
}
```

### Success Criteria Week 1-2

- [ ] ✅ Buf tooling работает (generate, lint, breaking)
- [ ] ✅ Proto contracts созданы для всех 5 сервисов
- [ ] ✅ Go/Python code generation работает
- [ ] ✅ PoC: Worker → gRPC → ras-adapter Ping/Pong
- [ ] ✅ CI/CD pipeline для proto validation
- [ ] ✅ Team training на gRPC basics (1 день)

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Team незнакома с Proto | MEDIUM | Training session + pair programming |
| Breaking changes detection | LOW | Buf breaking change checks в CI |
| Python gRPC async issues | MEDIUM | Используем sync calls first, async later |

---

## Week 3-5: Core Service Migration 🚀

**Sprint:** 3.1-3.2
**Dates:** Week 3-5
**Goal:** Мигрировать критичный путь Worker ↔ ras-adapter на gRPC

### Priority Order

1. **ras-adapter gRPC server** (Week 3)
2. **Worker gRPC client** (Week 4)
3. **Orchestrator gRPC** (Week 5)

### Week 3: ras-adapter gRPC Server

**Implement services:**

```protobuf
// contracts/proto/cc1c/ras/v1/ras_adapter.proto
service RASAdapterService {
  // Lock/Unlock operations
  rpc LockDatabase(LockRequest) returns (LockResponse);
  rpc UnlockDatabase(UnlockRequest) returns (UnlockResponse);

  // Batch with streaming
  rpc BatchLockDatabases(stream LockRequest) returns (stream LockResponse);

  // Session management
  rpc CreateSession(CreateSessionRequest) returns (Session);
  rpc TerminateSession(TerminateSessionRequest) returns (TerminateSessionResponse);
  rpc ListSessions(ListSessionsRequest) returns (ListSessionsResponse);

  // Cluster info
  rpc GetClusterInfo(GetClusterInfoRequest) returns (ClusterInfo);

  // Streaming events
  rpc StreamClusterEvents(StreamEventsRequest) returns (stream ClusterEvent);
}
```

**Implementation:**
```go
// ras-adapter/internal/grpc/lock_handler.go
func (s *Server) LockDatabase(ctx context.Context, req *pb.LockRequest) (*pb.LockResponse, error) {
    // 1. Validate request
    if req.DatabaseId == "" {
        return nil, status.Error(codes.InvalidArgument, "database_id required")
    }

    // 2. Execute lock via RAS
    result, err := s.rasClient.LockInfobase(ctx, &ras.LockParams{
        InfobaseID: req.DatabaseId,
        Mode:       convertLockMode(req.Mode),
        Message:    req.Message,
        PermCode:   req.PermissionCode,
    })
    if err != nil {
        return nil, status.Errorf(codes.Internal, "lock failed: %v", err)
    }

    // 3. Publish event to Redis (для Frontend)
    s.publishEvent(ctx, "database.locked", req.DatabaseId)

    // 4. Return gRPC response
    return &pb.LockResponse{
        Success:  true,
        LockId:   result.LockID,
        Message:  "Database locked successfully",
        LockedAt: timestamppb.Now(),
    }, nil
}
```

**Tasks Week 3:**
- [ ] Implement LockDatabase, UnlockDatabase (gRPC)
- [ ] Implement CreateSession, TerminateSession, ListSessions
- [ ] Implement GetClusterInfo
- [ ] Add Redis Pub/Sub publishing (сохранить для Frontend)
- [ ] Write unit tests (target: >80% coverage)
- [ ] Add metrics (Prometheus)
- [ ] Add logging (structured)
- [ ] Performance testing (benchmark vs REST)

### Week 4: Worker gRPC Client

**Replace REST client:**

```go
// worker/internal/clients/ras_adapter.go (OLD - REST)
func (c *RASAdapterClient) LockDatabase(ctx context.Context, dbID string) error {
    resp, err := c.httpClient.Post(
        fmt.Sprintf("%s/api/v1/databases/%s/lock", c.baseURL, dbID),
        "application/json",
        body,
    )
    // JSON parsing, error handling...
}
```

```go
// worker/internal/clients/ras_adapter_grpc.go (NEW - gRPC)
func (c *RASAdapterGRPCClient) LockDatabase(ctx context.Context, dbID string, mode LockMode) (*LockResponse, error) {
    ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
    defer cancel()

    resp, err := c.grpcClient.LockDatabase(ctx, &pb.LockRequest{
        DatabaseId:     dbID,
        Mode:          pb.LockMode(mode),
        PermissionCode: c.workerID,
        Timeout:       durationpb.New(5 * time.Minute),
    })
    if err != nil {
        return nil, fmt.Errorf("grpc call failed: %w", err)
    }

    return &LockResponse{
        Success: resp.Success,
        LockID:  resp.LockId,
    }, nil
}
```

**Tasks Week 4:**
- [ ] Create gRPC client wrapper
- [ ] Replace REST calls в Worker State Machine
- [ ] Add connection pooling (grpc.WithDefaultCallOptions)
- [ ] Add retry logic (grpc_retry)
- [ ] Add circuit breaker (github.com/sony/gobreaker)
- [ ] Update Worker tests (mock gRPC)
- [ ] Integration tests (Worker → ras-adapter)
- [ ] Backward compatibility mode (feature flag: USE_GRPC=true/false)

**Feature flag example:**
```go
// worker/internal/config/config.go
type Config struct {
    UseGRPC         bool   `env:"USE_GRPC" envDefault:"false"`
    RASAdapterREST  string `env:"RAS_ADAPTER_REST" envDefault:"http://localhost:8088"`
    RASAdapterGRPC  string `env:"RAS_ADAPTER_GRPC" envDefault:"localhost:50052"`
}

// worker/internal/clients/factory.go
func NewRASAdapterClient(cfg *Config) RASAdapter {
    if cfg.UseGRPC {
        return NewRASAdapterGRPCClient(cfg.RASAdapterGRPC)
    }
    return NewRASAdapterRESTClient(cfg.RASAdapterREST)
}
```

### Week 5: Orchestrator gRPC Integration

**Add FastAPI gRPC server:**

```python
# orchestrator/fastapi_app/main.py
import grpc
from concurrent import futures
from apps.core.proto import operation_service_pb2_grpc
from fastapi_app.grpc_handlers import OperationServiceHandler

async def start_grpc_server():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    operation_service_pb2_grpc.add_OperationServiceServicer_to_server(
        OperationServiceHandler(), server
    )
    server.add_insecure_port('[::]:50051')
    await server.start()
    await server.wait_for_termination()
```

```python
# orchestrator/fastapi_app/grpc_handlers/operation_handler.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.operations.models import Operation
from apps.core.proto import operation_service_pb2 as pb

class OperationServiceHandler(pb.OperationServiceServicer):
    async def GetOperation(self, request, context):
        try:
            # Django ORM async query
            operation = await Operation.objects.aget(id=request.operation_id)

            return pb.OperationResponse(
                id=str(operation.id),
                status=operation.status,
                progress=operation.progress,
                created_at=operation.created_at.isoformat(),
            )
        except Operation.DoesNotExist:
            context.abort(grpc.StatusCode.NOT_FOUND, "Operation not found")
```

**Tasks Week 5:**
- [ ] Setup FastAPI + Django hybrid (separate processes)
- [ ] Implement Operation gRPC service
- [ ] Implement Database gRPC service
- [ ] Add Celery integration (shared Django ORM)
- [ ] Connection pooling для gRPC
- [ ] Update Orchestrator tests
- [ ] Docker compose setup (dual service)

### Success Criteria Week 3-5

- [ ] ✅ ras-adapter gRPC server работает (Lock/Unlock/Sessions)
- [ ] ✅ Worker использует gRPC (feature flag)
- [ ] ✅ Orchestrator gRPC server работает (Operations/Databases)
- [ ] ✅ Performance improvement измерен: >30% latency reduction
- [ ] ✅ Redis Pub/Sub сохранён для Frontend WebSocket
- [ ] ✅ Backward compatibility (REST still works)
- [ ] ✅ Unit + Integration tests >80% coverage

### Performance Benchmarking

**Test scenarios:**
```bash
# Benchmark REST vs gRPC
cd scripts/benchmarks

# REST baseline
./bench-rest.sh --operations=1000 --concurrency=10
# Expected: ~250ms P95 latency, ~500 req/sec

# gRPC comparison
./bench-grpc.sh --operations=1000 --concurrency=10
# Target: <130ms P95 latency, >1500 req/sec

# Generate report
./compare-results.sh
```

**Success metric:** >30% latency improvement, >2x throughput

---

## Week 6-7: API Gateway gRPC Translation 🌉

**Sprint:** 3.3-3.4
**Dates:** Week 6-7
**Goal:** API Gateway translates REST → gRPC для внутренних вызовов

### Architecture

```
Frontend → REST → API Gateway → gRPC → Orchestrator
                      ↓
              Protocol Translation
              REST JSON ↔ gRPC Protobuf
```

### Implementation

**Add gRPC client pool:**
```go
// api-gateway/internal/grpc/client_pool.go
type ClientPool struct {
    orchestratorConn *grpc.ClientConn
    rasAdapterConn   *grpc.ClientConn
    workerConn       *grpc.ClientConn

    operationClient  pb.OperationServiceClient
    databaseClient   pb.DatabaseServiceClient
    rasClient        pb.RASAdapterServiceClient
}

func NewClientPool(cfg *Config) (*ClientPool, error) {
    // Connection pooling
    opts := []grpc.DialOption{
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithDefaultCallOptions(
            grpc.MaxCallRecvMsgSize(10 * 1024 * 1024), // 10MB
            grpc.MaxCallSendMsgSize(10 * 1024 * 1024),
        ),
        grpc.WithKeepaliveParams(keepalive.ClientParameters{
            Time:    10 * time.Second,
            Timeout: 3 * time.Second,
        }),
    }

    orchestratorConn, err := grpc.Dial(cfg.OrchestratorGRPC, opts...)
    if err != nil {
        return nil, err
    }

    return &ClientPool{
        orchestratorConn: orchestratorConn,
        operationClient:  pb.NewOperationServiceClient(orchestratorConn),
        databaseClient:   pb.NewDatabaseServiceClient(orchestratorConn),
    }, nil
}
```

**REST → gRPC translation:**
```go
// api-gateway/internal/handlers/operations.go
func (h *Handler) GetOperation(c *gin.Context) {
    operationID := c.Param("id")

    // gRPC call
    ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
    defer cancel()

    resp, err := h.grpcPool.operationClient.GetOperation(ctx, &pb.GetOperationRequest{
        OperationId: operationID,
    })
    if err != nil {
        if status.Code(err) == codes.NotFound {
            c.JSON(404, gin.H{"error": "Operation not found"})
            return
        }
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    // Proto → JSON translation
    c.JSON(200, gin.H{
        "id":           resp.Id,
        "status":       resp.Status.String(),
        "progress":     resp.Progress,
        "created_at":   resp.CreatedAt.AsTime(),
        "updated_at":   resp.UpdatedAt.AsTime(),
    })
}
```

**Health checks:**
```go
// api-gateway/internal/health/grpc_health.go
func (h *HealthChecker) CheckGRPCServices() map[string]string {
    services := map[string]string{
        "orchestrator": h.checkService(h.grpcPool.orchestratorConn),
        "ras-adapter":  h.checkService(h.grpcPool.rasAdapterConn),
    }
    return services
}

func (h *HealthChecker) checkService(conn *grpc.ClientConn) string {
    ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
    defer cancel()

    if conn.GetState() == connectivity.Ready {
        return "healthy"
    }
    return "unhealthy"
}
```

### Tasks Week 6-7

- [ ] Add gRPC client pool to API Gateway
- [ ] Implement REST → gRPC translation для всех endpoints
- [ ] Add connection health monitoring
- [ ] Load balancing (если несколько Orchestrator instances)
- [ ] Graceful degradation (fallback to REST если gRPC fails)
- [ ] Update API Gateway tests
- [ ] Load testing (simulate production traffic)
- [ ] Documentation (API Gateway architecture)

### Load Balancing Setup

**nginx.conf (если нужен L7 load balancer):**
```nginx
upstream orchestrator_grpc {
    server orchestrator-1:50051;
    server orchestrator-2:50051;
    server orchestrator-3:50051;
}

server {
    listen 50051 http2;

    location / {
        grpc_pass grpc://orchestrator_grpc;
    }
}
```

**Or use client-side load balancing:**
```go
// API Gateway uses dns:/// resolver
conn, err := grpc.Dial(
    "dns:///orchestrator-service:50051",
    grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
)
```

### Success Criteria Week 6-7

- [ ] ✅ API Gateway translates REST → gRPC для всех endpoints
- [ ] ✅ Health checks работают для gRPC connections
- [ ] ✅ Load balancing настроен (если > 1 instance)
- [ ] ✅ Graceful degradation работает
- [ ] ✅ Frontend НЕ замечает изменений (REST API unchanged)
- [ ] ✅ Load testing: API Gateway выдерживает production traffic
- [ ] ✅ Metrics показывают improvement

---

## Week 8-9: Integration & Testing 🧪

**Sprint:** 4.1-4.2
**Dates:** Week 8-9
**Goal:** End-to-end testing, performance validation, bug fixing

### Test Strategy

#### 1. Unit Tests

**Target coverage:** >80% для всех gRPC handlers

```go
// ras-adapter/internal/grpc/lock_handler_test.go
func TestLockDatabase_Success(t *testing.T) {
    // Mock RAS client
    mockRAS := &mockRASClient{
        lockResponse: &ras.LockResult{LockID: "lock-123"},
    }

    server := &Server{rasClient: mockRAS}

    resp, err := server.LockDatabase(context.Background(), &pb.LockRequest{
        DatabaseId: "db-123",
        Mode:       pb.LOCK_MODE_EXCLUSIVE,
    })

    assert.NoError(t, err)
    assert.True(t, resp.Success)
    assert.Equal(t, "lock-123", resp.LockId)
}
```

#### 2. Integration Tests

**Test full flow:**
```go
// tests/integration/grpc_flow_test.go
func TestLockDatabaseFlow(t *testing.T) {
    // 1. Start all services (docker-compose)
    docker := setupDockerCompose(t)
    defer docker.Cleanup()

    // 2. Worker calls ras-adapter via gRPC
    workerClient := NewWorkerClient("localhost:50051")
    lockResp, err := workerClient.LockDatabase(ctx, "test-db-1")
    assert.NoError(t, err)

    // 3. Verify lock in ras-adapter
    rasClient := NewRASClient("localhost:50052")
    sessions, _ := rasClient.ListSessions(ctx, &pb.ListSessionsRequest{
        DatabaseId: "test-db-1",
    })
    assert.Len(t, sessions.Sessions, 1)

    // 4. Verify event published to Redis
    redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
    sub := redisClient.Subscribe(ctx, "cluster:events")
    msg := <-sub.Channel()
    assert.Contains(t, msg.Payload, "database.locked")
}
```

#### 3. Performance Tests

**Benchmark tools:**
```bash
# ghz - gRPC benchmarking tool
ghz --insecure \
    --proto contracts/proto/cc1c/ras/v1/ras_adapter.proto \
    --call cc1c.ras.v1.RASAdapterService.LockDatabase \
    -d '{"database_id":"test-db","mode":1}' \
    -n 10000 \
    -c 100 \
    localhost:50052

# Expected results:
# - P50 latency: <100ms
# - P95 latency: <200ms
# - Throughput: >1000 req/sec
```

**Load test scenarios:**
```yaml
# k6 load test config
scenarios:
  lock_database:
    executor: ramping-vus
    stages:
      - duration: 2m
        target: 50   # Ramp up to 50 users
      - duration: 5m
        target: 50   # Stay at 50 users
      - duration: 2m
        target: 0    # Ramp down

thresholds:
  grpc_req_duration:
    - p(95) < 200  # 95% requests under 200ms
  grpc_req_failed:
    - rate < 0.01  # Less than 1% errors
```

#### 4. Compatibility Tests

**Ensure REST still works:**
```bash
# Test REST endpoints (should still work)
curl http://localhost:8080/api/v1/operations
curl http://localhost:8080/api/v1/databases

# Test gRPC endpoints
grpcurl -plaintext localhost:50051 cc1c.operations.v1.OperationService/ListOperations
```

### Tasks Week 8-9

**Week 8: Testing**
- [ ] Write unit tests для всех gRPC handlers (target >80%)
- [ ] Write integration tests (full flow)
- [ ] Performance benchmarking (ghz, k6)
- [ ] Compatibility testing (REST + gRPC parallel)
- [ ] Security testing (TLS, auth)
- [ ] Chaos engineering (kill services, network latency)

**Week 9: Bug Fixing & Optimization**
- [ ] Fix bugs found в testing
- [ ] Optimize slow paths
- [ ] Connection pooling tuning
- [ ] Memory leak detection (pprof)
- [ ] CPU profiling (pprof)
- [ ] Update documentation

### Monitoring & Observability

**Add metrics:**
```go
// shared/metrics/grpc_metrics.go
var (
    grpcRequestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "grpc_request_duration_seconds",
            Help:    "gRPC request duration",
            Buckets: prometheus.DefBuckets,
        },
        []string{"service", "method", "status"},
    )

    grpcRequestTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "grpc_requests_total",
            Help: "Total gRPC requests",
        },
        []string{"service", "method", "status"},
    )
)
```

**Grafana dashboard:**
- gRPC request rate (по сервисам)
- P50/P95/P99 latency
- Error rate
- Connection pool stats
- Memory/CPU usage

### Success Criteria Week 8-9

- [ ] ✅ Unit tests >80% coverage
- [ ] ✅ Integration tests проходят
- [ ] ✅ Performance improvement подтвержден: >40% latency reduction
- [ ] ✅ Load tests: система выдерживает 2x production traffic
- [ ] ✅ Compatibility: REST и gRPC работают параллельно
- [ ] ✅ Zero critical bugs
- [ ] ✅ Monitoring dashboard настроен
- [ ] ✅ Documentation complete

---

## Week 10: Production Rollout 🚀

**Sprint:** 4.3-4.4
**Dates:** Week 10
**Goal:** Staged deployment, monitoring, rollback plan

### Deployment Strategy: Canary Release

**Stage 1: 5% traffic (Day 1-2)**
```yaml
# kubernetes/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway-grpc
spec:
  replicas: 1  # 1 из 20 pods (5%)
  template:
    spec:
      containers:
      - name: api-gateway
        env:
        - name: USE_GRPC
          value: "true"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway-rest
spec:
  replicas: 19  # 19 из 20 pods (95%)
  template:
    spec:
      containers:
      - name: api-gateway
        env:
        - name: USE_GRPC
          value: "false"
```

**Monitoring:**
- Compare latency (gRPC vs REST pods)
- Error rate
- Resource usage
- User complaints

**Go/No-Go decision:** Если metrics OK → proceed

**Stage 2: 25% traffic (Day 3-4)**
```
gRPC pods: 5 из 20 (25%)
REST pods: 15 из 20 (75%)
```

**Stage 3: 50% traffic (Day 5-6)**
```
gRPC pods: 10 из 20 (50%)
REST pods: 10 из 20 (50%)
```

**Stage 4: 100% traffic (Day 7-8)**
```
gRPC pods: 20 из 20 (100%)
REST pods: 0 (retire)
```

### Rollback Plan

**If issues detected:**
```bash
# Immediate rollback to REST
kubectl scale deployment api-gateway-rest --replicas=20
kubectl scale deployment api-gateway-grpc --replicas=0

# Takes <30 seconds
```

**Rollback triggers:**
- Error rate >1%
- P95 latency increase >20%
- User complaints >5 per hour
- Memory leak detected
- Critical bugs

### Production Checklist

**Before deployment:**
- [ ] All tests pass (unit, integration, load)
- [ ] Performance benchmarks meet targets
- [ ] Security audit complete
- [ ] Documentation updated (runbooks, troubleshooting)
- [ ] Monitoring dashboards ready
- [ ] Rollback plan tested
- [ ] Team trained on new architecture
- [ ] On-call rotation scheduled

**During deployment:**
- [ ] Staged rollout (5% → 25% → 50% → 100%)
- [ ] Monitor metrics every 30 minutes
- [ ] Check error logs
- [ ] User feedback monitoring
- [ ] Performance comparison (gRPC vs REST)

**After deployment:**
- [ ] Post-mortem meeting
- [ ] Document lessons learned
- [ ] Update metrics baseline
- [ ] Plan for REST deprecation (if 100% gRPC successful)

### Success Criteria Week 10

- [ ] ✅ Production deployment successful
- [ ] ✅ 100% traffic на gRPC (or staged at agreed level)
- [ ] ✅ Zero critical incidents
- [ ] ✅ Performance improvement confirmed in production
- [ ] ✅ Error rate <0.1%
- [ ] ✅ User satisfaction maintained
- [ ] ✅ Team comfortable with new stack

---

## 📊 Success Metrics

### Performance KPIs

| Metric | Baseline (REST) | Target (gRPC) | Measured |
|--------|----------------|---------------|----------|
| **Lock/Unlock P95 latency** | 250ms | <130ms (-48%) | ⏳ TBD |
| **Batch ops throughput** | 500 ops/sec | >5000 ops/sec (+900%) | ⏳ TBD |
| **Small payload throughput** | 3,500 req/sec | >7,000 req/sec (+100%) | ⏳ TBD |
| **Memory per worker** | 200MB | <130MB (-34%) | ⏳ TBD |
| **CPU usage** | Baseline | <81% (-19%) | ⏳ TBD |

### Business KPIs

| Metric | Target | Measured |
|--------|--------|----------|
| **Infrastructure cost reduction** | -20% (через 6 мес) | ⏳ TBD |
| **User-reported latency complaints** | -50% | ⏳ TBD |
| **System capacity (databases)** | +30% (700 → 910) | ⏳ TBD |
| **Developer velocity** | Maintained | ⏳ TBD |

### Technical Debt Reduction

- [ ] Contract-First для всех сервисов (Proto + OpenAPI)
- [ ] Type safety на всех границах
- [ ] Reduced network hops (HTTP/2 multiplexing)
- [ ] Native streaming support
- [ ] Better observability (gRPC metrics)

---

## 🚨 Risks & Mitigation

### Risk Matrix

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Team learning curve** | MEDIUM | HIGH | Training, pair programming, gradual ramp-up |
| **Production incident** | HIGH | LOW | Staged rollout, comprehensive testing, rollback plan |
| **Performance не улучшается** | MEDIUM | LOW | PoC в Week 1-2 валидирует, бенчмарки до deployment |
| **Breaking changes в Proto** | HIGH | MEDIUM | Buf breaking change detection, versioning strategy |
| **gRPC tooling issues** | LOW | LOW | Используем mature tools (grpc-go, grpcio) |
| **Redis Pub/Sub conflicts** | LOW | LOW | Tested в PoC, Redis остается unchanged |

### Detailed Risk Analysis

#### Risk 1: Team Learning Curve
**Описание:** Команда незнакома с gRPC, Proto files

**Mitigation:**
1. Training session (Week 1): gRPC basics, Proto syntax
2. Pair programming: senior + junior
3. Documentation: internal wiki с примерами
4. Gradual ramp-up: простые endpoints first

**Contingency:** Если >2 недель задержка → рассмотреть FastAPI вместо gRPC

#### Risk 2: Production Incident
**Описание:** gRPC внедрение ломает production

**Mitigation:**
1. Comprehensive testing (Week 8-9)
2. Staged rollout (5% → 100%)
3. Feature flags (easy toggle)
4. Rollback plan (<5 min)
5. On-call rotation 24/7 (Week 10)

**Contingency:** Immediate rollback to REST, post-mortem, fix issues

#### Risk 3: Performance Не Улучшается
**Описание:** gRPC не дает ожидаемого improvement

**Mitigation:**
1. PoC в Week 1-2 validates approach
2. Benchmarking до deployment
3. Performance profiling (pprof)

**Contingency:** Если <20% improvement → остаться на REST, считать proof of concept

#### Risk 4: Breaking Changes в Proto
**Описание:** Proto изменения ломают клиентов

**Mitigation:**
1. Buf breaking change detection в CI
2. Versioning strategy: /v1, /v2
3. Deprecation policy: 3 месяца warning
4. Backward compatibility required

**Contingency:** Hotfix release, rollback проблемных изменений

---

## 📚 Documentation Deliverables

### Technical Docs

1. **Proto Contracts** (`contracts/proto/README.md`)
   - Proto file structure
   - Code generation instructions
   - Versioning strategy

2. **gRPC Integration Guide** (`docs/GRPC_INTEGRATION_GUIDE.md`)
   - How to add new gRPC service
   - Client/server patterns
   - Error handling
   - Testing strategies

3. **API Gateway Architecture** (`docs/architecture/API_GATEWAY_GRPC.md`)
   - REST → gRPC translation
   - Load balancing
   - Health checks
   - Monitoring

4. **Runbooks** (`docs/runbooks/`)
   - Troubleshooting gRPC issues
   - Connection pool tuning
   - Performance debugging
   - Incident response

### Training Materials

1. **gRPC Basics** (презентация + hands-on)
   - Proto syntax
   - Code generation
   - Client/server examples

2. **Migration Guide** (для developers)
   - How to migrate REST endpoint to gRPC
   - Testing checklist
   - Common pitfalls

3. **Operations Guide** (для DevOps)
   - Deployment procedures
   - Monitoring setup
   - Troubleshooting

---

## 🎓 Team Training Plan

### Week 1: gRPC Fundamentals (1 день)

**Topics:**
- Protocol Buffers syntax
- gRPC concepts (unary, streaming)
- Code generation workflow
- Tools: Buf, grpcurl, BloomRPC

**Hands-on:**
- Write simple .proto file
- Generate Go/Python code
- Implement hello-world service

### Week 3: Advanced gRPC (половина дня)

**Topics:**
- Error handling
- Interceptors/middleware
- Connection pooling
- Load balancing
- Monitoring

**Hands-on:**
- Add metrics to gRPC service
- Implement retry logic
- Test connection pool

### Week 8: Testing & Debugging (половина дня)

**Topics:**
- Unit testing gRPC
- Integration testing
- Performance benchmarking (ghz)
- Debugging tools

**Hands-on:**
- Write test для gRPC handler
- Run benchmark
- Debug slow request

---

## 🔄 Post-Migration Tasks

### Immediate (Week 11-12)

- [ ] Monitor production metrics (2 недели)
- [ ] Fix any discovered issues
- [ ] Optimize based on real traffic patterns
- [ ] Update capacity planning
- [ ] Conduct retrospective

### Short-term (Month 2-3)

- [ ] Deprecate REST endpoints (если 100% gRPC successful)
- [ ] Remove backward compatibility code
- [ ] Optimize Proto contracts based on usage
- [ ] Improve monitoring dashboards
- [ ] Write case study

### Long-term (Month 4-6)

- [ ] Evaluate gRPC-Web для Frontend (if needed)
- [ ] Consider GraphQL layer на gRPC (flexibility)
- [ ] Explore gRPC streaming для more use cases
- [ ] Mentor other teams на gRPC adoption

---

## 📝 Decision Log

### Key Decisions

| Date | Decision | Rationale | Owner |
|------|----------|-----------|-------|
| 2025-11-24 | Use gRPC Hybrid (not Full gRPC) | Preserve Frontend DX, minimize risk | Architecture Team |
| 2025-11-24 | Keep Redis Pub/Sub for events | Multiple subscribers (Frontend, monitoring) | Architecture Team |
| TBD | Buf для Proto management | Industry standard, breaking change detection | DevOps |
| TBD | Staged rollout 5% → 100% | Risk mitigation | DevOps |

### Open Questions

- [ ] TLS для gRPC? (use Istio service mesh or manual certs?)
- [ ] Multi-tenancy considerations?
- [ ] gRPC-Web для direct browser calls? (ConnectRPC альтернатива)
- [ ] When to deprecate REST completely? (6 месяцев после 100% gRPC?)

---

## 📞 Contacts & Resources

### Team

| Role | Name | Responsibility |
|------|------|----------------|
| **Tech Lead** | TBD | Overall migration, architecture decisions |
| **Backend Lead** | TBD | Go services (Worker, ras-adapter) |
| **Python Lead** | TBD | Orchestrator FastAPI integration |
| **DevOps Lead** | TBD | Deployment, monitoring, infrastructure |

### External Resources

- [gRPC Official Docs](https://grpc.io/docs/)
- [Buf Documentation](https://buf.build/docs/)
- [LinkedIn gRPC Migration](https://www.infoq.com/news/2024/04/qcon-london-grpc-linkedin/)
- [Netflix gRPC at Scale](https://www.cncf.io/case-studies/netflix/)
- Internal: `docs/GRPC_MIGRATION_ANALYSIS.md`

---

## 📅 Milestones Summary

| Milestone | Target Date | Status | Deliverables |
|-----------|-------------|--------|--------------|
| **M1: Foundation Complete** | Week 2 end | 📋 Planned | Proto contracts, PoC, tooling |
| **M2: Core Services Migrated** | Week 5 end | 📋 Planned | ras-adapter + Worker on gRPC |
| **M3: API Gateway Ready** | Week 7 end | 📋 Planned | REST → gRPC translation |
| **M4: Testing Complete** | Week 9 end | 📋 Planned | All tests pass, benchmarks OK |
| **M5: Production Rollout** | Week 10 end | 📋 Planned | 100% gRPC in production |

---

## 🎉 Success Definition

Migration считается **успешной** если:

1. ✅ **Performance improvement:** >40% latency reduction для Lock/Unlock
2. ✅ **Throughput:** >2x для batch операций
3. ✅ **Reliability:** Error rate <0.1% (same as REST baseline)
4. ✅ **Zero downtime:** Staged rollout без incidents
5. ✅ **Frontend unchanged:** React team не замечает изменений
6. ✅ **Team happy:** Developers комфортно с gRPC

---

**Version:** 1.0
**Last Updated:** 2025-11-24
**Status:** 📋 AWAITING APPROVAL

**Next Steps:**
1. Review roadmap с team
2. Approve timeline и resources
3. Start Week 1: Proto contracts setup
4. Kickoff meeting
