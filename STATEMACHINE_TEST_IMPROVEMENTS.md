# Test Improvements: Worker State Machine (Task 1.2)

**Дата:** 2025-11-12
**Статус:** Рекомендации по расширению coverage с 34.4% до 70%+

---

## Текущее состояние

**Тесты:** 14/14 PASS ✅
**Coverage:** 34.4%
**Проблема:** Handlers и main loop НЕ тестируются

```
✅ Tested (100%):       compensation.go, config.go (partial)
⚠️ Partial (50-99%):    state_machine.go, events.go (partial)
❌ Not tested (0%):     handlers.go, persistence.go (mostly), Run(), listenEvents()
```

---

## Рекомендуемые тесты (Приоритет HIGH)

### 1. Event Waiting Tests (5-7 тестов)

**Цель:** Протестировать waitForEvent() - самая сложная функция

#### 1.1 Happy path - событие приходит сразу

```go
func TestStateMachine_WaitForEvent_Success(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)

    // Симулируем событие
    go func() {
        time.Sleep(10 * time.Millisecond)
        envelope := &events.Envelope{
            MessageID:     "msg-123",
            EventType:     "expected.event",
            CorrelationID: "corr1",
        }
        sm.eventChan <- envelope
    }()

    // Ждем события
    envelope, err := sm.waitForEvent(ctx, "expected.event", 5*time.Second)

    assert.NoError(t, err)
    assert.NotNil(t, envelope)
    assert.Equal(t, "expected.event", envelope.EventType)
}
```

#### 1.2 Неправильный тип события - игнорируется

```go
func TestStateMachine_WaitForEvent_IgnoreWrongType(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)

    go func() {
        // Сначала отправляем неправильный тип
        sm.eventChan <- &events.Envelope{
            MessageID:     "msg-123",
            EventType:     "wrong.event",
            CorrelationID: "corr1",
        }

        time.Sleep(10 * time.Millisecond)

        // Потом правильный тип
        sm.eventChan <- &events.Envelope{
            MessageID:     "msg-124",
            EventType:     "expected.event",
            CorrelationID: "corr1",
        }
    }()

    envelope, err := sm.waitForEvent(ctx, "expected.event", 5*time.Second)

    assert.NoError(t, err)
    assert.NotNil(t, envelope)
    assert.Equal(t, "expected.event", envelope.EventType)
    assert.Equal(t, "msg-124", envelope.MessageID)
}
```

#### 1.3 Таймаут при ожидании

```go
func TestStateMachine_WaitForEvent_Timeout(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)

    // Ничего не отправляем - пусть timeout сработает
    envelope, err := sm.waitForEvent(ctx, "expected.event", 100*time.Millisecond)

    assert.Error(t, err)
    assert.Nil(t, envelope)
    assert.Contains(t, err.Error(), "timeout")
}
```

#### 1.4 Retry logic с exponential backoff

```go
func TestStateMachine_WaitForEvent_RetryWithBackoff(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    config := DefaultConfig()
    config.MaxRetries = 3
    config.RetryInitialDelay = 10 * time.Millisecond

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, config)

    attempts := 0
    go func() {
        time.Sleep(150 * time.Millisecond)  // После первого таймаута
        attempts++
        envelope := &events.Envelope{
            MessageID:     "msg-123",
            EventType:     "expected.event",
            CorrelationID: "corr1",
        }
        sm.eventChan <- envelope
    }()

    start := time.Now()
    envelope, err := sm.waitForEvent(ctx, "expected.event", 50*time.Millisecond)
    elapsed := time.Since(start)

    assert.NoError(t, err)
    assert.NotNil(t, envelope)
    assert.Greater(t, elapsed, 100*time.Millisecond)  // Был retry
}
```

#### 1.5 Деduplication при retry

```go
func TestStateMachine_WaitForEvent_DuplicateIgnored(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)

    envelope := &events.Envelope{
        MessageID:     "msg-123",
        EventType:     "expected.event",
        CorrelationID: "corr1",
    }

    go func() {
        // Отправляем одно и то же событие дважды
        sm.eventChan <- envelope
        time.Sleep(10 * time.Millisecond)
        sm.eventChan <- envelope
    }()

    // Первый вызов должен обработать первое событие
    result1, _ := sm.waitForEvent(ctx, "expected.event", 1*time.Second)
    assert.NotNil(t, result1)

    // Второе одинаковое событие должно быть пропущено (duplicate)
    // вместо этого должен быть timeout или ошибка
}
```

---

### 2. Handler Tests (требуют частичного mock event loop)

#### 2.1 handleInit успех

```go
func TestStateMachine_HandleInit_Success(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
    sm.State = StateInit
    sm.ClusterID = "cluster1"
    sm.InfobaseID = "infobase1"

    // Симулируем успешное выполнение
    go func() {
        // Проверяем что lock command был опубликован
        time.Sleep(10 * time.Millisecond)

        // Отправляем locked event
        sm.eventChan <- &events.Envelope{
            MessageID:     "msg-123",
            EventType:     "cluster.infobase.locked",
            CorrelationID: "corr1",
        }
    }()

    err := sm.handleInit(ctx)

    assert.NoError(t, err)
    assert.Equal(t, StateJobsLocked, sm.State)

    // Verify command was published
    assert.Equal(t, 1, publisher.GetPublishedCount())
    lastCall := publisher.GetLastPublished()
    assert.Equal(t, "cluster.infobase.lock", lastCall.EventType)
}
```

#### 2.2 handleInit timeout

```go
func TestStateMachine_HandleInit_Timeout(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    config := DefaultConfig()
    config.TimeoutLockJobs = 50 * time.Millisecond
    config.MaxRetries = 1

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, config)
    sm.State = StateInit

    // Ничего не отправляем - пусть timeout сработает
    err := sm.handleInit(ctx)

    assert.Error(t, err)
    assert.Contains(t, err.Error(), "timeout")
}
```

#### 2.3 handleJobsLocked success

```go
func TestStateMachine_HandleJobsLocked_Success(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
    sm.State = StateJobsLocked
    sm.ClusterID = "cluster1"
    sm.InfobaseID = "infobase1"

    go func() {
        time.Sleep(10 * time.Millisecond)
        sm.eventChan <- &events.Envelope{
            MessageID:     "msg-456",
            EventType:     "cluster.sessions.closed",
            CorrelationID: "corr1",
        }
    }()

    err := sm.handleJobsLocked(ctx)

    assert.NoError(t, err)
    assert.Equal(t, StateSessionsClosed, sm.State)
}
```

---

### 3. Configuration Validation Tests (добавить)

#### 3.1 Полная валидация всех timeout полей

```go
func TestStateMachine_Config_Validate_CompleteFields(t *testing.T) {
    tests := []struct {
        name      string
        config    *Config
        wantError bool
        errorMsg  string
    }{
        {
            name:      "all valid",
            config:    DefaultConfig(),
            wantError: false,
        },
        {
            name: "invalid TimeoutInstall",
            config: &Config{
                TimeoutLockJobs:  30 * time.Second,
                TimeoutTerminate: 90 * time.Second,
                TimeoutInstall:   0,
            },
            wantError: true,
            errorMsg:  "TimeoutInstall",
        },
        {
            name: "invalid TimeoutUnlock",
            config: &Config{
                TimeoutLockJobs:   30 * time.Second,
                TimeoutTerminate:  90 * time.Second,
                TimeoutInstall:    5 * time.Minute,
                TimeoutUnlock:     0,
            },
            wantError: true,
            errorMsg:  "TimeoutUnlock",
        },
        {
            name: "invalid TimeoutCompensation",
            config: &Config{
                TimeoutLockJobs:      30 * time.Second,
                TimeoutTerminate:     90 * time.Second,
                TimeoutInstall:       5 * time.Minute,
                TimeoutUnlock:        30 * time.Second,
                TimeoutCompensation:  0,
            },
            wantError: true,
            errorMsg:  "TimeoutCompensation",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := tt.config.Validate()
            if tt.wantError {
                assert.Error(t, err)
                assert.Contains(t, err.Error(), tt.errorMsg)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

---

### 4. Compensation Scenario Tests

#### 4.1 Полный workflow с compensation

```go
func TestStateMachine_FullWorkflow_WithCompensation(t *testing.T) {
    ctx := context.Background()
    publisher := NewMockPublisher()
    subscriber := NewMockSubscriber()

    sm, _ := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)

    compensated := []string{}

    // Simulate: init -> jobs_locked -> error -> compensation
    sm.State = StateJobsLocked
    sm.pushCompensation("unlock", func(ctx context.Context) error {
        compensated = append(compensated, "unlock")
        return nil
    })

    // Trigger error (transition to compensating)
    sm.transitionTo(StateCompensating)

    // Execute compensations
    err := sm.executeCompensations(ctx)

    assert.NoError(t, err)
    assert.Equal(t, StateFailed, sm.State)
    assert.Equal(t, []string{"unlock"}, compensated)
}
```

---

## Рекомендуемые метрики для успеха

| Метрика | Текущее | Целевое | Примечание |
|---------|---------|---------|-----------|
| Total tests | 14 | 25-30 | +11-16 новых тестов |
| Coverage | 34.4% | 65-70% | В основном handlers |
| handlers.go coverage | 0% | 80%+ | Критично |
| waitForEvent() coverage | 0% | 90%+ | Критично |
| Run() coverage | 0% | 50%+ | Допустимо (требует full loop) |
| Test execution time | 0.755s | <2.0s | Все еще fast |

---

## Пошаговый план

### Week 2.1 (текущая):
- [ ] Добавить 5 tests для waitForEvent()
- [ ] Добавить 3 tests для handleInit()
- [ ] Исправить Config.Validate() для всех полей
- **Target:** +8 тестов, +20% coverage

### Week 2.2:
- [ ] Добавить тесты для handleJobsLocked(), handleSessionsClosed()
- [ ] Добавить compensation scenario tests
- [ ] Добавить concurrent access tests (race conditions)
- **Target:** +10 тестов, +15% coverage

### Week 3.1 (Integration):
- [ ] Активировать state_machine_integration_test.go.skip
- [ ] Добавить full workflow tests
- [ ] Добавить Redis persistence tests
- **Target:** +15 tests, +20% coverage

### Итого:
- Week 2: 18 новых unit tests → 60-65% coverage
- Week 3: 15 integration tests → 75-80% coverage

---

## Tools and Utilities

### 1. Coverage monitoring

```bash
# Generate coverage report
go test ./internal/statemachine/... -coverprofile=coverage.out

# Show coverage percentage
go tool cover -func=coverage.out

# Generate HTML report
go tool cover -html=coverage.out -o coverage.html

# Show uncovered lines
go tool cover -html=coverage.out | grep red
```

### 2. Race condition detection

```bash
# Run with race detector
go test -race ./internal/statemachine/...

# This will detect concurrent access issues
```

### 3. Mock improvements needed

```go
// Add to mocks_test.go for better testing:

type MockPublisher struct {
    PublishDelay time.Duration  // Simulate slow publish
    PublishError error           // Configurable error
    // ...
}

type MockSubscriber struct {
    SubscribeError error          // Configurable error
    Handlers map[string]bool      // Track subscriptions
    // ...
}
```

---

## Success Criteria

✅ **Unit tests DONE when:**
- [x] 14 existing tests PASS
- [ ] 25+ total tests (add 11+)
- [ ] 60%+ coverage
- [ ] All handler tests exist
- [ ] waitForEvent() fully tested
- [ ] No obvious bugs in tests

✅ **Ready for Integration when:**
- [ ] state_machine_integration_test.go enabled
- [ ] Full workflow tested with Redis
- [ ] 70%+ total coverage
- [ ] <2 second test execution

---

**Подготовлено:** QA Engineer
**Дата:** 2025-11-12
**Статус:** Ready for implementation
