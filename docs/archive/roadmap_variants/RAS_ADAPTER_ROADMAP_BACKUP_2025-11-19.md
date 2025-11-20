# RAS Adapter Roadmap - Unified Architecture

**Version:** 2.0
**Date:** 2025-11-19
**Status:** Design Document - FINAL ARCHITECTURE
**Related:** [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md), [RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md](RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md)

---

## ⚠️ ВАЖНО: Архитектурное изменение (v2.0)

**Изменение от 2025-11-19:** RAS Adapter больше НЕ использует gRPC для коммуникации с Worker!

**Правильная архитектура (v2.0):**
- ✅ Worker общается ТОЛЬКО через **Redis Pub/Sub** (Event-Driven State Machine)
- ✅ RAS Adapter имеет ТОЛЬКО: **REST API** (для external clients) + **Redis Pub/Sub event handlers** (для Worker)
- ❌ **БЕЗ gRPC** - Worker не делает прямых вызовов к RAS Adapter

**Актуальная документация:**
- **[RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md](RAS_ADAPTER_STATE_MACHINE_COMPATIBILITY.md)** - ПОЛНАЯ актуальная архитектура ⭐
- Этот документ содержит старые упоминания gRPC/Hybrid Protocol - игнорируйте их

---

## Executive Summary

Комплексный план по унификации архитектуры микросервисов CommandCenter1C:

1. **RAS Adapter** - слияние cluster-service + ras-grpc-gw в единый сервис
2. **Event-Driven Only** - Worker общается ТОЛЬКО через Redis Pub/Sub (чистая event-driven архитектура)
3. **REST API для external clients** - admin, monitoring, debugging
4. **Distributed Tracing** - OpenTelemetry + Jaeger для мониторинга (future)
5. **Debug Tools** - CLI утилиты (ping, trace, health) (future)

**Проблема:**
- Два сервиса (cluster-service + ras-grpc-gw) делают похожие вещи
- Невозможно отследить запрос через микросервисы
- Нет debugging tools для межсервисной коммуникации
- RAS протокол имеет фундаментальные ограничения (UpdateInfobase не работает)

**Решение:**
- Единый RAS Adapter сервис (Go, порт 8088)
- **Event-Driven Protocol:** Redis Pub/Sub для Worker State Machine
- **REST API:** для external clients ONLY (админы, curl, monitoring)
- **NO gRPC** - Worker не делает прямых вызовов (clean event-driven)
- OpenTelemetry для distributed tracing (optional, later)
- Real-time operation tracking UI (optional, later)

---

## Table of Contents

1. [Текущее состояние](#текущее-состояние)
2. [Целевая архитектура](#целевая-архитектура)
3. [RAS Adapter - Единый сервис](#ras-adapter---единый-сервис)
4. [Event-Driven Protocol (Redis Pub/Sub)](#event-driven-protocol-redis-pubsub)
5. [REST API (External Clients)](#rest-api-external-clients)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Migration Strategy](#migration-strategy)
8. [Risk Analysis](#risk-analysis)
9. [Future Enhancements](#future-enhancements)

---

## Текущее состояние

### Проблемы

#### 1. Два сервиса с дублированием функций

```
┌──────────────────┐        ┌─────────────────┐
│ cluster-service  │        │  ras-grpc-gw    │
│ (Go, port 8088)  │ ────► │ (Go, port 9999) │
│                  │ gRPC   │                 │
│ REST API         │        │ gRPC ↔ RAS      │
│ Business logic   │        │ Protocol proxy  │
└──────────────────┘        └─────────────────┘
```

**Проблемы:**
- ❌ Дублирование кода (оба на Go, обе работают с RAS)
- ❌ Двойной network hop (cluster-service → ras-grpc-gw → RAS)
- ❌ Сложная отладка (два сервиса, два log файла)
- ❌ Две точки отказа (если упадет один - упадет всё)

#### 2. Event-Driven State Machine (IMPLEMENTED)

```
Frontend ──REST──► API Gateway ──REST──► Orchestrator
                                            │
                                            ▼ Celery
                                          Redis
                                            │
                                            ▼ Redis Pub/Sub
Worker State Machine ──commands──► cluster-service Event Handlers
  │                                  │
  │ ◄────events─────────────────────┘
  │                                  │
  │                                  └──gRPC──► ras-grpc-gw
  │
  └──OData/HTTP──► 1C Databases
```

**Текущее состояние:**
- ✅ Worker State Machine (Week 1-2 DONE)
- ✅ cluster-service Event Handlers (Week 2 DONE)
- ✅ Redis Pub/Sub для команд и событий
- ⚠️ cluster-service → ras-grpc-gw (двойной hop, нужно объединить)

#### 3. Отсутствие tracing (FUTURE)

```
Request flow:
Frontend → API Gateway → Orchestrator → Worker → cluster-service → ras-grpc-gw → RAS
   ❓          ❓              ❓           ❓            ❓              ❓          ❓

Where is my request? Why is it slow? Where did it fail?
```

**Проблемы:**
- ❌ Невозможно отследить конкретный запрос через все сервисы
- ❌ При ошибке не понятно где упало
- ❌ Нельзя сравнить fast vs slow requests
- ❌ Debugging = просмотр 7 разных log файлов

#### 4. Отсутствие debug tools

```bash
# Как проверить что Worker может достучаться до cluster-service?
# Нет команды типа:
$ cc1c-debug ping cluster-service
❌ Command not found

# Как проследить путь запроса?
# Нет команды типа:
$ cc1c-debug trace op-67890
❌ Command not found
```

#### 5. RAS Protocol Limitation

```
ERROR: RAS error: unknown type <*serializev1.InfobaseInfo> to create new message
```

**Причина:**
- UpdateInfobase() пытается отправить InfobaseInfo через endpoint.Request()
- RAS binary protocol не поддерживает InfobaseInfo updates
- Метод закомментирован в v8platform protos
- Все тесты используют mocks (никогда не тестировался на real RAS)

**Последствия:**
- ❌ LockInfobase() не работает (вызывает UpdateInfobase)
- ❌ UnlockInfobase() не работает (вызывает UpdateInfobase)
- ❌ Workflow установки расширений зависает на Lock step

---

## Целевая архитектура

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                      (React:5173)                            │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST
                         ▼
┌────────────────────────────────────────────────────────────┐
│                     API Gateway                            │
│                   (Go:8080)                                │
│  - JWT auth                                                │
│  - Rate limiting                                           │
│  - REST → gRPC translation                                 │
└────────────────────────┬───────────────────────────────────┘
                         │ gRPC (internal)
                         ▼
┌────────────────────────────────────────────────────────────┐
│                   Orchestrator                             │
│                 (Django:8000)                              │
│  - Business logic                                          │
│  - Task orchestration                                      │
└────────────┬──────────────────────┬────────────────────────┘
             │ Celery               │ gRPC
             ▼                      ▼
         ┌───────┐            ┌─────────────┐
         │ Redis │            │   Worker    │
         └───┬───┘            │  (Go x2)    │
             │                └──────┬──────┘
             │ Subscribe             │ gRPC (internal)
             └──────────────► ┌──────▼──────────────────────┐
                              │     RAS Adapter             │
                              │     (Go:8088)               │
                              │                             │
                              │ Unified Service:            │
                              │ ✓ cluster-service logic     │
                              │ ✓ ras-grpc-gw proxy         │
                              │ ✓ Dual interface:           │
                              │   - gRPC (internal)         │
                              │   - REST (external/legacy)  │
                              │ ✓ OpenTelemetry traces      │
                              │ ✓ Health checks             │
                              └──────────┬──────────────────┘
                                         │ RAS binary protocol
                                         ▼
                              ┌──────────────────────────┐
                              │   1C RAS Server          │
                              │   (port 1545)            │
                              └──────────────────────────┘
```

### Key Changes

| Компонент | До | После |
|-----------|-------|-------|
| **RAS integration** | cluster-service + ras-grpc-gw (2 сервиса) | RAS Adapter (1 сервис) |
| **Internal protocol** | REST + gRPC (смешанно) | gRPC only |
| **External API** | Нет | REST (для legacy/admin) |
| **Tracing** | Нет | OpenTelemetry + Jaeger |
| **Debug tools** | Нет | cc1c-debug CLI |
| **Monitoring** | Prometheus metrics | Prometheus + Jaeger + Real-time UI |

---

## RAS Adapter - Единый сервис

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      RAS Adapter (Go)                          │
│                      Port: 8088                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌───────────────────┐          ┌───────────────────┐         │
│  │   REST Server     │          │   gRPC Server     │         │
│  │   (Gin)           │          │   (grpc-go)       │         │
│  │                   │          │                   │         │
│  │ External clients  │          │ Internal services │         │
│  │ (curl, admin)     │          │ (Worker, Orchestr)│         │
│  └─────────┬─────────┘          └─────────┬─────────┘         │
│            │                              │                   │
│            └──────────────┬───────────────┘                   │
│                           ▼                                   │
│              ┌────────────────────────┐                       │
│              │   Business Logic       │                       │
│              │   (Service Layer)      │                       │
│              │                        │                       │
│              │ ✓ GetClusters()        │                       │
│              │ ✓ GetInfobases()       │                       │
│              │ ✓ GetSessions()        │                       │
│              │ ✓ LockInfobase()       │  ◄─── NEW IMPL       │
│              │ ✓ UnlockInfobase()     │  ◄─── NEW IMPL       │
│              │ ✓ TerminateSessions()  │                       │
│              └────────────┬───────────┘                       │
│                           │                                   │
│                           ▼                                   │
│              ┌────────────────────────┐                       │
│              │   RAS Client           │                       │
│              │   (v8platform SDK)     │                       │
│              │                        │                       │
│              │ ✓ Connection pooling   │                       │
│              │ ✓ Retry logic          │                       │
│              │ ✓ Circuit breaker      │                       │
│              │ ✓ Health checks        │                       │
│              └────────────┬───────────┘                       │
│                           │                                   │
├───────────────────────────┼───────────────────────────────────┤
│          OpenTelemetry Instrumentation                        │
│          ✓ Traces    ✓ Metrics    ✓ Logs                     │
└───────────────────────────┼───────────────────────────────────┘
                            │ RAS binary protocol (port 1545)
                            ▼
                 ┌──────────────────────┐
                 │   1C RAS Server      │
                 └──────────────────────┘
```

### Code Structure

```
go-services/ras-adapter/
├── cmd/
│   └── main.go                      # Entry point
├── internal/
│   ├── api/
│   │   ├── rest/
│   │   │   ├── router.go            # Gin REST API
│   │   │   ├── clusters.go          # GET /api/v1/clusters
│   │   │   ├── infobases.go         # GET /api/v1/infobases
│   │   │   └── sessions.go          # GET /api/v1/sessions
│   │   └── grpc/
│   │       ├── server.go            # gRPC server
│   │       └── handlers.go          # gRPC handlers
│   ├── service/
│   │   ├── cluster_service.go       # GetClusters, GetInfobases
│   │   ├── infobase_service.go      # Lock, Unlock (NEW IMPL)
│   │   └── session_service.go       # GetSessions, Terminate
│   ├── ras/
│   │   ├── client.go                # RAS client wrapper
│   │   ├── pool.go                  # Connection pool
│   │   ├── retry.go                 # Retry logic
│   │   └── circuit_breaker.go       # Circuit breaker
│   ├── tracing/
│   │   └── instrumentation.go       # OpenTelemetry setup
│   └── config/
│       └── config.go                # Configuration
├── pkg/
│   └── proto/
│       └── rasadapter/
│           ├── cluster.proto        # Cluster messages
│           ├── infobase.proto       # Infobase messages
│           └── session.proto        # Session messages
└── go.mod
```

### New Implementation: LockInfobase & UnlockInfobase

**Проблема:** UpdateInfobase() не работает через RAS binary protocol

**Решение:** Использовать специальные RAS команды напрямую

```go
// go-services/ras-adapter/internal/service/infobase_service.go
package service

import (
	"context"
	"fmt"

	"github.com/v8platform/api/ras"
	"go.uber.org/zap"
)

type InfobaseService struct {
	rasClient *ras.Client
	logger    *zap.Logger
}

// LockInfobase locks scheduled jobs for an infobase
// Uses direct RAS commands instead of UpdateInfobase
func (s *InfobaseService) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	s.logger.Info("locking infobase scheduled jobs",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Authenticate cluster
	if err := s.rasClient.Authenticate(clusterID, "", ""); err != nil {
		return fmt.Errorf("cluster auth failed: %w", err)
	}

	// Get current infobase info
	infobase, err := s.rasClient.GetInfobase(clusterID, infobaseID)
	if err != nil {
		return fmt.Errorf("get infobase failed: %w", err)
	}

	// Modify scheduled jobs deny flag
	infobase.ScheduledJobsDeny = true

	// Apply changes using RAS RegInfoBase command
	// This uses a different RAS endpoint than UpdateInfobase
	if err := s.rasClient.RegInfoBase(clusterID, infobase); err != nil {
		return fmt.Errorf("lock scheduled jobs failed: %w", err)
	}

	s.logger.Info("infobase locked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	return nil
}

// UnlockInfobase unlocks scheduled jobs for an infobase
func (s *InfobaseService) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	s.logger.Info("unlocking infobase scheduled jobs",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	// Authenticate cluster
	if err := s.rasClient.Authenticate(clusterID, "", ""); err != nil {
		return fmt.Errorf("cluster auth failed: %w", err)
	}

	// Get current infobase info
	infobase, err := s.rasClient.GetInfobase(clusterID, infobaseID)
	if err != nil {
		return fmt.Errorf("get infobase failed: %w", err)
	}

	// Modify scheduled jobs deny flag
	infobase.ScheduledJobsDeny = false

	// Apply changes
	if err := s.rasClient.RegInfoBase(clusterID, infobase); err != nil {
		return fmt.Errorf("unlock scheduled jobs failed: %w", err)
	}

	s.logger.Info("infobase unlocked successfully",
		zap.String("cluster_id", clusterID),
		zap.String("infobase_id", infobaseID))

	return nil
}
```

**Ключевое отличие:**
- ❌ `UpdateInfobase()` → endpoint.Request(InfobaseInfo) → RAS error
- ✅ `RegInfoBase()` → специальная RAS команда → работает

---

## Hybrid Protocol Strategy

### Зачем два протокола?

#### gRPC (Internal Communication)

**Use cases:**
- Worker → RAS Adapter
- Orchestrator → RAS Adapter (future)
- Service-to-service communication

**Преимущества:**
- ✅ Высокая производительность (binary protocol, HTTP/2)
- ✅ Автоматическая кодогенерация (protobuf)
- ✅ Streaming support (future: watch clusters)
- ✅ Встроенный load balancing
- ✅ Strong typing

**Недостатки:**
- ❌ Требует gRPC клиент (не curl/browser)
- ❌ Сложнее debugging (нужен grpcurl)

#### REST (External Access)

**Use cases:**
- Admin scripts (bash, curl)
- Third-party integrations
- Browser-based tools (Swagger UI)
- Legacy clients migration

**Преимущества:**
- ✅ Human-friendly (JSON, HTTP status codes)
- ✅ Easy debugging (curl, Postman)
- ✅ Browser compatible
- ✅ No special client needed

**Недостатки:**
- ❌ Медленнее gRPC (JSON parsing, HTTP/1.1)
- ❌ Нет type safety без OpenAPI codegen

### Implementation

#### Dual Server Setup

```go
// go-services/ras-adapter/cmd/main.go
package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/commandcenter1c/ras-adapter/internal/api/grpc"
	"github.com/commandcenter1c/ras-adapter/internal/api/rest"
	"github.com/commandcenter1c/ras-adapter/internal/service"
	"go.uber.org/zap"
	"golang.org/x/sync/errgroup"
)

func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	// Initialize services
	clusterSvc := service.NewClusterService(...)
	infobaseSvc := service.NewInfobaseService(...)
	sessionSvc := service.NewSessionService(...)

	// Start gRPC server (internal communication)
	grpcServer := grpc.NewServer(clusterSvc, infobaseSvc, sessionSvc, logger)
	grpcListener, err := net.Listen("tcp", ":9090")
	if err != nil {
		logger.Fatal("Failed to listen gRPC", zap.Error(err))
	}

	// Start REST server (external access)
	restServer := rest.NewServer(clusterSvc, infobaseSvc, sessionSvc, logger)
	httpServer := &http.Server{
		Addr:    ":8088",
		Handler: restServer.Router(),
	}

	// Graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	g, ctx := errgroup.WithContext(ctx)

	// Run gRPC server
	g.Go(func() error {
		logger.Info("Starting gRPC server", zap.String("addr", ":9090"))
		return grpcServer.Serve(grpcListener)
	})

	// Run REST server
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

		// Stop gRPC server
		grpcServer.GracefulStop()

		return nil
	})

	if err := g.Wait(); err != nil {
		logger.Fatal("Server error", zap.Error(err))
	}
}
```

#### REST API Specification

```yaml
# openapi.yaml
openapi: 3.0.0
info:
  title: RAS Adapter REST API
  version: 1.0.0
  description: External REST API for RAS operations

paths:
  /api/v1/clusters:
    get:
      summary: Get all clusters
      parameters:
        - name: server
          in: query
          required: true
          schema:
            type: string
          example: localhost:1545
      responses:
        '200':
          description: List of clusters
          content:
            application/json:
              schema:
                type: object
                properties:
                  clusters:
                    type: array
                    items:
                      $ref: '#/components/schemas/Cluster'

  /api/v1/infobases:
    get:
      summary: Get all infobases
      parameters:
        - name: server
          in: query
          required: true
          schema:
            type: string
        - name: cluster_id
          in: query
          required: true
          schema:
            type: string
      responses:
        '200':
          description: List of infobases

  /api/v1/infobases/{infobaseId}/lock:
    post:
      summary: Lock infobase scheduled jobs
      parameters:
        - name: infobaseId
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                cluster_id:
                  type: string
                scheduled_jobs_deny:
                  type: boolean
                  default: true
      responses:
        '200':
          description: Lock successful

  /api/v1/infobases/{infobaseId}/unlock:
    post:
      summary: Unlock infobase scheduled jobs
      # ... similar to lock

components:
  schemas:
    Cluster:
      type: object
      properties:
        uuid:
          type: string
        name:
          type: string
        server:
          type: string
```

#### gRPC Proto Definitions

```protobuf
// pkg/proto/rasadapter/infobase.proto
syntax = "proto3";

package rasadapter;

option go_package = "github.com/commandcenter1c/ras-adapter/pkg/proto/rasadapter";

service InfobaseService {
  // Lock scheduled jobs for an infobase
  rpc LockInfobase(LockInfobaseRequest) returns (LockInfobaseResponse);

  // Unlock scheduled jobs for an infobase
  rpc UnlockInfobase(UnlockInfobaseRequest) returns (UnlockInfobaseResponse);

  // Get all infobases for a cluster
  rpc GetInfobases(GetInfobasesRequest) returns (GetInfobasesResponse);
}

message LockInfobaseRequest {
  string cluster_id = 1;
  string infobase_id = 2;
  bool scheduled_jobs_deny = 3; // Default: true
}

message LockInfobaseResponse {
  bool success = 1;
  string message = 2;
}

message UnlockInfobaseRequest {
  string cluster_id = 1;
  string infobase_id = 2;
}

message UnlockInfobaseResponse {
  bool success = 1;
  string message = 2;
}

message GetInfobasesRequest {
  string cluster_id = 1;
}

message GetInfobasesResponse {
  repeated Infobase infobases = 1;
}

message Infobase {
  string uuid = 1;
  string name = 2;
  string description = 3;
  bool scheduled_jobs_deny = 4;
  bool sessions_deny = 5;
}
```

---

## Distributed Tracing & Monitoring

**Детальная документация:** [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md)

### Quick Summary

#### OpenTelemetry Integration

**All services instrumented:**
```go
// Initialize OpenTelemetry in RAS Adapter
import (
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/jaeger"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func initTracing() {
	exporter, _ := jaeger.New(jaeger.WithCollectorEndpoint(
		jaeger.WithEndpoint("http://localhost:14268/api/traces"),
	))

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
	)

	otel.SetTracerProvider(tp)
}
```

#### Correlation ID Propagation

```
Frontend → API Gateway → Orchestrator → Worker → RAS Adapter
  │            │              │            │          │
  └── op-123 ──┴──── op-123 ──┴─── op-123 ─┴─ op-123 ┘

Every log statement includes:
- operation_id: op-123
- correlation_id: corr-db-456-123-1234567890
- trace_id: abc123def456 (OpenTelemetry)
- span_id: def456ghi789
```

#### Real-Time Visualization

**Aggregate View (Service Mesh):**
```
Frontend → API Gateway → Orchestrator → Worker → RAS Adapter
  20 ops      20 recv       20 queue      18 active    5 locks
  P95: 45ms   P95: 50ms     15 pending    2 failed     Avg: 1.2s
```

**Trace View (Individual Operation):**
```
Operation op-67890:
├─ Frontend: 0.02s
├─ API Gateway: 0.05s
├─ Orchestrator: 0.15s
└─ Worker: 2.8s
   ├─ Lock: 0.8s ✓
   ├─ Install: 1.5s ✓
   └─ Unlock: 0.5s ✓
```

---

## Debug Tools

### CLI Tool: cc1c-debug

```bash
# Ping service (check availability)
$ cc1c-debug ping ras-adapter
✓ ras-adapter is reachable at localhost:8088
  Latency: 5ms
  Health: OK

# Trace operation (show path through services)
$ cc1c-debug trace op-67890
Operation: op-67890
Status: Success
Duration: 3.2s

Path:
Frontend (0.02s)
  → API Gateway (0.05s)
    → Orchestrator (0.15s)
      → Worker (2.8s)
        → RAS Adapter (1.5s)
          → RAS Server (1.2s)

# Health check all services
$ cc1c-debug health
┌─────────────────┬────────┬──────────┬─────────┐
│ Service         │ Status │ Latency  │ Version │
├─────────────────┼────────┼──────────┼─────────┤
│ Frontend        │ ✓      │ 2ms      │ v1.0.0  │
│ API Gateway     │ ✓      │ 5ms      │ v1.2.3  │
│ Orchestrator    │ ✓      │ 8ms      │ v1.0.5  │
│ Worker          │ ✓      │ 3ms      │ v1.1.0  │
│ RAS Adapter     │ ✓      │ 6ms      │ v2.0.0  │
│ RAS Server      │ ✓      │ 12ms     │ 8.3.27  │
└─────────────────┴────────┴──────────┴─────────┘

# Show service dependencies
$ cc1c-debug deps ras-adapter
RAS Adapter (v2.0.0) depends on:
  ← Worker (gRPC client)
  ← Orchestrator (gRPC client, future)
  → RAS Server (RAS binary protocol)

Incoming connections: 2 (Worker x2 replicas)
Outgoing connections: 15 (RAS connection pool)
```

### Implementation

```go
// cmd/cc1c-debug/main.go
package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "cc1c-debug",
	Short: "CommandCenter1C debug tool",
}

var pingCmd = &cobra.Command{
	Use:   "ping [service]",
	Short: "Ping a service to check availability",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		service := args[0]
		// ... ping implementation
	},
}

var traceCmd = &cobra.Command{
	Use:   "trace [operation-id]",
	Short: "Trace an operation through all services",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		operationID := args[0]
		// Query Jaeger API
		// Display trace tree
	},
}

var healthCmd = &cobra.Command{
	Use:   "health",
	Short: "Check health of all services",
	Run: func(cmd *cobra.Command, args []string) {
		// Check all services
		// Display table
	},
}

func main() {
	rootCmd.AddCommand(pingCmd)
	rootCmd.AddCommand(traceCmd)
	rootCmd.AddCommand(healthCmd)

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
```

---

## Implementation Roadmap

### MVP (4 weeks)

#### Week 1: RAS Adapter Foundation

**Goal:** Create RAS Adapter with basic functionality

**Tasks:**
- [ ] Create `go-services/ras-adapter` project structure
- [ ] Copy business logic from cluster-service
- [ ] Copy RAS client from ras-grpc-gw
- [ ] Implement dual servers (gRPC + REST)
- [ ] Add health check endpoints
- [ ] Unit tests (coverage > 70%)

**Deliverable:** RAS Adapter runs standalone, passes health checks

#### Week 2: New Lock/Unlock Implementation

**Goal:** Fix LockInfobase/UnlockInfobase using RegInfoBase

**Tasks:**
- [ ] Research RAS RegInfoBase command
- [ ] Implement new LockInfobase() using RegInfoBase
- [ ] Implement new UnlockInfobase() using RegInfoBase
- [ ] Integration tests with real RAS server
- [ ] Verify extension install workflow works end-to-end

**Deliverable:** Lock/Unlock работает корректно

#### Week 3: Worker Integration

**Goal:** Migrate Worker to use RAS Adapter gRPC

**Tasks:**
- [ ] Generate gRPC client code from protos
- [ ] Update Worker dual_mode.go to call RAS Adapter gRPC
- [ ] Remove HTTP client dependencies
- [ ] Update error handling
- [ ] Integration tests

**Deliverable:** Worker → RAS Adapter gRPC работает

#### Week 4: Deploy & Validate

**Goal:** Deploy to development, validate, deprecate old services

**Tasks:**
- [ ] Update docker-compose.yml
- [ ] Deploy RAS Adapter
- [ ] Smoke tests
- [ ] Performance comparison (old vs new)
- [ ] Stop cluster-service and ras-grpc-gw
- [ ] Update documentation

**Deliverable:** RAS Adapter deployed to development

#### Week 4.5: Manual Endpoint Testing ⭐ CRITICAL GATE

**Goal:** Comprehensive manual validation of all RAS Adapter endpoints before proceeding to tracing

**⚠️ GATE CONDITION:** ALL tests must PASS before proceeding to Week 5 (Tracing Infrastructure)

**Tasks:**
- [ ] Run comprehensive manual testing checklist
- [ ] Test ALL REST API endpoints (GET /clusters, /infobases, /sessions, POST /lock, /unlock, /terminate)
- [ ] Test ALL gRPC endpoints (LockInfobase, UnlockInfobase, GetInfobases)
- [ ] Verify Lock/Unlock NEW IMPLEMENTATION (RegInfoBase) works correctly
- [ ] Test end-to-end workflows (Lock → Verify → Unlock)
- [ ] Test concurrent requests (10+ parallel lock requests)
- [ ] Test REST vs gRPC consistency
- [ ] Performance validation (latency, throughput)
- [ ] Error handling validation
- [ ] Document test results and sign-off

**Testing Checklist:** [RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md)

**Sign-off Required:**
```
Tested by: _______________________
Date: _______________________
Status: ✅ PASSED / ❌ FAILED

All endpoints working: [ ] YES [ ] NO
Lock/Unlock working: [ ] YES [ ] NO
Performance acceptable: [ ] YES [ ] NO
Ready to proceed: [ ] YES [ ] NO
```

**Deliverable:**
- ✅ All manual tests PASSED
- ✅ Test report documented
- ✅ Sign-off received
- ✅ Green light to proceed to Week 5

**If tests FAIL:**
- ❌ DO NOT proceed to Week 5
- Fix identified issues
- Re-run manual testing checklist
- Obtain sign-off before continuing

---

### Full (8 weeks)

#### Week 1-4: MVP (см. выше)

#### Week 5-6: Distributed Tracing

**Goal:** OpenTelemetry + Jaeger integration

**Tasks:**
- [ ] Deploy Jaeger (docker-compose.tracing.yml)
- [ ] Instrument all services with OpenTelemetry
- [ ] Correlation ID propagation (HTTP headers, gRPC metadata)
- [ ] Structured logging with trace_id
- [ ] Test: operation flow visible in Jaeger UI

**Deliverable:** Distributed tracing работает

**Детали:** См. [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md) Phase 1-2

#### Week 7: Metrics & Real-Time UI

**Goal:** Prometheus metrics + WebSocket aggregator

**Tasks:**
- [ ] Add Prometheus metrics to all Go services
- [ ] Build metrics-aggregator service (WebSocket)
- [ ] Frontend: ServiceMeshMonitor component
- [ ] Frontend: useServiceMetrics() hook
- [ ] Test: real-time updates in UI

**Deliverable:** Service Mesh Monitor UI работает

**Детали:** См. [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md) Phase 3-5

#### Week 8: Debug Tools & Polish

**Goal:** cc1c-debug CLI + documentation

**Tasks:**
- [ ] Implement cc1c-debug ping
- [ ] Implement cc1c-debug trace (query Jaeger API)
- [ ] Implement cc1c-debug health
- [ ] Implement cc1c-debug deps
- [ ] User guide: debugging operations
- [ ] Admin guide: RAS Adapter configuration

**Deliverable:** cc1c-debug CLI готов, документация обновлена

---

## Migration Strategy

### Phase 1: Parallel Deployment (Week 1)

**Deploy RAS Adapter alongside existing services**

```yaml
# docker-compose.yml
services:
  # OLD (keep running)
  cluster-service:
    # ...
  ras-grpc-gw:
    # ...

  # NEW (deploy in parallel)
  ras-adapter:
    build: ./go-services/ras-adapter
    ports:
      - "8088:8088"  # Conflict! Change old cluster-service to 8089
      - "9090:9090"  # gRPC
    environment:
      - RAS_SERVER=localhost:1545
```

**Configuration:**
```bash
# Temporarily change cluster-service port
export CLUSTER_SERVICE_PORT=8089

# RAS Adapter uses 8088 (final port)
export RAS_ADAPTER_REST_PORT=8088
export RAS_ADAPTER_GRPC_PORT=9090
```

### Phase 2: Worker Migration (Week 3)

**Update Worker to use RAS Adapter gRPC**

```go
// go-services/worker/internal/processor/dual_mode.go

// OLD: HTTP client to cluster-service:8089
// httpClient := &http.Client{...}
// resp, err := httpClient.Post("http://localhost:8089/api/v1/infobases/lock", ...)

// NEW: gRPC client to ras-adapter:9090
import rasadapter "github.com/commandcenter1c/ras-adapter/pkg/proto/rasadapter"

rasClient := rasadapter.NewInfobaseServiceClient(conn)
resp, err := rasClient.LockInfobase(ctx, &rasadapter.LockInfobaseRequest{
	ClusterId:         clusterID,
	InfobaseId:        infobaseID,
	ScheduledJobsDeny: true,
})
```

### Phase 3: Validation (Week 4)

**Run both systems in parallel, compare results**

```bash
# Test workflow with OLD services
$ ./test-extension-install.sh --use-old
Operation: op-old-123
Status: FAILED (lock failed with status 500)

# Test workflow with NEW RAS Adapter
$ ./test-extension-install.sh --use-new
Operation: op-new-456
Status: SUCCESS
Duration: 3.2s
```

### Phase 4: Cutover (Week 4)

**Switch all traffic to RAS Adapter**

```yaml
# docker-compose.yml
services:
  # Remove old services
  # cluster-service: REMOVED
  # ras-grpc-gw: REMOVED

  # RAS Adapter is primary
  ras-adapter:
    # ...
```

### Phase 5: Deprecation (After Week 4)

**Archive old services**

```bash
# Move old code to archive
git mv go-services/cluster-service go-services/archive/cluster-service
git mv ../ras-grpc-gw ../ras-grpc-gw-archive

# Update documentation
echo "DEPRECATED: Use ras-adapter instead" > go-services/archive/cluster-service/README.md
```

---

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **RegInfoBase doesn't work** | Low | Critical | Technical spike (Week 2, Day 1-2): test on real RAS |
| **gRPC performance issues** | Low | Medium | Benchmark before migration, add connection pooling |
| **Breaking changes in Worker** | Medium | High | Feature flag: allow fallback to old HTTP client |
| **RAS connection pool bugs** | Medium | Medium | Extensive load testing, circuit breaker pattern |
| **Jaeger overhead** | Low | Low | Sampling rate 10% in production (100% in dev) |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Downtime during migration** | Medium | High | Parallel deployment, gradual cutover, rollback plan |
| **Lost traces during outage** | Low | Low | Jaeger buffers traces, retry on failure |
| **Debug tool requires training** | High | Low | User guide, video tutorial, CLI help |
| **Increased complexity** | Medium | Medium | Comprehensive documentation, runbooks |

### Rollback Plan

**If RAS Adapter fails in production:**

```bash
# 1. Revert docker-compose.yml
git checkout HEAD~1 docker-compose.yml

# 2. Restart old services
docker-compose up -d cluster-service ras-grpc-gw

# 3. Revert Worker to HTTP client
git revert <commit-hash-of-grpc-migration>

# 4. Rebuild and deploy
./scripts/dev/restart-all.sh
```

**Feature flag for gradual rollout:**

```go
// go-services/worker/internal/config/config.go
type Config struct {
	UseRASAdapter bool `env:"USE_RAS_ADAPTER" envDefault:"false"`
}

// go-services/worker/internal/processor/dual_mode.go
func (dm *DualModeProcessor) lockInfobase(...) error {
	if dm.config.UseRASAdapter {
		// Call RAS Adapter gRPC
		return dm.rasAdapterClient.LockInfobase(...)
	} else {
		// Call old cluster-service HTTP
		return dm.clusterServiceHTTP.LockInfobase(...)
	}
}
```

---

## Success Metrics

### Performance Metrics

| Metric | Current | Target (MVP) | Target (Full) |
|--------|---------|--------------|---------------|
| **Lock/Unlock Success Rate** | 0% (broken) | 99% | 99.9% |
| **Extension Install Success Rate** | 50% (fails at lock) | 95% | 99% |
| **Lock/Unlock Latency P95** | N/A | < 2s | < 1s |
| **Network Hops (Worker → RAS)** | 2 (cluster-service → ras-grpc-gw) | 1 | 1 |
| **Number of Services** | 7 | 6 (-1) | 6 |

### Observability Metrics

| Metric | Current | Target (MVP) | Target (Full) |
|--------|---------|--------------|---------------|
| **Trace Coverage** | 0% | 50% (Worker only) | 100% (all services) |
| **Time to Debug** | 30+ min (7 log files) | 15 min | 5 min (click operation → see trace) |
| **Mean Time to Detect (MTTD)** | 10+ min | 5 min | 1 min (real-time alerts) |
| **Mean Time to Resolve (MTTR)** | 60+ min | 30 min | 15 min (trace + logs + metrics) |

### Business Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Operations per minute** | ~10 (limited by failures) | 100+ |
| **Developer productivity** | Baseline | +50% (faster debugging) |
| **User satisfaction** | Low (frequent failures) | High (reliable, visible progress) |

---

## Next Steps

### Decision Point

**Выбери roadmap:**
- [ ] **MVP (4.5 weeks)** - Fix Lock/Unlock, basic RAS Adapter, + manual validation gate, no tracing
- [ ] **Full (8 weeks)** - MVP + Distributed Tracing + Real-Time UI + Debug Tools
- [ ] **Hybrid (8.5 weeks)** ⭐ RECOMMENDED - MVP + manual validation + basic tracing + basic UI

### Immediate Actions (если MVP)

1. **Week 1, Day 1:**
   - [ ] Create `go-services/ras-adapter` directory structure
   - [ ] Copy business logic from cluster-service
   - [ ] Setup dual servers (gRPC + REST)

2. **Week 2, Day 1-2 (Technical Spike):**
   - [ ] Research RAS RegInfoBase command
   - [ ] Test Lock/Unlock with RegInfoBase on real RAS server
   - [ ] Validate: extension install workflow works end-to-end

3. **Week 3:**
   - [ ] Migrate Worker to RAS Adapter gRPC
   - [ ] Integration tests

4. **Week 4:**
   - [ ] Deploy, validate, deprecate old services

5. **Week 4.5 (CRITICAL GATE):**
   - [ ] Run [RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md)
   - [ ] Test ALL endpoints (REST + gRPC)
   - [ ] Verify Lock/Unlock works correctly
   - [ ] Obtain sign-off before proceeding

### Immediate Actions (если Full)

1. **Week 1-4:** MVP tasks (см. выше)
2. **Week 5:** Deploy Jaeger, instrument services
3. **Week 6:** Correlation ID propagation
4. **Week 7:** Metrics + Real-Time UI
5. **Week 8:** Debug tools + documentation

---

## References

- **[RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md)** - Comprehensive endpoint testing (Week 4.5) ⭐
- [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md) - Детальный план tracing & monitoring (10 недель)
- [OBSERVABILITY_QUICKSTART.md](OBSERVABILITY_QUICKSTART.md) - Quick Start для выбора стратегии
- [EVENT_DRIVEN_ARCHITECTURE.md](EVENT_DRIVEN_ARCHITECTURE.md) - Event-Driven State Machine (будущее)
- [ROADMAP.md](../ROADMAP.md) - Основной roadmap проекта (Balanced Approach)
- [v8platform/protos](https://github.com/v8platform/protos) - RAS protobuf definitions
- [OpenTelemetry Go](https://opentelemetry.io/docs/instrumentation/go/) - Tracing documentation
- [Jaeger](https://www.jaegertracing.io/) - Distributed tracing backend

---

**Version History:**

- v1.1 (2025-11-19): Added Week 4.5 manual testing gate
  - Added comprehensive manual testing checklist
  - Updated MVP roadmap: 4 weeks → 4.5 weeks
  - Updated Hybrid roadmap: 8 weeks → 8.5 weeks
  - Added sign-off requirement before Week 5
  - Risk level lowered: Medium → Very Low
- v1.0 (2025-11-19): Initial version
  - RAS Adapter architecture
  - Hybrid Protocol Strategy
  - MVP (4 weeks) + Full (8 weeks) roadmaps
  - New Lock/Unlock implementation plan
  - Integration with REAL_TIME_OPERATION_TRACKING.md

**Authors:** AI Architect + AI Orchestrator

**Status:** ✅ Ready for Review
