# Events Library

Production-ready event-driven library для CommandCenter1C, построенная на Watermill + Redis Streams.

## Возможности

- **Message Envelope**: Стандартизированный формат сообщений с correlation ID, timestamps, metadata
- **Publisher**: Простая публикация событий с автогенерацией IDs и timestamps
- **Subscriber**: Подписка на события с consumer groups для масштабирования
- **Middleware**: Retry, idempotency, logging, timeout, panic recovery
- **Type Safety**: Строгая типизация событий через Go structs
- **Graceful Shutdown**: Контекст-based управление жизненным циклом
- **Error Handling**: Детальная обработка ошибок Redis unavailable, malformed messages, handler panics

## Архитектура

```
Publisher → Redis Streams (channel) → Consumer Group → Subscriber → Handler
```

**Преимущества Redis Streams над Pub/Sub:**
- Персистентность сообщений
- Consumer groups для load balancing
- Acknowledgments (ACK/NACK)
- Retry механизмы
- Message history

## Quick Start

### 1. Создание Publisher

```go
import (
    "context"
    "github.com/commandcenter1c/commandcenter/shared/events"
    "github.com/redis/go-redis/v9"
    "github.com/ThreeDotsLabs/watermill"
)

// Создать Redis клиент
redisClient := redis.NewClient(&redis.Options{
    Addr: "localhost:6379",
})

// Создать logger
logger := watermill.NewStdLogger(false, false)

// Создать publisher
publisher, err := events.NewPublisher(redisClient, "my-service", logger)
if err != nil {
    log.Fatal(err)
}
defer publisher.Close()

// Опубликовать событие
type InfobaseLockPayload struct {
    InfobaseID string `json:"infobase_id"`
    Reason     string `json:"reason"`
}

payload := InfobaseLockPayload{
    InfobaseID: "uuid-123",
    Reason:     "maintenance",
}

err = publisher.Publish(
    context.Background(),
    "commands:cluster-service",
    "commands:cluster-service:infobase:lock",
    payload,
    "", // correlation_id will be auto-generated
)
```

### 2. Создание Subscriber

```go
import (
    "context"
    "log"
    "github.com/commandcenter1c/commandcenter/shared/events"
    "github.com/redis/go-redis/v9"
    "github.com/ThreeDotsLabs/watermill"
)

// Создать Redis клиент
redisClient := redis.NewClient(&redis.Options{
    Addr: "localhost:6379",
})

// Создать logger
logger := watermill.NewStdLogger(false, false)

// Создать subscriber
subscriber, err := events.NewSubscriber(
    redisClient,
    "cluster-service-consumer", // consumer group
    logger,
)
if err != nil {
    log.Fatal(err)
}
defer subscriber.Close()

// Зарегистрировать handler
err = subscriber.Subscribe("commands:cluster-service", func(ctx context.Context, envelope *events.Envelope) error {
    log.Printf("Received event: %s (correlation_id: %s)", envelope.EventType, envelope.CorrelationID)

    // Parse payload
    var payload InfobaseLockPayload
    if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
        return err
    }

    // Process event
    log.Printf("Locking infobase %s: %s", payload.InfobaseID, payload.Reason)

    return nil
})

// Запустить subscriber (blocking)
ctx := context.Background()
if err := subscriber.Run(ctx); err != nil {
    log.Fatal(err)
}
```

### 3. Graceful Shutdown

```go
import (
    "context"
    "os"
    "os/signal"
    "syscall"
)

// Create subscriber
subscriber, err := events.NewSubscriber(redisClient, "my-consumer", logger)
if err != nil {
    log.Fatal(err)
}

// Register handlers
subscriber.Subscribe("my-channel", myHandler)

// Create context for graceful shutdown
ctx, cancel := context.WithCancel(context.Background())

// Handle shutdown signals
sigChan := make(chan os.Signal, 1)
signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

go func() {
    <-sigChan
    log.Println("Shutting down gracefully...")
    cancel()
}()

// Run subscriber (blocks until context is cancelled)
if err := subscriber.Run(ctx); err != nil {
    log.Fatal(err)
}

// Cleanup
subscriber.Close()
```

## Advanced Usage

### Использование Correlation ID для трейсинга

```go
// Publisher: создать correlation ID
correlationID := events.GenerateCorrelationID()

// Publish с correlation ID
err := publisher.Publish(ctx, "channel", "event-type", payload, correlationID)

// Subscriber: использовать correlation ID
handler := func(ctx context.Context, envelope *events.Envelope) error {
    log.Printf("Processing event %s with correlation_id=%s",
        envelope.EventType, envelope.CorrelationID)

    // Можно передать correlation ID в другие сервисы
    return processEvent(envelope.CorrelationID, envelope.Payload)
}
```

### Metadata и Idempotency Key

```go
// Publisher: добавить metadata
metadata := map[string]interface{}{
    "timeout_seconds": 30,
    "priority":       "high",
}

// Generate idempotency key
idempotencyKey := events.GenerateIdempotencyKey(correlationID, eventType)
metadata["idempotency_key"] = idempotencyKey

err := publisher.PublishWithMetadata(
    ctx, "channel", "event-type", payload, correlationID, metadata,
)

// Subscriber: прочитать metadata
handler := func(ctx context.Context, envelope *events.Envelope) error {
    if timeout, ok := envelope.GetMetadata("timeout_seconds"); ok {
        log.Printf("Timeout: %v", timeout)
    }

    idempotencyKey := envelope.GetIdempotencyKey()
    if idempotencyKey != "" {
        // Check if already processed
    }

    return nil
}
```

### Middleware

```go
import (
    "time"
    "github.com/ThreeDotsLabs/watermill/message"
)

// Create subscriber
subscriber, err := events.NewSubscriber(redisClient, "my-consumer", logger)

// Add middleware to router
subscriber.router.AddMiddleware(
    // Logging
    events.WithLogging(logger),

    // Panic recovery
    events.WithRecovery(logger),

    // Retry with exponential backoff
    events.WithRetry(3, time.Second, logger),

    // Timeout
    events.WithTimeout(30*time.Second, logger),

    // Idempotency check
    events.WithIdempotency(redisClient, 24*time.Hour, logger),
)

// Register handlers
subscriber.Subscribe("channel", myHandler)

// Run
subscriber.Run(ctx)
```

## Message Envelope Format

```json
{
  "version": "1.0",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "timestamp": "2025-11-12T10:30:00Z",
  "event_type": "commands:cluster-service:infobase:lock",
  "service_name": "worker",
  "payload": {
    "infobase_id": "uuid-123",
    "reason": "maintenance"
  },
  "metadata": {
    "retry_count": 0,
    "timeout_seconds": 30,
    "idempotency_key": "abc123..."
  }
}
```

## Event Types Convention

Используй следующую конвенцию для event types:

```
<category>:<service>:<entity>:<action>
```

**Примеры:**
- `commands:cluster-service:infobase:lock`
- `commands:cluster-service:infobase:unlock`
- `commands:cluster-service:session:terminate`
- `events:worker:operation:started`
- `events:worker:operation:completed`
- `events:worker:operation:failed`

**Категории:**
- `commands` - команды для выполнения действий
- `events` - события о произошедших изменениях
- `queries` - запросы данных (редко, обычно синхронно)

## Error Handling

```go
// Publisher error handling
err := publisher.Publish(ctx, channel, eventType, payload, correlationID)
if err != nil {
    if errors.Is(err, events.ErrPublisherClosed) {
        // Publisher was closed
    } else if errors.Is(err, events.ErrRedisUnavailable) {
        // Redis is not available
    } else {
        // Other error
    }
}

// Subscriber error handling
handler := func(ctx context.Context, envelope *events.Envelope) error {
    // Validate payload
    if err := envelope.Validate(); err != nil {
        return err // Will NACK the message
    }

    // Process
    if err := doSomething(); err != nil {
        // Return error to NACK (message will be retried)
        return err
    }

    // Success - message will be ACKed
    return nil
}
```

## Best Practices

### 1. Always use Correlation ID

Correlation ID позволяет трейсить события через все сервисы:

```go
// Service A
correlationID := events.GenerateCorrelationID()
publisher.Publish(ctx, "channel-a", "event-a", payload, correlationID)

// Service B (receives event-a)
handlerB := func(ctx context.Context, envelope *events.Envelope) error {
    // Use same correlation ID to publish next event
    publisher.Publish(ctx, "channel-b", "event-b", payload, envelope.CorrelationID)
    return nil
}
```

### 2. Use Idempotency for Critical Operations

```go
// Generate idempotency key from correlation ID and event type
idempotencyKey := events.GenerateIdempotencyKey(correlationID, eventType)

metadata := map[string]interface{}{
    "idempotency_key": idempotencyKey,
}

publisher.PublishWithMetadata(ctx, channel, eventType, payload, correlationID, metadata)
```

### 3. Handle Panics

Всегда используй `WithRecovery` middleware или встроенную panic recovery в subscriber:

```go
subscriber.router.AddMiddleware(events.WithRecovery(logger))
```

### 4. Set Timeouts

```go
// Per-message timeout
subscriber.router.AddMiddleware(events.WithTimeout(30*time.Second, logger))

// Or in metadata
metadata["timeout_seconds"] = 30
```

### 5. Validate Payloads

```go
handler := func(ctx context.Context, envelope *events.Envelope) error {
    var payload MyPayload
    if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
        return fmt.Errorf("invalid payload: %w", err)
    }

    // Validate
    if payload.ID == "" {
        return errors.New("missing ID")
    }

    return processPayload(payload)
}
```

### 6. Graceful Shutdown

```go
// Create context with cancellation
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

// Handle OS signals
sigChan := make(chan os.Signal, 1)
signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

go func() {
    <-sigChan
    cancel()
}()

// Run subscriber
subscriber.Run(ctx) // Will stop when context is cancelled

// Cleanup
subscriber.Close()
publisher.Close()
```

## Testing

См. примеры в `tests/`:
- `publisher_test.go` - unit tests для Publisher
- `subscriber_test.go` - unit tests для Subscriber
- `envelope_test.go` - tests для Envelope marshaling
- `integration_test.go` - интеграционные тесты с Redis

Запуск тестов:

```bash
cd go-services/shared/events
go test -v ./...
```

## Configuration

```go
// Create config
config := events.DefaultConfig()
config.RedisAddr = "localhost:6379"
config.RedisPassword = ""
config.ConsumerGroup = "my-consumer"
config.MaxRetries = 3
config.RetryDelay = 5 * time.Second

// Validate
if err := config.Validate(); err != nil {
    log.Fatal(err)
}

// Use with Publisher/Subscriber
redisClient := redis.NewClient(&redis.Options{
    Addr:     config.RedisAddr,
    Password: config.RedisPassword,
    DB:       config.RedisDB,
})
```

## Troubleshooting

### Redis Connection Errors

```go
publisher, err := events.NewPublisher(redisClient, serviceName, logger)
if err != nil {
    if errors.Is(err, events.ErrRedisUnavailable) {
        // Redis is not available - retry connection
    }
}
```

### Messages not being processed

1. Проверь что subscriber запущен: `subscriber.Run(ctx)`
2. Проверь consumer group name - должен быть одинаковый для load balancing
3. Проверь handler errors - если handler возвращает error, message будет NACK и retry

### Duplicate message processing

Используй idempotency middleware:

```go
subscriber.router.AddMiddleware(
    events.WithIdempotency(redisClient, 24*time.Hour, logger),
)
```

## Performance

**Benchmarks** (на локальной машине с Redis 7):
- Publisher: ~10,000 msg/sec
- Subscriber: ~8,000 msg/sec
- Latency: ~1-2ms (local Redis)

**Масштабирование:**
- Consumer groups позволяют запустить несколько subscribers для load balancing
- Redis Streams поддерживает millions msg/sec
- Используй connection pooling для Redis client

## Prometheus Metrics

Library автоматически экспортирует метрики для observability:

### Доступные метрики

- `events_messages_published_total` - Всего опубликованных сообщений (labels: service, channel, event_type)
- `events_messages_processed_total` - Всего обработанных сообщений (labels: channel, event_type, status)
- `events_processing_duration_seconds` - Гистограмма времени обработки сообщений
- `events_publish_duration_seconds` - Гистограмма времени публикации сообщений
- `events_concurrent_handlers` - Gauge текущего количества concurrent handlers

### Использование

Метрики собираются автоматически. Для экспорта в Prometheus:

```go
import (
    "net/http"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

http.Handle("/metrics", promhttp.Handler())
http.ListenAndServe(":9090", nil)
```

### Grafana Dashboard

Примеры Prometheus queries:

```promql
# Publish rate
rate(events_messages_published_total[5m])

# Processing error rate
rate(events_messages_processed_total{status="error"}[5m])

# P95 processing latency
histogram_quantile(0.95, rate(events_processing_duration_seconds_bucket[5m]))

# P99 publish latency
histogram_quantile(0.99, rate(events_publish_duration_seconds_bucket[5m]))

# Concurrent handlers by consumer group
events_concurrent_handlers
```

## Backpressure & Rate Limiting

### Max Concurrent Handlers

По умолчанию subscriber ограничен 100 concurrent handlers. Для изменения:

```go
subscriber.SetMaxConcurrency(50) // Limit to 50 concurrent
```

### Payload Size Limit

По умолчанию max payload size = 1MB. Для защиты от DoS атак через огромные сообщения.

## Redis Reconnect

Library автоматически переподключается к Redis при сбое:

```go
// NewPublisher/NewSubscriber automatically:
// 1. Check Redis availability
// 2. Wait for Redis (exponential backoff)
// 3. Retry connection with max retries
```

Config опции:

```go
config.EnableAutoReconnect = true
config.ReconnectInterval = 5 * time.Second
config.MaxReconnectRetries = 0 // 0 = infinite retries
```

## Roadmap

- [x] ~~Add Prometheus metrics~~ (✅ Done)
- [x] ~~Add backpressure handling~~ (✅ Done)
- [x] ~~Add payload size limits~~ (✅ Done)
- [x] ~~Add Redis auto-reconnect~~ (✅ Done)
- [ ] Add OpenTelemetry tracing integration
- [ ] Add dead letter queue for failed messages
- [ ] Add message priority support
- [ ] Add schema validation (JSON Schema / Protobuf)

## License

Internal use only - CommandCenter1C project.
