# Developer Checklist: Worker State Machine Fixes

**For:** Go Developer
**Date:** 2025-11-12
**Sprint:** 2.1-2.2

---

## Issue Tracker

### Issue #1: defer cancel() in loop

**File:** `go-services/worker/internal/statemachine/events.go`
**Function:** `waitForEvent()`
**Severity:** MEDIUM
**Time to Fix:** 5-10 minutes

#### Current Code Problem
```go
for attempts < maxAttempts {
    attempts++
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()  // ← PROBLEM: executes at END of function

    select {
    case envelope := <-sm.eventChan:
        // ...
    case <-timeoutCtx.Done():
        // ...
    }
}
```

#### Fix Option A (Simple)
```go
for attempts < maxAttempts {
    attempts++
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)

    select {
    case envelope := <-sm.eventChan:
        cancel()  // Explicit cancel
        // ... rest ...
        return envelope, nil
    case <-timeoutCtx.Done():
        cancel()  // Explicit cancel
        if attempts < maxAttempts {
            delay := sm.calculateBackoff(attempts)
            time.Sleep(delay)
            continue
        }
        return nil, fmt.Errorf("timeout...")
    }
}
```

#### Fix Option B (Elegant - Recommended)
```go
func (sm *ExtensionInstallStateMachine) waitForEventOnce(
    ctx context.Context,
    expectedEventType string,
    timeout time.Duration,
) (*events.Envelope, error) {
    timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
    defer cancel()  // Safe here - function scope

    select {
    case envelope := <-sm.eventChan:
        if envelope.EventType == expectedEventType {
            if !sm.isEventProcessed(envelope.MessageID) {
                sm.markEventProcessed(envelope.MessageID)
                return envelope, nil
            }
        }
        return nil, fmt.Errorf("event mismatch or duplicate")
    case <-timeoutCtx.Done():
        return nil, timeoutCtx.Err()
    }
}

// Then in waitForEvent:
for attempts < maxAttempts {
    attempts++
    envelope, err := sm.waitForEventOnce(ctx, expectedEventType, timeout)
    if err == nil {
        return envelope, nil
    }
    if attempts < maxAttempts {
        delay := sm.calculateBackoff(attempts)
        time.Sleep(delay)
    }
}
return nil, fmt.Errorf("max retries reached")
```

**Recommended:** Option B (cleaner code)

**Tests:** Will be covered by `TestStateMachine_WaitForEvent_*` tests

---

### Issue #2: Race condition in Close()

**File:** `go-services/worker/internal/statemachine/state_machine.go`
**Function:** `Close()`
**Severity:** LOW
**Time to Fix:** 10-15 minutes

#### Current Code Problem
```go
func (sm *ExtensionInstallStateMachine) Close() error {
    sm.mu.Lock()
    defer sm.mu.Unlock()

    if sm.closed {
        return nil
    }

    sm.cancel()
    sm.closed = true

    select {
    case <-sm.eventChan:
    default:
        close(sm.eventChan)  // ← Can panic if listenEvents writes to it
    }

    return nil
}
```

#### Risk Scenario
```
Thread 1 (Close)              Thread 2 (listenEvents)
────────────────────────────────────────────────────
sm.closed = true
sm.cancel()
                              <-ctx.Done() returns
                              sends to sm.eventChan ← PANIC!
close(sm.eventChan)
```

#### Fix Option A (Simple - Recommended)
```go
func (sm *ExtensionInstallStateMachine) Close() error {
    sm.mu.Lock()

    if sm.closed {
        sm.mu.Unlock()
        return nil
    }

    sm.closed = true
    sm.mu.Unlock()  // Release lock before cancellation

    sm.cancel()  // Cancel context (tells goroutines to stop)

    time.Sleep(10 * time.Millisecond)  // Give goroutines time to exit

    sm.mu.Lock()
    defer sm.mu.Unlock()

    // Now safe to close channel
    select {
    case <-sm.eventChan:
    default:
        close(sm.eventChan)
    }

    return nil
}
```

#### Fix Option B (Elegant - Using sync.Once)
```go
type ExtensionInstallStateMachine struct {
    // ... existing fields ...
    closeOnce sync.Once  // ← ADD THIS
}

func (sm *ExtensionInstallStateMachine) Close() error {
    var err error
    sm.closeOnce.Do(func() {
        sm.mu.Lock()
        sm.closed = true
        sm.mu.Unlock()

        sm.cancel()  // Signal goroutines to stop

        // Wait a bit for goroutines to finish
        time.Sleep(10 * time.Millisecond)

        sm.mu.Lock()
        defer sm.mu.Unlock()

        // Close channel
        select {
        case <-sm.eventChan:
        default:
            close(sm.eventChan)
        }
    })
    return err
}
```

**Recommended:** Option B (thread-safe, idempotent)

**Tests:** Will be covered by `TestStateMachine_Close_Concurrent` test

---

### Issue #3: Goroutine leak in listenEvents()

**File:** `go-services/worker/internal/statemachine/state_machine.go`
**Function:** `listenEvents()`
**Severity:** LOW
**Time to Fix:** 20-30 minutes

#### Current Code Problem
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

    sm.subscriber.Subscribe("events:orchestrator:*", handler)
    // ← Subscriber keeps reference to handler

    <-ctx.Done()
    // ← Goroutine exits, but handler still registered in Subscriber
    // ← Subscriber may still call handler on new events
}
```

#### Issue Detail
- listenEvents() goroutine exits when ctx is done
- BUT: Subscriber still has reference to handler
- Subscriber may still try to call handler on new events
- Handler tries to write to closed eventChan → panic or leak

#### Fix: Add Unsubscribe()

**Step 1: Update Interfaces**

In `interfaces.go`:
```go
type EventSubscriber interface {
    Subscribe(channel string, handler func(context.Context, *events.Envelope) error) error
    Unsubscribe(channel string) error  // ← ADD THIS
    Close() error
}
```

**Step 2: Update Mocks**

In `mocks_test.go`:
```go
type MockSubscriber struct {
    mu       sync.Mutex
    Handlers map[string]func(context.Context, *events.Envelope) error
    Closed   bool
}

// ADD THIS:
func (m *MockSubscriber) Unsubscribe(channel string) error {
    m.mu.Lock()
    defer m.mu.Unlock()

    delete(m.Handlers, channel)
    return nil
}
```

**Step 3: Update listenEvents()**

In `state_machine.go`:
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

    channel := "events:orchestrator:*"
    sm.subscriber.Subscribe(channel, handler)

    <-ctx.Done()

    // ← ADD THIS: Explicitly unsubscribe
    sm.subscriber.Unsubscribe(channel)
}
```

**Recommended:** This approach

**Tests:** Will be covered by `TestStateMachine_ListenEvents_Cleanup` test

---

## Implementation Priority

### MUST DO (Week 2.1)
- [x] Issue #2 - Race condition (add sync.Once)
- [ ] Test concurrent Close()

### SHOULD DO (Week 2.2)
- [ ] Issue #1 - defer cancel() (refactor waitForEvent)
- [ ] Issue #3 - Goroutine leak (add Unsubscribe)

### Nice To Have (Week 3)
- [ ] Memory profiling to confirm fixes
- [ ] Stress tests with 100+ workflows

---

## Testing Your Fixes

### After Issue #1 Fix
```bash
cd go-services/worker
go test -v ./internal/statemachine/... -run TestStateMachine_WaitForEvent
```

### After Issue #2 Fix
```bash
cd go-services/worker
go test -race ./internal/statemachine/...
```

### After Issue #3 Fix
```bash
cd go-services/worker
# Check for goroutine leaks with proper cleanup
go test -v ./internal/statemachine/... -run TestStateMachine_ListenEvents
```

### All Tests Together
```bash
cd go-services/worker
go test -v -cover ./internal/statemachine/...
# Should still be fast (<1s) and all pass
```

---

## Verification Checklist

- [ ] Issue #1 fixed (defer cancel)
  - [ ] Code compiles
  - [ ] Tests pass
  - [ ] No syntax errors

- [ ] Issue #2 fixed (race condition)
  - [ ] Code compiles
  - [ ] Tests pass
  - [ ] `go test -race` passes (no race detected)

- [ ] Issue #3 fixed (goroutine leak)
  - [ ] EventSubscriber interface updated
  - [ ] Mocks updated
  - [ ] listenEvents() updated
  - [ ] Code compiles
  - [ ] Tests pass

- [ ] Coverage unchanged
  - [ ] Run `go test ./internal/statemachine/... -cover`
  - [ ] Should still be ~34%

- [ ] Execution time unchanged
  - [ ] Should still be <1 second

---

## Questions?

### For Code Review:
- See files: state_machine.go, events.go, interfaces.go, mocks_test.go
- See test file: state_machine_unit_test.go
- See bug details: STATEMACHINE_BUG_REPORT.md

### For Implementation Help:
- Look at existing code patterns in the file
- Use sync package for thread safety
- Follow existing error handling patterns

---

**Prepared by:** Senior QA Engineer
**Date:** 2025-11-12
**Status:** Ready for developer implementation
