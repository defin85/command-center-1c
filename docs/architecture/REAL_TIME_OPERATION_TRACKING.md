# Real-Time Operation Tracking & Distributed Tracing

**Version:** 1.0
**Date:** 2025-11-19
**Status:** Design Document

## Executive Summary

Реализация real-time трекинга операций с двумя уровнями визуализации:

1. **Aggregate View** - общая картина: сколько заданий где находится (real-time)
2. **Trace View** - судьба конкретного задания: полный путь через все микросервисы

**Цель:** Видеть движение каждой операции через микросервисную архитектуру в режиме реального времени, как в сетевом мониторе.

---

## Table of Contents

1. [Архитектура](#архитектура)
2. [Aggregate View - Общая картина](#aggregate-view---общая-картина)
3. [Trace View - Судьба задания](#trace-view---судьба-задания)
4. [Технический Stack](#технический-stack)
5. [Implementation Roadmap](#implementation-roadmap)
6. [API Specification](#api-specification)
7. [UI Components](#ui-components)
8. [Integration Points](#integration-points)

---

## Архитектура

### Три уровня отслеживания

```
┌─────────────────────────────────────────────────────────────────┐
│                    Level 1: Metrics (Aggregate)                 │
│  OpenTelemetry Metrics → Prometheus → Grafana / Custom UI       │
│  Real-time counts, rates, throughput                            │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Level 2: Traces (Individual)                 │
│  OpenTelemetry Traces → Jaeger → Custom Trace Viewer            │
│  Individual operation flow through services                     │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Level 3: Logs (Debug)                        │
│  Structured logs with correlation ID → Loki / ClickHouse        │
│  Detailed debug info for troubleshooting                        │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│  ┌────────────────────┐          ┌─────────────────────┐        │
│  │  Service Mesh      │          │  Operation Trace    │        │
│  │  Monitor           │          │  Viewer             │        │
│  │  (Aggregate View)  │          │  (Trace View)       │        │
│  └────────┬───────────┘          └─────────┬───────────┘        │
└───────────┼──────────────────────────────────┼──────────────────┘
            │                                  │
            │ WebSocket                        │ HTTP API
            │                                  │
┌───────────▼──────────────────────────────────▼──────────────────┐
│                    Backend Services Layer                        │
│                                                                  │
│  ┌──────────────────┐        ┌─────────────────────┐           │
│  │ Metrics Collector│        │ Jaeger Query API    │           │
│  │ (Go service)     │        │ (port 16686)        │           │
│  └────────┬─────────┘        └─────────┬───────────┘           │
│           │                            │                        │
│           │ queries                    │ queries                │
│           ▼                            ▼                        │
│  ┌──────────────┐            ┌────────────────┐                │
│  │ Prometheus   │            │ Jaeger Backend │                │
│  │ (port 9090)  │            │ (port 14268)   │                │
│  └──────┬───────┘            └────────┬───────┘                │
└─────────┼──────────────────────────────┼────────────────────────┘
          │                              │
          │ scrape metrics              │ receive traces
          │                              │
┌─────────▼──────────────────────────────▼────────────────────────┐
│              Application Services (Instrumented)                 │
│                                                                  │
│  Frontend → API Gateway → Orchestrator → Worker → RAS Adapter   │
│     │            │             │            │          │         │
│     └────────────┴─────────────┴────────────┴──────────┘         │
│                    OpenTelemetry SDK                             │
│            (Metrics + Traces + Correlation IDs)                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Aggregate View - Общая картина

### User Story

**Как администратор,** я хочу видеть общую картину движения операций через микросервисы в режиме реального времени, чтобы быстро оценить загрузку системы и обнаружить проблемы.

### UI Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│  Service Mesh Monitor                          Last 5 minutes   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│        ┌────────────┐                                            │
│        │  Frontend  │                                            │
│        │  (React)   │                                            │
│        │            │                                            │
│        │ ↓ 20 ops   │ ◄─── Click → Show list of 20 operations  │
│        │ ↑ 18 resp  │                                            │
│        └──────┬─────┘                                            │
│               │                                                  │
│        ┌──────▼──────┐                                           │
│        │ API Gateway │                                           │
│        │   (Go)      │                                           │
│        │             │                                           │
│        │ ↓ 20 recv   │                                           │
│        │ → 20 fwd    │                                           │
│        │ Latency: 50ms P95                                      │
│        └──────┬──────┘                                           │
│               │                                                  │
│     ┌─────────┴──────────┐                                      │
│     │                    │                                      │
│ ┌───▼──────┐      ┌──────▼─────┐                               │
│ │Orchestr. │      │   Worker   │                               │
│ │(Django)  │      │ (Go x2)    │                               │
│ │          │      │            │                               │
│ │ ↓ 20 recv│      │ ⚡ 18 active│ ◄─── Click → Show active tasks│
│ │ → 20 queue│      │ ✗ 2 failed │ ◄─── Click → Show failed tasks│
│ └───┬──────┘      └──────┬─────┘                               │
│     │                    │                                      │
│     │              ┌─────▼─────┐                                │
│     │              │RAS Adapter│                                │
│     │              │   (Go)    │                                │
│     │              │           │                                │
│     │              │ ↓ 5 lock  │                                │
│     │              │ ⚙ Avg: 1.2s                                │
│     │              └───────────┘                                │
│     │                                                            │
│     └─────► ┌──────────────┐                                    │
│             │ Redis Queue  │                                    │
│             │ 📦 15 pending│ ◄─── Click → Show pending tasks   │
│             └──────────────┘                                    │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Legend:                                                         │
│  ⚡ Active  ✓ Success  ✗ Failed  📦 Queued  ⚙ Processing       │
└─────────────────────────────────────────────────────────────────┘
```

### Metrics to Collect

#### 1. Frontend Metrics
```typescript
// Prometheus metrics format
frontend_operations_initiated_total{user="admin"} 20
frontend_operations_completed_total{status="success"} 18
frontend_operations_completed_total{status="error"} 2
frontend_active_sessions_total 5
```

#### 2. API Gateway Metrics
```go
// go-services/api-gateway/internal/metrics/metrics.go
var (
	RequestsReceived = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "api_gateway_requests_received_total",
			Help: "Total number of requests received",
		},
		[]string{"method", "path"},
	)

	RequestsForwarded = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "api_gateway_requests_forwarded_total",
			Help: "Total number of requests forwarded to orchestrator",
		},
		[]string{"destination"},
	)

	RequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "api_gateway_request_duration_seconds",
			Help: "Request duration in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path", "status"},
	)

	ActiveRequests = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "api_gateway_active_requests",
			Help: "Number of requests currently being processed",
		},
	)
)
```

#### 3. Orchestrator Metrics
```python
# orchestrator/apps/operations/metrics.py
from prometheus_client import Counter, Gauge, Histogram

operations_created = Counter(
    'orchestrator_operations_created_total',
    'Total number of operations created',
    ['operation_type']
)

operations_queued = Counter(
    'orchestrator_operations_queued_total',
    'Total number of operations queued to Celery',
    ['operation_type']
)

celery_queue_depth = Gauge(
    'orchestrator_celery_queue_depth',
    'Number of tasks in Celery queue',
    ['queue_name']
)
```

#### 4. Worker Metrics
```go
// go-services/worker/internal/metrics/metrics.go
var (
	TasksReceived = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_tasks_received_total",
			Help: "Total number of tasks received from Redis",
		},
		[]string{"operation_type"},
	)

	TasksActive = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "worker_tasks_active",
			Help: "Number of tasks currently being processed",
		},
		[]string{"operation_type"},
	)

	TasksCompleted = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_tasks_completed_total",
			Help: "Total number of tasks completed",
		},
		[]string{"operation_type", "status"},
	)

	TaskDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "worker_task_duration_seconds",
			Help: "Task processing duration in seconds",
			Buckets: []float64{0.1, 0.5, 1, 2, 5, 10, 30, 60},
		},
		[]string{"operation_type"},
	)
)
```

#### 5. RAS Metrics

RAS метрики публикуются самим Worker (direct RAS). См. `go-services/worker/internal/metrics/`.

### Real-Time Updates via WebSocket

#### Backend: Metrics Aggregator Service

```go
// go-services/metrics-aggregator/main.go
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
	"github.com/prometheus/client_golang/api"
	v1 "github.com/prometheus/client_golang/api/prometheus/v1"
)

type ServiceMetrics struct {
	Service           string  `json:"service"`
	RequestsReceived  int64   `json:"requests_received"`
	RequestsForwarded int64   `json:"requests_forwarded"`
	ActiveRequests    int64   `json:"active_requests"`
	FailedRequests    int64   `json:"failed_requests"`
	AvgLatency        float64 `json:"avg_latency"`
	P95Latency        float64 `json:"p95_latency"`
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

func main() {
	http.HandleFunc("/ws/metrics", handleMetricsWebSocket)
	log.Fatal(http.ListenAndServe(":8090", nil))
}

func handleMetricsWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade error:", err)
		return
	}
	defer conn.Close()

	// Create Prometheus API client
	client, err := api.NewClient(api.Config{
		Address: "http://localhost:9090",
	})
	if err != nil {
		log.Println("Prometheus client error:", err)
		return
	}
	v1api := v1.NewAPI(client)

	// Send metrics every 2 seconds
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		metrics, err := collectMetrics(v1api)
		if err != nil {
			log.Println("Collect metrics error:", err)
			continue
		}

		err = conn.WriteJSON(metrics)
		if err != nil {
			log.Println("Write error:", err)
			break
		}
	}
}

func collectMetrics(api v1.API) ([]ServiceMetrics, error) {
	ctx := context.Background()

	// Query Prometheus for all service metrics
	queries := map[string]string{
		"frontend_received":    `sum(rate(frontend_operations_initiated_total[5m]))`,
		"api_gateway_received": `sum(rate(api_gateway_requests_received_total[5m]))`,
		"worker_active":        `sum(worker_tasks_active)`,
		"worker_failed":        `sum(rate(worker_tasks_completed_total{status="error"}[5m]))`,
		// ... more queries
	}

	metrics := []ServiceMetrics{}

	// Execute queries and build ServiceMetrics
	// ...

	return metrics, nil
}
```

#### Frontend: WebSocket Consumer

```typescript
// frontend/src/hooks/useServiceMetrics.ts
import { useEffect, useState } from 'react';

interface ServiceMetrics {
  service: string;
  requestsReceived: number;
  requestsForwarded: number;
  activeRequests: number;
  failedRequests: number;
  avgLatency: number;
  p95Latency: number;
}

export function useServiceMetrics() {
  const [metrics, setMetrics] = useState<ServiceMetrics[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8090/ws/metrics');

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const newMetrics: ServiceMetrics[] = JSON.parse(event.data);
      setMetrics(newMetrics);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  return { metrics, connected };
}
```

---

## Trace View - Судьба задания

### User Story

**Как администратор,** я хочу выбрать конкретную операцию и увидеть её полный путь через все микросервисы (с таймингами, параметрами и ошибками), чтобы понять где задание застряло или почему упало.

### UI Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│  Operation Trace: op-67890                              [Close] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Operation: Install Extension "УправлениеПерсоналом"            │
│  Correlation ID: corr-12345-67890-1763565661                    │
│  Status: ✓ Success  │  Total Duration: 3.2s                     │
│                                                                  │
│  ┌─ Timeline ─────────────────────────────────────────────┐     │
│  │                                                         │     │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │     │
│  │  0s                    1.5s                    3.2s    │     │
│  │                                                         │     │
│  │  [Frontend] ✓ 0.02s                                    │     │
│  │  ├─ [API Gateway] ✓ 0.05s                             │     │
│  │  │  ├─ [Orchestrator] ✓ 0.15s                         │     │
│  │  │  │  └─ [Worker] ✓ 2.8s                             │     │
│  │  │  │     ├─ [Lock Jobs] ✓ 0.8s                       │     │
│  │  │  │     ├─ [Install Ext] ✓ 1.5s                     │     │
│  │  │  │     └─ [Unlock Jobs] ✓ 0.5s                     │     │
│  │  │  └─ [Result Aggregation] ✓ 0.18s                   │     │
│  │                                                         │     │
│  └─────────────────────────────────────────────────────────     │
│                                                                  │
│  ┌─ Service Flow ────────────────────────────────────────┐     │
│  │                                                         │     │
│  │  Frontend ──0.02s──► API GW ──0.05s──► Orchestr       │     │
│  │                                           │             │     │
│  │                                           ▼ 0.15s      │     │
│  │                                         Redis           │     │
│  │                                           │             │     │
│  │                                           ▼ 2.8s       │     │
│  │                                         Worker          │     │
│  │                                       ┌───┴───┐         │     │
│  │                                       │       │         │     │
│  │                                       ▼       ▼         │     │
│  │                                   RAS Adpt  OData       │     │
│  │                                                         │     │
│  └─────────────────────────────────────────────────────────     │
│                                                                  │
│  ┌─ Span Details ───────────────────────────────────────┐      │
│  │ Selected: [Worker] Lock Scheduled Jobs               │      │
│  │                                                       │      │
│  │ Start Time: 2025-01-15 10:30:00.220                  │      │
│  │ Duration: 0.8s                                        │      │
│  │ Status: ✓ Success                                     │      │
│  │                                                       │      │
│  │ Attributes:                                           │      │
│  │   operation_id: op-67890                              │      │
│  │   correlation_id: corr-12345-67890-1763565661         │      │
│  │   database_id: db-12345                               │      │
│  │   cluster_id: c3e50859-3d41-4383-b0d7-4ee20272b69d   │      │
│  │   infobase_id: 60e7713e-b933-49e0-a3ae-5107ef56560c  │      │
│  │                                                       │      │
│  │ gRPC Call:                                            │      │
│  │   Service: ras.InfobaseManagementService              │      │
│  │   Method: LockInfobase                                │      │
│  │   Request: {cluster_id: "...", infobase_id: "..."}   │      │
│  │   Response: {success: true, message: "Locked"}        │      │
│  │                                                       │      │
│  └───────────────────────────────────────────────────────      │
│                                                                  │
│  [View Logs] [Download Trace] [Share Link]                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Correlation ID Propagation

#### Already exists in Worker!

```go
// go-services/worker/internal/processor/dual_mode.go:170
correlationID := fmt.Sprintf("%s-%s-%d", msg.OperationID, databaseID, time.Now().UnixNano())
```

#### Extend to all services

```go
// go-services/shared/tracing/context.go
package tracing

import (
	"context"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// InjectOperationContext adds operation tracking to context
func InjectOperationContext(ctx context.Context, operationID, correlationID, databaseID string) context.Context {
	span := trace.SpanFromContext(ctx)

	span.SetAttributes(
		attribute.String("operation.id", operationID),
		attribute.String("correlation.id", correlationID),
		attribute.String("database.id", databaseID),
	)

	return ctx
}

// StartSpan creates a new span with operation context
func StartSpan(ctx context.Context, spanName string, operationID string) (context.Context, trace.Span) {
	tracer := otel.Tracer("commandcenter1c")

	ctx, span := tracer.Start(ctx, spanName)

	span.SetAttributes(
		attribute.String("operation.id", operationID),
		attribute.String("service.name", "worker"),
	)

	return ctx, span
}

// ExtractOperationIDs extracts operation tracking IDs from context
func ExtractOperationIDs(ctx context.Context) (operationID, correlationID string) {
	span := trace.SpanFromContext(ctx)
	// Extract from span attributes
	// ...
	return
}
```

#### HTTP Header Propagation

```go
// go-services/api-gateway/internal/middleware/tracing.go
package middleware

import (
	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

func TracingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Extract trace context from incoming headers
		ctx := otel.GetTextMapPropagator().Extract(
			c.Request.Context(),
			propagation.HeaderCarrier(c.Request.Header),
		)

		// Start new span
		tracer := otel.Tracer("api-gateway")
		ctx, span := tracer.Start(ctx, c.Request.URL.Path)
		defer span.End()

		// Extract operation ID from request
		operationID := c.GetHeader("X-Operation-ID")
		if operationID == "" {
			operationID = generateOperationID()
		}

		// Add to context
		c.Set("operation_id", operationID)
		c.Request = c.Request.WithContext(ctx)

		// Inject trace context into outgoing headers (for forwarding)
		otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(c.Writer.Header()))

		c.Next()
	}
}
```

#### gRPC Metadata Propagation

```go
// go-services/worker/internal/client/ras_adapter_client.go
package client

import (
	"context"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

type RASAdapterClient struct {
	conn *grpc.ClientConn
}

func NewRASAdapterClient(addr string) (*RASAdapterClient, error) {
	// gRPC client with OpenTelemetry interceptor
	conn, err := grpc.Dial(addr,
		grpc.WithInsecure(),
		grpc.WithUnaryInterceptor(otelgrpc.UnaryClientInterceptor()),
		grpc.WithStreamInterceptor(otelgrpc.StreamClientInterceptor()),
	)
	if err != nil {
		return nil, err
	}

	return &RASAdapterClient{conn: conn}, nil
}

func (c *RASAdapterClient) LockInfobase(ctx context.Context, operationID, correlationID, clusterID, infobaseID string) error {
	// Inject operation IDs into gRPC metadata
	ctx = metadata.AppendToOutgoingContext(ctx,
		"operation-id", operationID,
		"correlation-id", correlationID,
	)

	// OpenTelemetry will automatically propagate trace context
	client := pb.NewInfobaseManagementServiceClient(c.conn)
	_, err := client.LockInfobase(ctx, &pb.LockInfobaseRequest{
		ClusterId:         clusterID,
		InfobaseId:        infobaseID,
		ScheduledJobsDeny: true,
	})

	return err
}
```

### Jaeger Integration

#### Export traces to Jaeger

```go
// go-services/shared/tracing/jaeger.go
package tracing

import (
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/jaeger"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.4.0"
)

func InitJaegerTracer(serviceName string, jaegerEndpoint string) error {
	// Create Jaeger exporter
	exporter, err := jaeger.New(
		jaeger.WithCollectorEndpoint(jaeger.WithEndpoint(jaegerEndpoint)),
	)
	if err != nil {
		return err
	}

	// Create trace provider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceNameKey.String(serviceName),
		)),
	)

	otel.SetTracerProvider(tp)

	return nil
}
```

#### Initialize in each service

```go
// go-services/worker/cmd/main.go
package main

import (
	"github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
)

func main() {
	cfg := config.Load()

	// Initialize Jaeger tracing
	err := tracing.InitJaegerTracer("worker", "http://localhost:14268/api/traces")
	if err != nil {
		log.Fatalf("Failed to initialize Jaeger: %v", err)
	}

	// ... rest of initialization
}
```

### Query Jaeger API for Trace View

```typescript
// frontend/src/api/jaeger.ts
import axios from 'axios';

const JAEGER_API = 'http://localhost:16686';

export interface JaegerSpan {
  traceID: string;
  spanID: string;
  operationName: string;
  startTime: number;
  duration: number;
  tags: Record<string, any>;
  logs: any[];
  references: any[];
}

export interface JaegerTrace {
  traceID: string;
  spans: JaegerSpan[];
  processes: Record<string, any>;
}

export async function getTraceByOperationID(operationID: string): Promise<JaegerTrace | null> {
  try {
    // Search for traces with operation_id tag
    const response = await axios.get(`${JAEGER_API}/api/traces`, {
      params: {
        service: 'worker',
        tags: JSON.stringify({ 'operation.id': operationID }),
        limit: 1,
      },
    });

    if (response.data.data && response.data.data.length > 0) {
      return response.data.data[0];
    }

    return null;
  } catch (error) {
    console.error('Failed to fetch trace:', error);
    return null;
  }
}

export async function getTrace(traceID: string): Promise<JaegerTrace | null> {
  try {
    const response = await axios.get(`${JAEGER_API}/api/traces/${traceID}`);

    if (response.data.data && response.data.data.length > 0) {
      return response.data.data[0];
    }

    return null;
  } catch (error) {
    console.error('Failed to fetch trace:', error);
    return null;
  }
}
```

---

## Технический Stack

### OpenTelemetry + Jaeger

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Instrumentation** | OpenTelemetry SDK (Go, Python, JS) | Generate traces, metrics, logs |
| **Trace Backend** | Jaeger (all-in-one) | Store and query traces |
| **Metrics Backend** | Prometheus | Store metrics, provide PromQL |
| **Metrics Aggregator** | Custom Go service (port 8090) | Aggregate metrics, push via WebSocket |
| **UI Backend** | Jaeger Query API (port 16686) | HTTP API for trace queries |
| **UI Frontend** | React + TypeScript | Service mesh monitor, trace viewer |

### Deployment Architecture

```yaml
# docker-compose.tracing.yml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "5775:5775/udp"   # accept zipkin.thrift over compact thrift protocol
      - "6831:6831/udp"   # accept jaeger.thrift over compact thrift protocol
      - "6832:6832/udp"   # accept jaeger.thrift over binary thrift protocol
      - "5778:5778"       # serve configs
      - "16686:16686"     # serve frontend (Jaeger UI)
      - "14268:14268"     # accept jaeger.thrift directly from clients
      - "14250:14250"     # accept model.proto (gRPC)
      - "9411:9411"       # Zipkin compatible endpoint
    environment:
      - COLLECTOR_ZIPKIN_HTTP_PORT=9411
    networks:
      - commandcenter

  metrics-aggregator:
    build: ./go-services/metrics-aggregator
    ports:
      - "8090:8090"       # WebSocket endpoint
    environment:
      - PROMETHEUS_URL=http://prometheus:9090
    depends_on:
      - prometheus
    networks:
      - commandcenter

networks:
  commandcenter:
    external: true
```

---

## Implementation Roadmap

### Phase 1: Infrastructure Setup (Week 1)

**Goal:** Deploy Jaeger, instrument services with basic tracing

#### Task 1.1: Deploy Jaeger (1 day)
- [ ] Add `docker-compose.tracing.yml`
- [ ] Configure Jaeger all-in-one container
- [ ] Verify Jaeger UI accessible at http://localhost:16686
- [ ] Test manual trace creation

**Deliverable:** Jaeger running and accessible

#### Task 1.2: Create Shared Tracing Library (2 days)
- [ ] Implement `go-services/shared/tracing/jaeger.go`
- [ ] Implement `go-services/shared/tracing/context.go`
- [ ] Add OpenTelemetry dependencies to all Go services
- [ ] Create helper functions: `StartSpan`, `InjectOperationContext`

**Deliverable:** Reusable tracing library

#### Task 1.3: Instrument API Gateway (1 day)
- [ ] Add tracing middleware to Gin
- [ ] Propagate trace context in HTTP headers
- [ ] Test: curl request → see trace in Jaeger

**Deliverable:** API Gateway sends traces to Jaeger

#### Task 1.4: Instrument Worker (1 day)
- [ ] Initialize Jaeger tracer in `cmd/main.go`
- [ ] Add spans to `dual_mode.go`:
  - `ProcessExtensionInstall` (parent span)
  - `processEventDriven` (child span)
  - `processHTTPSync` (child span)
- [ ] Test: trigger operation → see trace in Jaeger

**Deliverable:** Worker sends traces to Jaeger

---

### Phase 2: Correlation ID Propagation (Week 2)

**Goal:** Propagate operation_id and correlation_id through all services

#### Task 2.1: HTTP Header Propagation (2 days)
- [ ] Frontend: Add `X-Operation-ID` header to API calls
- [ ] API Gateway: Extract and forward `X-Operation-ID`
- [ ] Orchestrator: Extract `X-Operation-ID` from Django request
- [ ] Add to span attributes in all services

**Deliverable:** operation_id flows Frontend → API Gateway → Orchestrator

#### Task 2.2: RAS Metadata Propagation (2 days)
- [ ] Worker: Add operation_id to RAS call context (span attributes)
- [ ] Add interceptor for automatic metadata extraction

**Deliverable:** operation_id flows Worker → RAS calls

#### Task 2.3: Structured Logging (1 day)
- [ ] Update all log statements to include:
  - `operation_id`
  - `correlation_id`
  - `trace_id`
  - `span_id`
- [ ] Test: filter logs by correlation_id

**Deliverable:** Logs correlated with traces

---

### Phase 3: Metrics Collection (Week 3)

**Goal:** Expose Prometheus metrics from all services

#### Task 3.1: Go Services Metrics (3 days)
- [ ] API Gateway: requests_received, requests_forwarded, latency
- [ ] Worker: tasks_received, tasks_active, tasks_completed
- [ ] RAS Adapter: ras_requests_total, active_connections, latency
- [ ] Expose `/metrics` endpoint in each service
- [ ] Configure Prometheus scrape targets

**Deliverable:** Prometheus scrapes metrics from Go services

#### Task 3.2: Django Orchestrator Metrics (2 days)
- [ ] Install `django-prometheus`
- [ ] Add custom metrics: operations_created, celery_queue_depth
- [ ] Expose `/metrics` endpoint
- [ ] Configure Prometheus scrape

**Deliverable:** Prometheus scrapes Django metrics

---

### Phase 4: Metrics Aggregator & WebSocket (Week 4)

**Goal:** Real-time metrics pushed to frontend

#### Task 4.1: Build Metrics Aggregator (3 days)
- [ ] Create `go-services/metrics-aggregator` service
- [ ] Query Prometheus for service metrics (PromQL)
- [ ] Aggregate into `ServiceMetrics` struct
- [ ] Expose WebSocket endpoint `/ws/metrics`
- [ ] Push metrics every 2 seconds

**Deliverable:** WebSocket server pushing real-time metrics

#### Task 4.2: Frontend WebSocket Consumer (2 days)
- [ ] Create `useServiceMetrics()` hook
- [ ] Connect to WebSocket on component mount
- [ ] Update state on new metrics received
- [ ] Handle reconnection on disconnect

**Deliverable:** Frontend receives real-time metrics

---

### Phase 5: Aggregate View UI (Week 5-6)

**Goal:** Service Mesh Monitor component

#### Task 5.1: Service Node Component (2 days)
```typescript
// frontend/src/components/ServiceNode.tsx
interface ServiceNodeProps {
  service: string;
  metrics: ServiceMetrics;
  onClickRequests: () => void;
  position: { x: number; y: number };
}

export function ServiceNode({ service, metrics, onClickRequests, position }: ServiceNodeProps) {
  return (
    <div className="service-node" style={{ left: position.x, top: position.y }}>
      <h3>{service}</h3>
      <div className="metrics">
        <div className="metric" onClick={onClickRequests}>
          ↓ {metrics.requestsReceived} recv
        </div>
        <div className="metric">
          → {metrics.requestsForwarded} fwd
        </div>
        <div className="metric status-active">
          ⚡ {metrics.activeRequests} active
        </div>
        {metrics.failedRequests > 0 && (
          <div className="metric status-error">
            ✗ {metrics.failedRequests} failed
          </div>
        )}
      </div>
      <div className="latency">
        Avg: {metrics.avgLatency.toFixed(2)}ms
      </div>
    </div>
  );
}
```

**Deliverable:** ServiceNode component

#### Task 5.2: Service Mesh Layout (2 days)
- [ ] Position nodes on canvas (Frontend → API GW → Orchestr → Worker → RAS)
- [ ] Draw connections between nodes (SVG lines)
- [ ] Animate data flow (CSS animations)
- [ ] Add legend (Active, Success, Failed, Queued)

**Deliverable:** Service mesh visualization

#### Task 5.3: Click Interactions (2 days)
- [ ] Click on "20 ops sent" → show list of operations
- [ ] Click on "2 failed" → show only failed operations
- [ ] Modal with operation list (Operation ID, Status, Duration)
- [ ] Click operation → open Trace View

**Deliverable:** Interactive service mesh

---

### Phase 6: Trace View UI (Week 7-8)

**Goal:** Operation Trace Viewer component

#### Task 6.1: Jaeger API Integration (1 day)
- [ ] Implement `getTraceByOperationID()`
- [ ] Implement `getTrace(traceID)`
- [ ] Parse Jaeger response into UI-friendly format
- [ ] Test with real traces

**Deliverable:** Jaeger API client

#### Task 6.2: Timeline Component (3 days)
```typescript
// frontend/src/components/TraceTimeline.tsx
interface TraceTimelineProps {
  trace: JaegerTrace;
  onSelectSpan: (span: JaegerSpan) => void;
}

export function TraceTimeline({ trace, onSelectSpan }: TraceTimelineProps) {
  // Build hierarchical span tree
  const spanTree = buildSpanTree(trace.spans);

  // Calculate positions based on timestamps
  const totalDuration = calculateTotalDuration(trace);

  return (
    <div className="trace-timeline">
      <div className="timeline-axis">
        <span>0s</span>
        <span>{(totalDuration / 2).toFixed(1)}s</span>
        <span>{totalDuration.toFixed(1)}s</span>
      </div>

      {spanTree.map(span => (
        <SpanBar
          key={span.spanID}
          span={span}
          totalDuration={totalDuration}
          onSelect={onSelectSpan}
        />
      ))}
    </div>
  );
}
```

**Deliverable:** Timeline visualization

#### Task 6.3: Service Flow Diagram (2 days)
- [ ] Extract service names from spans
- [ ] Build service dependency graph
- [ ] Render as flowchart (Frontend → API GW → ...)
- [ ] Show durations on edges

**Deliverable:** Service flow diagram

#### Task 6.4: Span Details Panel (2 days)
- [ ] Display span attributes (operation_id, correlation_id, database_id)
- [ ] Show gRPC/HTTP request details
- [ ] Show response details
- [ ] Format JSON payloads
- [ ] Add "View Logs" button (filter logs by correlation_id)

**Deliverable:** Span details panel

---

### Phase 7: Polish & Integration (Week 9-10)

#### Task 7.1: Error Highlighting (1 day)
- [ ] Red color for failed spans in timeline
- [ ] Red border for services with errors in mesh
- [ ] Error count badge on service nodes

#### Task 7.2: Performance Optimization (2 days)
- [ ] Virtualize operation lists (react-window)
- [ ] Memoize expensive calculations
- [ ] Lazy load Jaeger traces (only when clicked)
- [ ] Debounce WebSocket updates

#### Task 7.3: Export & Share (2 days)
- [ ] "Download Trace" button (JSON export)
- [ ] "Share Link" button (copy trace URL)
- [ ] Deep linking to specific operation trace

#### Task 7.4: Documentation (2 days)
- [ ] User guide: How to use Service Mesh Monitor
- [ ] User guide: How to debug with Trace Viewer
- [ ] Admin guide: Jaeger configuration
- [ ] Developer guide: How to add instrumentation

---

## API Specification

### Metrics Aggregator API

#### WebSocket: `/ws/metrics`

**Protocol:** WebSocket

**Message Format:**
```json
[
  {
    "service": "frontend",
    "requests_received": 20,
    "requests_forwarded": 20,
    "active_requests": 0,
    "failed_requests": 2,
    "avg_latency": 45.5,
    "p95_latency": 120.8
  },
  {
    "service": "api-gateway",
    "requests_received": 20,
    "requests_forwarded": 20,
    "active_requests": 1,
    "failed_requests": 0,
    "avg_latency": 50.2,
    "p95_latency": 85.3
  },
  {
    "service": "worker",
    "requests_received": 20,
    "requests_forwarded": 0,
    "active_requests": 18,
    "failed_requests": 2,
    "avg_latency": 2500.5,
    "p95_latency": 5000.0
  }
]
```

**Update Frequency:** Every 2 seconds

---

### Jaeger Query API

#### GET `/api/traces`

**Description:** Search for traces by service and tags

**Parameters:**
- `service` (required): Service name (e.g., "worker")
- `tags` (optional): JSON string with tag filters (e.g., `{"operation.id": "op-67890"}`)
- `limit` (optional): Maximum number of traces to return (default: 20)
- `start` (optional): Start time in microseconds
- `end` (optional): End time in microseconds

**Response:**
```json
{
  "data": [
    {
      "traceID": "abc123",
      "spans": [...],
      "processes": {...}
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "errors": null
}
```

#### GET `/api/traces/{traceID}`

**Description:** Get a specific trace by ID

**Response:**
```json
{
  "data": [
    {
      "traceID": "abc123",
      "spans": [
        {
          "traceID": "abc123",
          "spanID": "def456",
          "operationName": "ProcessExtensionInstall",
          "startTime": 1705311000000000,
          "duration": 3200000,
          "tags": [
            { "key": "operation.id", "type": "string", "value": "op-67890" },
            { "key": "correlation.id", "type": "string", "value": "corr-12345-67890-1763565661" },
            { "key": "database.id", "type": "string", "value": "db-12345" }
          ],
          "logs": [],
          "references": []
        }
      ],
      "processes": {
        "p1": {
          "serviceName": "worker",
          "tags": []
        }
      }
    }
  ]
}
```

---

## UI Components

### Component Hierarchy

```
<App>
  └─ <DashboardPage>
      ├─ <ServiceMeshMonitor>          // Aggregate View
      │   ├─ <ServiceNode> (Frontend)
      │   ├─ <ServiceNode> (API Gateway)
      │   ├─ <ServiceNode> (Orchestrator)
      │   ├─ <ServiceNode> (Worker)
      │   └─ <ServiceNode> (RAS Adapter)
      │
      └─ <OperationTraceViewer>        // Trace View (Modal)
          ├─ <TraceTimeline>
          │   └─ <SpanBar> (nested)
          ├─ <ServiceFlowDiagram>
          └─ <SpanDetailsPanel>
```

### Key Components

#### 1. ServiceMeshMonitor
```typescript
// frontend/src/components/ServiceMeshMonitor.tsx
export function ServiceMeshMonitor() {
  const { metrics, connected } = useServiceMetrics();
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const handleNodeClick = (service: string, metric: string) => {
    // Show modal with operation list
    // ...
  };

  return (
    <div className="service-mesh-monitor">
      <div className="status-indicator">
        {connected ? '🟢 Live' : '🔴 Disconnected'}
      </div>

      <div className="service-graph">
        {metrics.map(m => (
          <ServiceNode
            key={m.service}
            metrics={m}
            onClickRequests={() => handleNodeClick(m.service, 'requests')}
            position={getNodePosition(m.service)}
          />
        ))}
      </div>
    </div>
  );
}
```

#### 2. OperationTraceViewer
```typescript
// frontend/src/components/OperationTraceViewer.tsx
interface Props {
  operationId: string;
  onClose: () => void;
}

export function OperationTraceViewer({ operationId, onClose }: Props) {
  const [trace, setTrace] = useState<JaegerTrace | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<JaegerSpan | null>(null);

  useEffect(() => {
    loadTrace();
  }, [operationId]);

  async function loadTrace() {
    const trace = await getTraceByOperationID(operationId);
    setTrace(trace);
  }

  return (
    <Modal open onClose={onClose} size="xl">
      <ModalHeader>
        Operation Trace: {operationId}
      </ModalHeader>

      <ModalBody>
        {trace && (
          <div className="trace-viewer">
            <div className="trace-info">
              <Tag>Status: {getTraceStatus(trace)}</Tag>
              <Tag>Duration: {formatDuration(getTotalDuration(trace))}</Tag>
            </div>

            <Tabs>
              <TabPane tab="Timeline" key="timeline">
                <TraceTimeline trace={trace} onSelectSpan={setSelectedSpan} />
              </TabPane>

              <TabPane tab="Service Flow" key="flow">
                <ServiceFlowDiagram trace={trace} />
              </TabPane>

              <TabPane tab="Logs" key="logs">
                <LogsPanel correlationId={getCorrelationId(trace)} />
              </TabPane>
            </Tabs>

            {selectedSpan && (
              <SpanDetailsPanel span={selectedSpan} />
            )}
          </div>
        )}
      </ModalBody>
    </Modal>
  );
}
```

---

## Integration Points

### 1. Frontend → API Gateway

**Existing:** HTTP requests via `axios`

**Add:**
```typescript
// frontend/src/api/client.ts
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

const apiClient = axios.create({
  baseURL: 'http://localhost:8080/api/v1',
});

// Add operation ID to all requests
apiClient.interceptors.request.use((config) => {
  const operationId = uuidv4();
  config.headers['X-Operation-ID'] = operationId;

  // Store for later retrieval
  sessionStorage.setItem(`operation-${operationId}`, Date.now().toString());

  return config;
});

export default apiClient;
```

### 2. API Gateway → Orchestrator

**Existing:** HTTP proxy with `http.ReverseProxy`

**Add:** Forward `X-Operation-ID` header

```go
// go-services/api-gateway/internal/proxy/orchestrator.go
func (p *OrchestratorProxy) proxyRequest(c *gin.Context) {
	// Extract operation ID from context
	operationID, exists := c.Get("operation_id")
	if !exists {
		operationID = generateOperationID()
	}

	// Create request to Orchestrator
	req, _ := http.NewRequest(c.Request.Method, targetURL, c.Request.Body)

	// Forward operation ID
	req.Header.Set("X-Operation-ID", operationID.(string))

	// Forward trace context (OpenTelemetry)
	otel.GetTextMapPropagator().Inject(c.Request.Context(), propagation.HeaderCarrier(req.Header))

	// Execute request
	// ...
}
```

### 3. Orchestrator → Celery → Worker

**Existing:** Celery task queue

**Add:** Pass operation_id in task payload

```python
# orchestrator/apps/operations/tasks.py
from celery import shared_task

@shared_task
def process_operation(operation_id: str, correlation_id: str, databases: list):
    """
    Process operation for multiple databases

    Args:
        operation_id: Operation ID from HTTP header
        correlation_id: Generated correlation ID
        databases: List of database IDs to process
    """
    for database_id in databases:
        # Publish to Redis with operation_id
        message = {
            "operation_id": operation_id,
            "correlation_id": f"{correlation_id}-{database_id}",
            "database_id": database_id,
            # ... other fields
        }
        redis_client.publish("worker_tasks", json.dumps(message))
```

### 4. Worker → RAS Adapter

**Existing:** gRPC calls (after migration)

**Add:** Pass operation_id in gRPC metadata

```go
// go-services/worker/internal/processor/dual_mode.go

func (dm *DualModeProcessor) ProcessExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	// Create span
	ctx, span := tracing.StartSpan(ctx, "ProcessExtensionInstall", msg.OperationID)
	defer span.End()

	// Inject operation context
	ctx = tracing.InjectOperationContext(ctx, msg.OperationID, correlationID, databaseID)

	// ... existing logic

	// Call RAS Adapter with context (metadata automatically propagated by otelgrpc)
	result, err := dm.rasClient.LockInfobase(ctx, clusterID, infobaseID)

	// ...
}
```

---

## Summary

### What we get

✅ **Aggregate View:**
- Real-time service mesh visualization
- See operation counts flowing through services
- Click on numbers to drill down
- WebSocket updates every 2 seconds

✅ **Trace View:**
- Click any operation → see full journey
- Timeline with durations
- Service flow diagram
- Detailed span info (params, responses, errors)
- Correlated logs

✅ **Debugging:**
- Instantly see where operation is stuck
- Compare successful vs failed traces
- Root cause analysis with spans
- Export traces for sharing

### Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Infrastructure** | Week 1 | Jaeger deployed, basic tracing working |
| **Phase 2: Correlation IDs** | Week 2 | operation_id flows through all services |
| **Phase 3: Metrics** | Week 3 | All services expose Prometheus metrics |
| **Phase 4: WebSocket** | Week 4 | Real-time metrics pushed to frontend |
| **Phase 5: Aggregate View** | Week 5-6 | Service mesh monitor UI |
| **Phase 6: Trace View** | Week 7-8 | Operation trace viewer UI |
| **Phase 7: Polish** | Week 9-10 | Error highlighting, export, docs |

**Total: 10 weeks (2.5 months)**

**MVP Option (6 weeks):**
- Phases 1-4 (Infrastructure + Metrics + WebSocket)
- Basic Aggregate View (no fancy animations)
- Jaeger UI for Trace View (skip custom UI)

---

**Next Steps:**

1. ✅ Review and approve this design
2. Add to RAS Adapter roadmap as parallel workstream
3. Start with Phase 1 (Jaeger setup)
4. Iterate based on feedback

**Questions?**
