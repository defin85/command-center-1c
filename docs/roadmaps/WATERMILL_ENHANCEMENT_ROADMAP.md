# Watermill Enhancement Roadmap - Production Resilience Patterns

**Version:** 1.0
**Date:** 2025-11-20
**Status:** Active Roadmap
**Target:** go-services/shared/events library
**Related:** [EVENT_DRIVEN_ARCHITECTURE.md](../architecture/EVENT_DRIVEN_ARCHITECTURE.md), [RAS_ADAPTER_ROADMAP.md](RAS_ADAPTER_ROADMAP.md)

---

## Executive Summary

### Current State ✅

**Watermill integration УЖЕ работает отлично:**
- ✅ Redis Streams (Pub/Sub с persistence)
- ✅ Consumer Groups (load balancing)
- ✅ Middleware: Retry, Idempotency, Logging, Recovery, Timeout
- ✅ Prometheus metrics
- ✅ Graceful shutdown
- ✅ Backpressure (semaphore)
- ✅ Auto-reconnect к Redis

**Файлы:**
- `go-services/shared/events/publisher.go` - Watermill Publisher wrapper
- `go-services/shared/events/subscriber.go` - Watermill Subscriber wrapper
- `go-services/shared/events/middleware.go` - Retry, Idempotency, Logging, Recovery, Timeout
- `go-services/shared/events/metrics.go` - Prometheus metrics
- `go-services/shared/events/config.go` - Configuration

### What's Missing ❌

**Critical для Production:**
1. ❌ **Circuit Breaker** - защита от cascading failures (упоминается в EVENT_DRIVEN_ARCHITECTURE!)
2. ❌ **Dead Letter Queue (DLQ)** - для необработанных сообщений
3. ❌ **OpenTelemetry Tracing** - distributed tracing (в roadmap README)

**Nice to Have:**
4. ❌ **Rate Limiting** - защита от event storms
5. ❌ **Schema Validation** - JSON Schema/Protobuf validation (в roadmap README)
6. ❌ **Message Priority** - приоритезация критичных событий (в roadmap README)
7. ❌ **Bulkhead Pattern** - изоляция ресурсов между handlers

### Goal

Добавить production-ready resilience patterns в `go-services/shared/events` для event-driven архитектуры:
- Защита от cascading failures (Circuit Breaker)
- Надежная обработка failed messages (DLQ)
- Full observability (OpenTelemetry)
- Protection от abuse (Rate Limiting)

### Effort

- **Phase 1 (Critical):** 2 weeks - Circuit Breaker + DLQ
- **Phase 2 (Observability):** 1 week - OpenTelemetry
- **Phase 3 (Nice to Have):** 1.5 weeks - Rate Limiting + Schema Validation + Priority
- **Total:** 4.5 weeks

---

## Phase 1: Critical Resilience Patterns (2 weeks)

### Week 1: Circuit Breaker Middleware

**Goal:** Защита от cascading failures при сбоях downstream сервисов

**Motivation:**
- Из EVENT_DRIVEN_ARCHITECTURE.md: "Circuit breaker (fail fast if RAS unavailable)"
- Текущая проблема: если cluster-service падает, Worker продолжает отправлять команды → событийный шторм

**Implementation:**

#### 1.1. Circuit Breaker States

```go
// go-services/shared/events/circuitbreaker.go

type CircuitBreakerState int

const (
    StateClosed CircuitBreakerState = iota  // Normal operation
    StateOpen                                // Circuit opened - fail fast
    StateHalfOpen                            // Testing recovery
)

type CircuitBreaker struct {
    state              CircuitBreakerState
    failureCount       int
    successCount       int
    consecutiveSuccess int
    lastStateChange    time.Time
    mu                 sync.RWMutex

    // Config
    maxFailures        int           // Open circuit after N failures
    timeout            time.Duration // Wait before HalfOpen
    halfOpenRequests   int           // Test with N requests in HalfOpen
}
```

#### 1.2. Circuit Breaker Middleware

```go
// WithCircuitBreaker adds circuit breaker pattern to prevent cascading failures
func WithCircuitBreaker(
    name string,
    maxFailures int,
    timeout time.Duration,
    logger watermill.LoggerAdapter,
) message.HandlerMiddleware {
    cb := NewCircuitBreaker(name, maxFailures, timeout)

    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            // Check circuit state
            if cb.IsOpen() {
                logger.Error("Circuit breaker OPEN - rejecting message", ErrCircuitBreakerOpen, watermill.LogFields{
                    "circuit_breaker": name,
                    "message_id":      msg.UUID,
                })
                RecordCircuitBreakerOpen(name)
                return nil, ErrCircuitBreakerOpen // Fast fail!
            }

            // Execute handler
            messages, err := h(msg)

            // Record result
            if err != nil {
                cb.RecordFailure()
                if cb.IsOpen() {
                    logger.Error("Circuit breaker OPENED", nil, watermill.LogFields{
                        "circuit_breaker": name,
                        "failure_count":   cb.failureCount,
                    })
                }
            } else {
                cb.RecordSuccess()
                if cb.WasClosed() {
                    logger.Info("Circuit breaker CLOSED (recovered)", watermill.LogFields{
                        "circuit_breaker": name,
                    })
                }
            }

            return messages, err
        }
    }
}
```

#### 1.3. Integration Example

```go
// cluster-service/cmd/main.go

// Create subscriber with circuit breaker
subscriber, _ := events.NewSubscriber(redisClient, "cluster-service-consumer", logger)

// Add circuit breaker middleware
subscriber.Router().AddMiddleware(
    // Circuit breaker for RAS calls (fail fast if RAS unavailable)
    events.WithCircuitBreaker(
        "ras-client",
        5,              // Open after 5 failures
        30*time.Second, // Wait 30s before retry
        logger,
    ),

    // Recovery
    events.WithRecovery(logger),

    // Retry (AFTER circuit breaker check!)
    events.WithRetry(3, time.Second, logger),
)
```

**Deliverables:**
- [ ] `circuitbreaker.go` - CircuitBreaker implementation
- [ ] `middleware.go` - WithCircuitBreaker middleware
- [ ] `circuitbreaker_test.go` - Unit tests
- [ ] Prometheus metrics: `events_circuit_breaker_state{name, state}`, `events_circuit_breaker_failures_total{name}`
- [ ] Integration test with simulated RAS failures

---

### Week 2: Dead Letter Queue (DLQ)

**Goal:** Сохранить необработанные сообщения для manual action

**Motivation:**
- Из EVENT_DRIVEN_ARCHITECTURE.md Risk 4: "Worker crashes → infobase locked навсегда"
- Текущая проблема: если handler fails после max retries → сообщение теряется

**Implementation:**

#### 2.1. DLQ Publisher

```go
// go-services/shared/events/dlq.go

type DLQPublisher struct {
    redisClient *redis.Client
    publisher   *Publisher
    logger      watermill.LoggerAdapter
}

func NewDLQPublisher(redisClient *redis.Client, serviceName string, logger watermill.LoggerAdapter) (*DLQPublisher, error) {
    publisher, err := NewPublisher(redisClient, serviceName+"-dlq", logger)
    if err != nil {
        return nil, err
    }

    return &DLQPublisher{
        redisClient: redisClient,
        publisher:   publisher,
        logger:      logger,
    }, nil
}

// PublishToDLQ sends failed message to dead letter queue
func (d *DLQPublisher) PublishToDLQ(ctx context.Context, envelope *Envelope, failureReason string, retryCount int) error {
    dlqChannel := fmt.Sprintf("dlq:%s", envelope.ServiceName)

    // Add DLQ metadata
    dlqPayload := DLQMessage{
        OriginalEnvelope: envelope,
        FailureReason:    failureReason,
        RetryCount:       retryCount,
        FailedAt:         time.Now().UTC(),
        CanRetry:         true, // Can be manually retried
    }

    err := d.publisher.Publish(ctx, dlqChannel, "dlq.message.failed", dlqPayload, envelope.CorrelationID)
    if err != nil {
        d.logger.Error("Failed to publish to DLQ", err, watermill.LogFields{
            "message_id":     envelope.MessageID,
            "correlation_id": envelope.CorrelationID,
        })
        return err
    }

    // Also store in PostgreSQL for admin panel
    d.storeDLQInDB(ctx, dlqPayload)

    return nil
}
```

#### 2.2. DLQ Middleware

```go
// WithDLQ sends failed messages to dead letter queue after max retries
func WithDLQ(dlqPublisher *DLQPublisher, maxRetries int, logger watermill.LoggerAdapter) message.HandlerMiddleware {
    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            var lastErr error

            for attempt := 0; attempt <= maxRetries; attempt++ {
                messages, err := h(msg)
                if err == nil {
                    return messages, nil // Success!
                }

                lastErr = err

                if attempt < maxRetries {
                    // Retry logic (exponential backoff)
                    delay := calculateBackoff(attempt)
                    time.Sleep(delay)
                }
            }

            // All retries exhausted - send to DLQ
            logger.Error("Message failed after max retries - sending to DLQ", lastErr, watermill.LogFields{
                "message_id": msg.UUID,
                "attempts":   maxRetries + 1,
            })

            var envelope Envelope
            json.Unmarshal(msg.Payload, &envelope)

            err := dlqPublisher.PublishToDLQ(msg.Context(), &envelope, lastErr.Error(), maxRetries)
            if err != nil {
                logger.Error("Failed to publish to DLQ", err, nil)
            }

            // ACK the message (don't retry infinitely)
            return nil, nil
        }
    }
}
```

#### 2.3. DLQ Replay Tool

```bash
# scripts/replay-dlq.sh

#!/bin/bash
# Replay messages from DLQ

CORRELATION_ID=$1
CHANNEL=$2

if [ -z "$CORRELATION_ID" ]; then
    echo "Usage: ./replay-dlq.sh <correlation_id> [channel]"
    exit 1
fi

go run cmd/tools/dlq-replay/main.go --correlation-id="$CORRELATION_ID" --channel="$CHANNEL"
```

```go
// cmd/tools/dlq-replay/main.go

func main() {
    // Fetch DLQ message from Redis
    dlqMsg := fetchDLQMessage(correlationID)

    // Re-publish to original channel
    publisher.Publish(ctx, dlqMsg.OriginalChannel, dlqMsg.EventType, dlqMsg.Payload, correlationID)

    log.Printf("Replayed message %s to channel %s", correlationID, dlqMsg.OriginalChannel)
}
```

**Deliverables:**
- [ ] `dlq.go` - DLQPublisher implementation
- [ ] `middleware.go` - WithDLQ middleware
- [ ] `dlq_test.go` - Unit tests
- [ ] `cmd/tools/dlq-replay/main.go` - Replay tool
- [ ] PostgreSQL table `dlq_messages` для admin panel
- [ ] Django admin view для DLQ messages
- [ ] Prometheus metrics: `events_dlq_messages_total{channel, reason}`

---

## Phase 2: Observability (1 week)

### Week 3: OpenTelemetry Tracing

**Goal:** Full distributed tracing для event-driven workflows

**Motivation:**
- Из EVENT_DRIVEN_ARCHITECTURE.md Section 8.4: "OpenTelemetry Integration"
- Текущая проблема: сложно трейсить события через Worker → cluster-service → RAS
- Из roadmap README: "Add OpenTelemetry tracing integration"

**Implementation:**

#### 3.1. OpenTelemetry Propagation

```go
// go-services/shared/events/tracing.go

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/propagation"
    "go.opentelemetry.io/otel/trace"
)

// WithTracing adds OpenTelemetry tracing to message processing
func WithTracing(serviceName string) message.HandlerMiddleware {
    tracer := otel.Tracer(serviceName)
    propagator := otel.GetTextMapPropagator()

    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            // Extract trace context from message metadata
            ctx := propagator.Extract(msg.Context(), &MessageCarrier{msg: msg})

            // Start span
            ctx, span := tracer.Start(ctx, "process_event",
                trace.WithSpanKind(trace.SpanKindConsumer),
            )
            defer span.End()

            // Add envelope metadata to span
            var envelope Envelope
            json.Unmarshal(msg.Payload, &envelope)

            span.SetAttributes(
                attribute.String("message_id", envelope.MessageID),
                attribute.String("correlation_id", envelope.CorrelationID),
                attribute.String("event_type", envelope.EventType),
                attribute.String("service_name", envelope.ServiceName),
            )

            // Set context back to message
            msg.SetContext(ctx)

            // Process message
            messages, err := h(msg)
            if err != nil {
                span.RecordError(err)
                span.SetStatus(codes.Error, err.Error())
            }

            return messages, err
        }
    }
}

// Publisher.Publish с trace propagation
func (p *Publisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
    // ... existing code ...

    // Inject trace context into message metadata
    propagator := otel.GetTextMapPropagator()
    propagator.Inject(ctx, &MessageCarrier{msg: msg})

    // Publish message
    return p.watermill.Publish(channel, msg)
}
```

#### 3.2. Trace Visualization Example

```
Trace ID: abc-123-def (correlation_id)

┌─ extension_install (Worker) [52.3s] ──────────────────────────┐
│  ├─ publish:cluster.infobase.lock (1ms)                       │
│  │  └─ redis:publish (1ms)                                    │
│  ├─ wait:cluster.infobase.locked (1.2s)                       │
│  │  └─ cluster-service:lock_handler (1.1s)                    │
│  │     └─ grpc:LockInfobase (1.0s)                            │
│  ├─ publish:cluster.sessions.terminate (1ms)                  │
│  ├─ wait:cluster.sessions.closed (8.5s)                       │
│  │  └─ cluster-service:terminate_handler (8.4s)               │
│  │     └─ grpc:TerminateSessions (8.3s)                       │
│  ├─ publish:batch.extension.install (1ms)                     │
│  ├─ wait:batch.extension.installed (31.2s)                    │
│  │  └─ batch-service:install_handler (31.1s)                  │
│  │     └─ subprocess:1cv8.exe (31.0s)                         │
│  └─ publish:cluster.infobase.unlock (1ms)                     │
│     └─ cluster-service:unlock_handler (1.0s)                  │
│        └─ grpc:UnlockInfobase (0.9s)                          │
└────────────────────────────────────────────────────────────────┘
```

**Deliverables:**
- [ ] `tracing.go` - OpenTelemetry integration
- [ ] `middleware.go` - WithTracing middleware
- [ ] MessageCarrier для trace context propagation
- [ ] Update Publisher/Subscriber для trace context injection/extraction
- [ ] Jaeger/Tempo integration example
- [ ] Documentation для observability setup

---

## Phase 3: Additional Enhancements (1.5 weeks)

### Week 4: Rate Limiting & Schema Validation

#### 4.1. Rate Limiting Middleware (3 days)

**Goal:** Защита от event storms

```go
// WithRateLimit limits message processing rate per channel
func WithRateLimit(
    rps int,                       // Requests per second
    burst int,                     // Burst size
    logger watermill.LoggerAdapter,
) message.HandlerMiddleware {
    limiter := rate.NewLimiter(rate.Limit(rps), burst)

    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            // Wait for rate limiter
            if err := limiter.Wait(msg.Context()); err != nil {
                logger.Error("Rate limit exceeded", err, watermill.LogFields{
                    "message_id": msg.UUID,
                })
                return nil, ErrRateLimitExceeded
            }

            return h(msg)
        }
    }
}
```

**Usage:**
```go
subscriber.Router().AddMiddleware(
    events.WithRateLimit(100, 200, logger), // 100 rps, burst 200
)
```

#### 4.2. Schema Validation Middleware (3 days)

**Goal:** Validate event payloads против JSON Schema

```go
// WithSchemaValidation validates message payload against JSON Schema
func WithSchemaValidation(
    schemas map[string]*jsonschema.Schema, // event_type -> schema
    logger watermill.LoggerAdapter,
) message.HandlerMiddleware {
    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            var envelope Envelope
            json.Unmarshal(msg.Payload, &envelope)

            // Get schema for event type
            schema, ok := schemas[envelope.EventType]
            if !ok {
                // No schema defined - skip validation
                return h(msg)
            }

            // Validate payload
            if err := schema.Validate(envelope.Payload); err != nil {
                logger.Error("Schema validation failed", err, watermill.LogFields{
                    "message_id": msg.UUID,
                    "event_type": envelope.EventType,
                })
                RecordSchemaValidationError(envelope.EventType)
                return nil, fmt.Errorf("schema validation failed: %w", err)
            }

            return h(msg)
        }
    }
}
```

**Schema Example:**
```json
// schemas/cluster.infobase.lock.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["cluster_id", "infobase_id"],
  "properties": {
    "cluster_id": {
      "type": "string",
      "format": "uuid"
    },
    "infobase_id": {
      "type": "string",
      "format": "uuid"
    },
    "database_id": {
      "type": "string",
      "format": "uuid"
    }
  }
}
```

**Deliverables:**
- [ ] `ratelimit.go` - Rate limiting implementation
- [ ] `schema.go` - Schema validation
- [ ] `middleware.go` - WithRateLimit, WithSchemaValidation
- [ ] JSON Schema files для всех event types
- [ ] Tests

---

### Week 4.5: Message Priority & Bulkhead (1.5 days)

#### 4.3. Message Priority (Optional)

**Goal:** Prioritize critical events (из roadmap README)

```go
// Priority levels
const (
    PriorityLow    = 1
    PriorityNormal = 5
    PriorityHigh   = 10
)

// PublishWithPriority publishes event with priority
func (p *Publisher) PublishWithPriority(
    ctx context.Context,
    channel string,
    eventType string,
    payload interface{},
    correlationID string,
    priority int,
) error {
    metadata := map[string]interface{}{
        "priority": priority,
    }

    return p.PublishWithMetadata(ctx, channel, eventType, payload, correlationID, metadata)
}

// Priority subscriber processes high-priority messages first
func NewPrioritySubscriber(...) (*Subscriber, error) {
    // Use multiple consumer groups with different priority channels
    // High priority: "commands:cluster-service:priority:high"
    // Normal: "commands:cluster-service:priority:normal"
    // Low: "commands:cluster-service:priority:low"
}
```

#### 4.4. Bulkhead Pattern (Optional)

**Goal:** Изоляция ресурсов между handlers

```go
// WithBulkhead isolates resources for different event types
func WithBulkhead(
    maxConcurrent map[string]int, // event_type -> max concurrent
    logger watermill.LoggerAdapter,
) message.HandlerMiddleware {
    semaphores := make(map[string]chan struct{})
    for eventType, max := range maxConcurrent {
        semaphores[eventType] = make(chan struct{}, max)
    }

    return func(h message.HandlerFunc) message.HandlerFunc {
        return func(msg *message.Message) ([]*message.Message, error) {
            var envelope Envelope
            json.Unmarshal(msg.Payload, &envelope)

            // Get semaphore for event type
            sem, ok := semaphores[envelope.EventType]
            if !ok {
                // No bulkhead for this event type
                return h(msg)
            }

            // Acquire semaphore
            select {
            case sem <- struct{}{}:
                defer func() { <-sem }()
            case <-msg.Context().Done():
                return nil, msg.Context().Err()
            }

            return h(msg)
        }
    }
}
```

**Usage:**
```go
subscriber.Router().AddMiddleware(
    events.WithBulkhead(map[string]int{
        "cluster.infobase.lock":      10,  // Max 10 concurrent locks
        "cluster.sessions.terminate": 5,   // Max 5 concurrent terminates
        "batch.extension.install":    20,  // Max 20 concurrent installs
    }, logger),
)
```

**Deliverables:**
- [ ] `priority.go` - Priority implementation
- [ ] `bulkhead.go` - Bulkhead pattern
- [ ] Tests
- [ ] Documentation

---

## Integration Strategy

### Middleware Stack Order (CRITICAL!)

```go
// Recommended middleware order
subscriber.Router().AddMiddleware(
    // 1. Logging (first - log everything)
    events.WithLogging(logger),

    // 2. Metrics (track all messages)
    events.WithMetrics(consumerGroup),

    // 3. Tracing (distributed tracing)
    events.WithTracing("cluster-service"),

    // 4. Recovery (catch panics early)
    events.WithRecovery(logger),

    // 5. Timeout (prevent infinite hangs)
    events.WithTimeout(30*time.Second, logger),

    // 6. Rate Limiting (prevent overload)
    events.WithRateLimit(100, 200, logger),

    // 7. Circuit Breaker (fail fast)
    events.WithCircuitBreaker("ras-client", 5, 30*time.Second, logger),

    // 8. Bulkhead (resource isolation)
    events.WithBulkhead(maxConcurrentMap, logger),

    // 9. Idempotency (dedupe messages)
    events.WithIdempotency(redisClient, 24*time.Hour, logger),

    // 10. Schema Validation (validate payload)
    events.WithSchemaValidation(schemas, logger),

    // 11. DLQ + Retry (last - handle failures)
    events.WithDLQ(dlqPublisher, 3, logger),
)
```

**Почему этот порядок:**
1. Logging/Metrics/Tracing - наблюдаемость ВСЕХ сообщений
2. Recovery - catch panics до того, как они сломают pipeline
3. Timeout - prevent infinite hangs
4. Rate Limiting - защита от overload
5. Circuit Breaker - fail fast при downstream failures
6. Bulkhead - resource isolation
7. Idempotency - prevent duplicate processing
8. Schema Validation - validate payload перед обработкой
9. DLQ + Retry - обработка failures в конце

---

## Migration Plan

### Phase 1: Circuit Breaker (Week 1)

**Day 1-2: Implementation**
```bash
# Create files
touch go-services/shared/events/circuitbreaker.go
touch go-services/shared/events/circuitbreaker_test.go

# Implement
# - CircuitBreaker struct
# - State transitions (Closed → Open → HalfOpen → Closed)
# - WithCircuitBreaker middleware

# Tests
go test ./go-services/shared/events/... -run TestCircuitBreaker
```

**Day 3-4: Integration**
```go
// cluster-service/cmd/main.go
subscriber.Router().AddMiddleware(
    events.WithCircuitBreaker("ras-client", 5, 30*time.Second, logger),
)

// Test: Simulate RAS failures
./scripts/test-circuit-breaker.sh
```

**Day 5: Validation**
- Monitor Prometheus metrics: `events_circuit_breaker_state`
- Simulate RAS unavailable → Circuit should OPEN
- Wait 30s → Circuit should go HalfOpen → Test → Closed

### Phase 2: DLQ (Week 2)

**Day 1-3: Implementation**
```bash
# Create files
touch go-services/shared/events/dlq.go
touch go-services/shared/events/dlq_test.go

# Django migration
cd orchestrator
python manage.py makemigrations operations --name add_dlq_messages_table

# Implement
# - DLQPublisher
# - WithDLQ middleware
# - PostgreSQL storage

# Tests
go test ./go-services/shared/events/... -run TestDLQ
```

**Day 4-5: Replay Tool**
```bash
# Create replay tool
mkdir -p cmd/tools/dlq-replay
touch cmd/tools/dlq-replay/main.go

# Implement replay logic
# Test replay
./scripts/replay-dlq.sh <correlation_id> <channel>
```

### Phase 3: OpenTelemetry (Week 3)

**Day 1-3: Implementation**
```bash
# Add dependencies
cd go-services/shared
go get go.opentelemetry.io/otel
go get go.opentelemetry.io/otel/trace
go get go.opentelemetry.io/otel/propagation

# Create files
touch go-services/shared/events/tracing.go
touch go-services/shared/events/tracing_test.go

# Implement
# - MessageCarrier (TextMapCarrier)
# - WithTracing middleware
# - Publisher/Subscriber trace propagation
```

**Day 4-5: Integration**
```yaml
# docker-compose.local.monitoring.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "14268:14268"  # Jaeger collector
```

```go
// cluster-service/cmd/main.go
import "go.opentelemetry.io/otel"

// Initialize OpenTelemetry
tp := initTracer("cluster-service", "http://localhost:14268/api/traces")
defer tp.Shutdown(context.Background())

// Add tracing middleware
subscriber.Router().AddMiddleware(
    events.WithTracing("cluster-service"),
)
```

**Validation:**
- Open Jaeger UI: http://localhost:16686
- Trigger extension install workflow
- See full trace: Worker → cluster-service → RAS → batch-service

---

## Success Metrics

### Phase 1 (Circuit Breaker + DLQ)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Circuit Breaker reaction time | < 5s | Time from RAS failure to circuit OPEN |
| DLQ capture rate | 100% | Failed messages sent to DLQ |
| DLQ replay success rate | > 95% | Replayed messages processed successfully |

### Phase 2 (OpenTelemetry)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Trace coverage | 100% | All events have trace context |
| Trace latency overhead | < 1ms | OpenTelemetry overhead |
| Trace visualization | Full workflow | See Worker → cluster-service → RAS in Jaeger |

### Phase 3 (Rate Limiting + Schema Validation)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Rate limiting accuracy | ± 5% | Actual RPS vs configured |
| Schema validation coverage | 100% | All event types have schemas |
| Schema validation error rate | < 1% | Invalid payloads rejected |

---

## Prometheus Metrics (New)

**Circuit Breaker:**
```promql
# Circuit breaker state (0=Closed, 1=Open, 2=HalfOpen)
events_circuit_breaker_state{name="ras-client"}

# Circuit breaker failures
rate(events_circuit_breaker_failures_total{name="ras-client"}[5m])

# Circuit breaker opens
rate(events_circuit_breaker_opens_total{name="ras-client"}[5m])
```

**Dead Letter Queue:**
```promql
# DLQ messages
rate(events_dlq_messages_total{channel, reason}[5m])

# DLQ replay success
rate(events_dlq_replay_success_total{channel}[5m])
```

**Rate Limiting:**
```promql
# Rate limit rejections
rate(events_rate_limit_rejections_total{channel}[5m])
```

**Schema Validation:**
```promql
# Schema validation errors
rate(events_schema_validation_errors_total{event_type}[5m])
```

---

## Grafana Dashboards (Enhanced)

### Dashboard 1: Event-Driven Resilience

**Panels:**
1. Circuit Breaker States (gauge) - per handler
2. DLQ Messages Rate (graph) - messages/sec
3. Rate Limit Rejections (counter)
4. Schema Validation Errors (table) - by event type

### Dashboard 2: OpenTelemetry Traces

**Panels:**
1. Trace Latency Heatmap - P50/P95/P99
2. Service Dependencies Graph - визуализация вызовов
3. Error Traces - failed workflows
4. Slowest Operations - top 10

---

## Testing Strategy

### Unit Tests

```go
// circuitbreaker_test.go
func TestCircuitBreakerStateTransitions(t *testing.T) {
    cb := NewCircuitBreaker("test", 3, 10*time.Second)

    // Initially Closed
    assert.Equal(t, StateClosed, cb.State())

    // 3 failures → Open
    cb.RecordFailure()
    cb.RecordFailure()
    cb.RecordFailure()
    assert.Equal(t, StateOpen, cb.State())

    // Wait timeout → HalfOpen
    time.Sleep(11 * time.Second)
    assert.Equal(t, StateHalfOpen, cb.State())

    // Success → Closed
    cb.RecordSuccess()
    assert.Equal(t, StateClosed, cb.State())
}
```

### Integration Tests

```go
// integration_test.go
func TestCircuitBreakerWithRealRedis(t *testing.T) {
    // Start Redis
    redisContainer := testcontainers.StartRedis(t)
    defer redisContainer.Terminate(t)

    // Create subscriber with circuit breaker
    subscriber, _ := events.NewSubscriber(redisClient, "test", logger)
    subscriber.Router().AddMiddleware(
        events.WithCircuitBreaker("test-handler", 2, 5*time.Second, logger),
    )

    // Register failing handler
    failCount := 0
    subscriber.Subscribe("test-channel", func(ctx context.Context, envelope *events.Envelope) error {
        failCount++
        if failCount <= 3 {
            return errors.New("simulated failure")
        }
        return nil
    })

    // Publish 5 messages
    publisher.Publish(ctx, "test-channel", "test-event", payload, "corr-id")
    // ... publish 5 times

    // Assert: Circuit should be OPEN after 2 failures
    assert.Equal(t, StateOpen, cb.State())
}
```

---

## Rollback Plan

### Phase 1: Circuit Breaker

**If circuit breaker causes issues:**
```go
// Remove middleware
subscriber.Router().AddMiddleware(
    // events.WithCircuitBreaker(...), // COMMENTED OUT
    events.WithRecovery(logger),
    events.WithRetry(3, time.Second, logger),
)
```

### Phase 2: DLQ

**If DLQ fills up too fast:**
```go
// Increase max retries temporarily
events.WithDLQ(dlqPublisher, 10, logger) // Was 3, now 10

// Or disable DLQ temporarily
// events.WithDLQ(...), // COMMENTED OUT
```

### Phase 3: OpenTelemetry

**If tracing overhead too high:**
```go
// Disable tracing middleware
// events.WithTracing("service-name"), // COMMENTED OUT

// Or reduce sampling rate
tp := initTracer("service", "endpoint", tracesdk.WithSampler(tracesdk.TraceIDRatioBased(0.1))) // 10% sampling
```

---

## References

### Related Documents

- [EVENT_DRIVEN_ARCHITECTURE.md](../architecture/EVENT_DRIVEN_ARCHITECTURE.md) - Full event-driven design
- [RAS_ADAPTER_ROADMAP.md](RAS_ADAPTER_ROADMAP.md) - RAS Adapter implementation
- [go-services/shared/events/README.md](../../go-services/shared/events/README.md) - Events library docs

### External Resources

**Circuit Breaker Pattern:**
- Martin Fowler: https://martinfowler.com/bliki/CircuitBreaker.html
- Microsoft: https://docs.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker

**Dead Letter Queue:**
- AWS SQS DLQ: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
- Google Cloud Pub/Sub DLQ: https://cloud.google.com/pubsub/docs/dead-letter-topics

**OpenTelemetry:**
- Official Docs: https://opentelemetry.io/docs/
- Go SDK: https://github.com/open-telemetry/opentelemetry-go

**Watermill:**
- Official Docs: https://watermill.io/docs/
- Middleware: https://watermill.io/docs/middlewares/

---

## Version History

- **v1.0 (2025-11-20):** Initial roadmap
  - Phase 1: Circuit Breaker + DLQ (2 weeks)
  - Phase 2: OpenTelemetry (1 week)
  - Phase 3: Rate Limiting + Schema Validation + Priority + Bulkhead (1.5 weeks)
  - Total: 4.5 weeks

**Authors:** AI Orchestrator + AI Architect

**Status:** ✅ Active Roadmap - Ready for implementation
