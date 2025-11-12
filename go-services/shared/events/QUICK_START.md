# Events Library - Quick Start

## Установка

```bash
cd go-services/shared
go get github.com/ThreeDotsLabs/watermill@v1.5.1
go get github.com/ThreeDotsLabs/watermill-redisstream@v1.4.4
go get github.com/redis/go-redis/v9@v9.16.0
go mod tidy
```

## Минимальный пример (Publisher)

```go
package main

import (
    "context"
    "log"
    
    "github.com/commandcenter1c/commandcenter/shared/events"
    "github.com/redis/go-redis/v9"
    "github.com/ThreeDotsLabs/watermill"
)

func main() {
    // 1. Создать Redis клиент
    redisClient := redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })
    defer redisClient.Close()
    
    // 2. Создать logger
    logger := watermill.NewStdLogger(false, false)
    
    // 3. Создать publisher
    publisher, err := events.NewPublisher(redisClient, "my-service", logger)
    if err != nil {
        log.Fatal(err)
    }
    defer publisher.Close()
    
    // 4. Опубликовать событие
    payload := map[string]string{
        "action": "user_created",
        "user_id": "12345",
    }
    
    err = publisher.Publish(
        context.Background(),
        "user-events",           // channel
        "events:user:created",   // event type
        payload,                 // payload
        "",                      // correlation_id (auto-generated)
    )
    
    if err != nil {
        log.Fatal(err)
    }
    
    log.Println("Event published successfully!")
}
```

## Минимальный пример (Subscriber)

```go
package main

import (
    "context"
    "encoding/json"
    "log"
    "os"
    "os/signal"
    "syscall"
    
    "github.com/commandcenter1c/commandcenter/shared/events"
    "github.com/redis/go-redis/v9"
    "github.com/ThreeDotsLabs/watermill"
)

func main() {
    // 1. Создать Redis клиент
    redisClient := redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })
    defer redisClient.Close()
    
    // 2. Создать logger
    logger := watermill.NewStdLogger(false, false)
    
    // 3. Создать subscriber
    subscriber, err := events.NewSubscriber(
        redisClient,
        "my-consumer-group", // consumer group name
        logger,
    )
    if err != nil {
        log.Fatal(err)
    }
    defer subscriber.Close()
    
    // 4. Зарегистрировать handler
    err = subscriber.Subscribe("user-events", func(ctx context.Context, envelope *events.Envelope) error {
        log.Printf("Received event: %s (correlation_id: %s)", 
            envelope.EventType, envelope.CorrelationID)
        
        // Parse payload
        var payload map[string]string
        if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
            return err
        }
        
        log.Printf("User created: %s", payload["user_id"])
        return nil
    })
    
    if err != nil {
        log.Fatal(err)
    }
    
    // 5. Настроить graceful shutdown
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()
    
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    
    go func() {
        <-sigChan
        log.Println("Shutting down...")
        cancel()
    }()
    
    // 6. Запустить subscriber (blocking)
    log.Println("Subscriber started, waiting for events...")
    if err := subscriber.Run(ctx); err != nil {
        log.Fatal(err)
    }
    
    log.Println("Subscriber stopped")
}
```

## С Middleware

```go
// Add middleware to subscriber
subscriber.Router().AddMiddleware(
    // Logging
    events.WithLogging(logger),
    
    // Panic recovery
    events.WithRecovery(logger),
    
    // Retry with exponential backoff (3 attempts, 5s initial delay)
    events.WithRetry(3, 5*time.Second, logger),
    
    // Timeout (30 seconds)
    events.WithTimeout(30*time.Second, logger),
    
    // Idempotency check (24 hours TTL)
    events.WithIdempotency(redisClient, 24*time.Hour, logger),
)

// Register handlers AFTER adding middleware
subscriber.Subscribe("my-channel", myHandler)
```

## Полная документация

См. [README.md](README.md) для полной документации с примерами и best practices.
