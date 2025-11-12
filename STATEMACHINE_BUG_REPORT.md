# Bug Report: Worker State Machine (Task 1.2)

**Дата:** 2025-11-12
**Статус:** 3 потенциальных проблемы найдено (LOW-MEDIUM приоритет)

---

## Найденные проблемы

### 1. ⚠️ MEDIUM: defer cancel() в цикле (waitForEvent)

**Файл:** `events.go`, функция `waitForEvent()`
**Строка:** примерно 50-70
**Приоритет:** MEDIUM (утечка ресурсов, но не критично)

#### Описание

```go
for attempts < maxAttempts {
    attempts++
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()  // ← ПРОБЛЕМА!

    select {
    case envelope := <-sm.eventChan:
        // ...
    case <-timeoutCtx.Done():
        if attempts < maxAttempts {
            delay := sm.calculateBackoff(attempts)
            time.Sleep(delay)
            continue
        }
        return nil, fmt.Errorf("timeout waiting for event...")
    }
}
```

#### Проблема

Когда используется `defer` в цикле, все вызовы `cancel()` будут выполнены **в конце функции**, не в конце каждой итерации.

Это означает:
- При MaxRetries=3, создаются 3 context и 3 cancel функции
- Все 3 cancel() выполнятся в конце, потратив ресурсы
- Context будет оставаться active между итерациями (утечка памяти)

#### Решение

Переместить `cancel()` вне defer:

```go
for attempts < maxAttempts {
    attempts++
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)

    select {
    case envelope := <-sm.eventChan:
        cancel()  // Немедленно отменяем context
        // ... остальной код
    case <-timeoutCtx.Done():
        cancel()  // Отменяем context
        if attempts < maxAttempts {
            delay := sm.calculateBackoff(attempts)
            time.Sleep(delay)
            continue
        }
        return nil, fmt.Errorf("timeout waiting for event...")
    }
}
```

Или еще лучше - использовать named function для cleanup:

```go
for attempts < maxAttempts {
    attempts++
    if err := sm.waitForEventOnce(ctx, expectedEventType, timeout); err == nil {
        return envelope, nil
    }
}

func (sm *ExtensionInstallStateMachine) waitForEventOnce(
    ctx context.Context,
    expectedEventType string,
    timeout time.Duration,
) (*events.Envelope, error) {
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()  // Безопасно в отдельной функции

    select {
    case envelope := <-sm.eventChan:
        return envelope, nil
    case <-timeoutCtx.Done():
        return nil, timeoutCtx.Err()
    }
}
```

#### Влияние

- **Performance:** Low - утечка ресурсов небольшая (3 context вместо 1)
- **Correctness:** Low - код все еще работает, just inefficient
- **Test Coverage:** Not detected (waitForEvent НЕ тестируется)

---

### 2. ⚠️ LOW: Race condition при Close() eventChan

**Файл:** `state_machine.go`, функция `Close()`
**Строка:** примерно 175-195
**Приоритет:** LOW (редкий случай, но потенциально опасно)

#### Описание

```go
func (sm *ExtensionInstallStateMachine) Close() error {
    sm.mu.Lock()
    defer sm.mu.Unlock()

    if sm.closed {
        return nil
    }

    sm.cancel()
    sm.closed = true

    // Close channel safely
    select {
    case <-sm.eventChan:
    default:
        close(sm.eventChan)  // ← ПРОБЛЕМА!
    }

    return nil
}
```

#### Проблема

Race condition между Close() и listenEvents():

```
Goroutine 1 (Close)          Goroutine 2 (listenEvents)
─────────────────────────────────────────────────────
sm.cancel()
                             <-ctx.Done() returns
sm.closed = true
                             envelope := newEvent
                             select {
                             case sm.eventChan <- envelope:  ← PANIC!
                             }
close(sm.eventChan)  ← Sending on closed channel
```

Если listenEvents() пытается писать в eventChan после того, как Close() его закрыл, будет **panic**.

#### Решение

Использовать atomic flag или sync.Once:

```go
func (sm *ExtensionInstallStateMachine) Close() error {
    sm.mu.Lock()
    defer sm.mu.Unlock()

    if sm.closed {
        return nil
    }

    sm.closed = true
    sm.cancel()  // Отменяем context ДО close channel

    // Даем время goroutines завершиться
    // или используем WaitGroup для синхронизации
    time.Sleep(10 * time.Millisecond)

    // Drain channel перед close
    select {
    case <-sm.eventChan:
    default:
    }

    close(sm.eventChan)
    return nil
}
```

Или лучше - использовать sync.Once:

```go
type ExtensionInstallStateMachine struct {
    closeOnce sync.Once
    // ... остальное ...
}

func (sm *ExtensionInstallStateMachine) Close() error {
    var err error
    sm.closeOnce.Do(func() {
        sm.mu.Lock()
        defer sm.mu.Unlock()

        sm.cancel()
        sm.closed = true

        // safe close
        select {
        case <-sm.eventChan:
        default:
            close(sm.eventChan)
        }
    })
    return err
}
```

#### Влияние

- **Probability:** LOW - требует specific timing
- **Severity:** CRITICAL - приведет к panic и crash процесса
- **Test Coverage:** Not detected (Close() работает, но не тестируется с concurrent goroutines)

---

### 3. ⚠️ LOW: Goroutine leak в listenEvents()

**Файл:** `state_machine.go`, функция `listenEvents()`
**Строка:** примерно 197-220
**Приоритет:** LOW (утечка памяти, но небольшая)

#### Описание

```go
func (sm *ExtensionInstallStateMachine) listenEvents(ctx context.Context) {
    // Subscribe to events for this correlation ID
    handler := func(ctx context.Context, envelope *events.Envelope) error {
        if envelope.CorrelationID == sm.CorrelationID {
            select {
            case sm.eventChan <- envelope:
            case <-ctx.Done():
                return ctx.Err()
            }
        }
        return nil
    }

    // Subscribe to orchestrator events
    sm.subscriber.Subscribe("events:orchestrator:*", handler)
    // ← Нет явного Unsubscribe()

    // Wait for context cancellation to prevent goroutine leak
    <-ctx.Done()
}
```

#### Проблема

Goroutine listenEvents() остается in-memory после Close() потому что Subscriber продолжает удерживать обработчик (handler).

Sequence:
1. Run() запускает `go sm.listenEvents(ctx)`
2. listenEvents() вызывает `sm.subscriber.Subscribe(..., handler)`
3. Subscriber регистрирует handler в своем map
4. Close() вызывает `sm.cancel()` - отменяет контекст
5. listenEvents() получает `<-ctx.Done()` и выходит
6. НО: Subscriber все еще имеет reference на handler в своем map
7. Goroutine остается жить, пока Subscriber не очистится

#### Решение

Явно отписаться от события:

```go
// Добавить Unsubscribe метод в интерфейс EventSubscriber
type EventSubscriber interface {
    Subscribe(channel string, handler func(context.Context, *events.Envelope) error) error
    Unsubscribe(channel string) error  // ← ДОБАВИТЬ
    Close() error
}

// Использовать в listenEvents():
func (sm *ExtensionInstallStateMachine) listenEvents(ctx context.Context) {
    handler := func(ctx context.Context, envelope *events.Envelope) error {
        if envelope.CorrelationID == sm.CorrelationID {
            select {
            case sm.eventChan <- envelope:
            case <-ctx.Done():
                return ctx.Err()
            }
        }
        return nil
    }

    sm.subscriber.Subscribe("events:orchestrator:*", handler)

    <-ctx.Done()

    // Explicitly unsubscribe to prevent goroutine leak
    sm.subscriber.Unsubscribe("events:orchestrator:*")
}
```

Или использовать context-aware cleanup:

```go
func (sm *ExtensionInstallStateMachine) listenEvents(ctx context.Context) {
    handler := func(ctx context.Context, envelope *events.Envelope) error {
        if envelope.CorrelationID == sm.CorrelationID {
            select {
            case sm.eventChan <- envelope:
            case <-ctx.Done():
                return ctx.Err()
            }
        }
        return nil
    }

    // Использовать sync.WaitGroup для отслеживания goroutine
    sm.listenerDone = make(chan struct{})
    defer close(sm.listenerDone)

    sm.subscriber.Subscribe("events:orchestrator:*", handler)
    <-ctx.Done()
}
```

#### Влияние

- **Probability:** MEDIUM - происходит после каждого завершения workflow
- **Severity:** LOW - goroutine leak небольшой (1 goroutine per workflow)
- **Memory Impact:** ~1KB per goroutine, для 100 workflows = 100KB утечки
- **Test Coverage:** Not detected (нет concurrent Close() testing)

---

## Summary table

| # | Проблема | Файл | Приоритет | Тип | Влияние |
|---|----------|------|-----------|-----|---------|
| 1 | defer cancel() в цикле | events.go | MEDIUM | Resource leak | Low (утечка памяти context) |
| 2 | Race condition Close() | state_machine.go | LOW | Panic risk | Critical (crash на панику) |
| 3 | Goroutine leak | state_machine.go | LOW | Memory leak | Low (~1KB per workflow) |

---

## Рекомендации по приоритизации

### Немедленно (Week 2.1):
- [ ] Добавить тесты для concurrent Close() (problem #2)
- [ ] Исправить defer cancel() в цикле (problem #1)

### В течение Week 2:
- [ ] Добавить Unsubscribe() метод (problem #3)
- [ ] Добавить WaitGroup для goroutine cleanup

### Integration Testing (Week 3):
- [ ] Load test с 100+ workflows (выявит утечки)
- [ ] Stress test с rapid Close() calls
- [ ] Memory profiling

---

## Как эти проблемы не были обнаружены тестами?

1. **defer cancel() в цикле**: waitForEvent() НЕ тестируется (0% coverage)
2. **Race condition Close()**: Close() тестируется только с single goroutine, без concurrent access
3. **Goroutine leak**: listenEvents() НЕ тестируется, нет leak detection

Для выявления этих проблем нужны:
- ✅ Stress tests с concurrent access
- ✅ Integration tests с full event loop
- ✅ Memory profiling / goroutine leak detection
- ✅ Race condition detector (`go test -race`)

---

**Подготовлено:** QA Engineer
**Дата:** 2025-11-12
**Статус:** Ready for review and prioritization
