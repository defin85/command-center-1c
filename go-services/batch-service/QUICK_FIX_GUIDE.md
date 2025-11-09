# Quick Fix Guide - Subprocess Deadlock

> 5-минутный гайд для быстрого исправления critical bug

## Проблема

Integration tests зависают на 600 секунд. Root cause: subprocess deadlock.

## Быстрое решение (copy-paste ready)

### 1. Замени extension_deleter.go

**Найди строки 60-68:**
```go
// СТАРЫЙ КОД (УДАЛИТЬ)
var stdout, stderr bytes.Buffer
cmd.Stdout = &stdout
cmd.Stderr = &stderr

err := cmd.Run()
if err != nil {
    return v8errors.ParseV8Error(stdout.String(), stderr.String(), err)
}
```

**Замени на:**
```go
// НОВЫЙ КОД (ВСТАВИТЬ)
// Create pipes for async reading
stdoutPipe, err := cmd.StdoutPipe()
if err != nil {
    return fmt.Errorf("failed to create stdout pipe: %w", err)
}

stderrPipe, err := cmd.StderrPipe()
if err != nil {
    return fmt.Errorf("failed to create stderr pipe: %w", err)
}

// Start subprocess
if err := cmd.Start(); err != nil {
    return v8errors.ParseV8Error("", "", err)
}

// Ensure cleanup
defer func() {
    if cmd.Process != nil {
        cmd.Process.Kill()
    }
}()

// Read stdout/stderr asynchronously
var stdoutBuf, stderrBuf bytes.Buffer
var wg sync.WaitGroup

wg.Add(2)

go func() {
    defer wg.Done()
    io.Copy(&stdoutBuf, stdoutPipe)
}()

go func() {
    defer wg.Done()
    io.Copy(&stderrBuf, stderrPipe)
}()

// Wait for subprocess
err = cmd.Wait()

// Wait for readers
wg.Wait()

if err != nil {
    return v8errors.ParseV8Error(stdoutBuf.String(), stderrBuf.String(), err)
}
```

**Добавь imports:**
```go
import (
    // ... existing imports
    "io"
    "sync"
)
```

---

### 2. Замени extension_lister.go

**Найди строки 73-80:**
```go
// СТАРЫЙ КОД (УДАЛИТЬ)
var stdout, stderr bytes.Buffer
cmd.Stdout = &stdout
cmd.Stderr = &stderr

err := cmd.Run()
if err != nil {
    return nil, v8errors.ParseV8Error(stdout.String(), stderr.String(), err)
}
```

**Замени на тот же код что и выше** (аналогично extension_deleter.go)

---

### 3. Добавь semaphore для rate limiting

**В extension_deleter.go:**

**Найди struct:**
```go
type ExtensionDeleter struct {
    exe1cv8Path string
    timeout     time.Duration
}
```

**Замени на:**
```go
type ExtensionDeleter struct {
    exe1cv8Path string
    timeout     time.Duration
    semaphore   chan struct{} // Limit concurrent subprocess
}
```

**Найди NewExtensionDeleter:**
```go
return &ExtensionDeleter{
    exe1cv8Path: exe1cv8Path,
    timeout:     timeout,
}
```

**Замени на:**
```go
return &ExtensionDeleter{
    exe1cv8Path: exe1cv8Path,
    timeout:     timeout,
    semaphore:   make(chan struct{}, 10), // Max 10 concurrent
}
```

**В начало DeleteExtension добавь:**
```go
// Acquire semaphore
select {
case d.semaphore <- struct{}{}:
    defer func() { <-d.semaphore }()
case <-ctx.Done():
    return ctx.Err()
}
```

---

### 4. Тестирование

```bash
# Запусти integration tests
cd go-services/batch-service
go test -v -timeout 30s ./tests/integration/

# Ожидаемый результат:
# ✓ Все tests завершаются за < 10 секунд
# ✓ НЕТ timeout
# ✓ Tests корректно обрабатывают ошибки
```

---

## Если нужно больше деталей

**Читай:**
- `CODE_REVIEW_SUMMARY.md` - краткий отчет
- `REVIEW_FIXES_REFERENCE.md` - полный код всех исправлений
- `DEADLOCK_EXPLANATION.md` - подробное объяснение проблемы

---

## Checklist

- [ ] Заменил код в extension_deleter.go
- [ ] Заменил код в extension_lister.go
- [ ] Добавил semaphore
- [ ] Добавил imports (io, sync)
- [ ] Запустил tests - проходят успешно
- [ ] Время выполнения < 10 секунд
- [ ] Нет timeout

---

**Время на исправление:** ~30 минут
**Сложность:** Средняя (copy-paste + проверка)
