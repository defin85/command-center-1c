# Объяснение Subprocess Deadlock Problem

## Визуализация проблемы

### ❌ ТЕКУЩАЯ РЕАЛИЗАЦИЯ (DEADLOCK)

```
┌─────────────────────────────────────────────────────────────┐
│                     Go Process                              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  var stdout, stderr bytes.Buffer                     │  │
│  │  cmd.Stdout = &stdout  ←── Buffered (no limit)      │  │
│  │  cmd.Stderr = &stderr  ←── Buffered (no limit)      │  │
│  │                                                       │  │
│  │  cmd.Run() ←─────────┐                              │  │
│  │         ▲            │                              │  │
│  │         │            │ Waiting for subprocess       │  │
│  │         │            │ to exit...                   │  │
│  │         │            └──────────────────────────────┼──┤
│  │         │ Blocked                                   │  │
│  │         │ reading                                   │  │
│  │         │ pipe                                      │  │
│  └─────────┼───────────────────────────────────────────┘  │
│            │                                               │
│            │ OS Pipe (limited buffer: 4KB-64KB)           │
│            │                                               │
│         ┌──┴──┐                                            │
│         │PIPE │ ◄─── FULL! (64KB written, no readers)     │
│         └──▲──┘                                            │
│            │                                               │
│            │ Trying to write more...                       │
│            │ BLOCKED!                                      │
└────────────┼───────────────────────────────────────────────┘
             │
             │
┌────────────┼───────────────────────────────────────────────┐
│            │         1cv8.exe Process                      │
│            │                                               │
│         ┌──┴──────────────────────────────────────────┐   │
│         │  Writing to stdout/stderr...                │   │
│         │                                             │   │
│         │  Wrote 64KB... pipe full!                   │   │
│         │                                             │   │
│         │  ⏳ Waiting for pipe to drain...           │   │
│         │     (BLOCKED - pipe buffer full)           │   │
│         │                                             │   │
│         │  Cannot exit until write completes!        │   │
│         └─────────────────────────────────────────────┘   │
│                                                            │
└────────────────────────────────────────────────────────────┘

                    ⚠️  DEADLOCK! ⚠️

Go process waits for 1cv8.exe to exit
    ↓
1cv8.exe waits for pipe to drain
    ↓
Pipe cannot drain because nobody is reading
    ↓
TIMEOUT after 600 seconds!
```

---

### ✅ ИСПРАВЛЕННАЯ РЕАЛИЗАЦИЯ (NO DEADLOCK)

```
┌─────────────────────────────────────────────────────────────┐
│                     Go Process                              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  stdoutPipe, _ := cmd.StdoutPipe()                   │  │
│  │  stderrPipe, _ := cmd.StderrPipe()                   │  │
│  │                                                       │  │
│  │  cmd.Start() ←─── Non-blocking start                │  │
│  │                                                       │  │
│  │  ┌─────────────┐    ┌─────────────┐                │  │
│  │  │ Goroutine 1 │    │ Goroutine 2 │                │  │
│  │  │             │    │             │                │  │
│  │  │ io.Copy()   │    │ io.Copy()   │                │  │
│  │  │ ↓           │    │ ↓           │                │  │
│  │  │ Reading     │    │ Reading     │                │  │
│  │  │ stdout      │    │ stderr      │                │  │
│  │  └─────┬───────┘    └─────┬───────┘                │  │
│  │        │                  │                         │  │
│  │        │ Active           │ Active                  │  │
│  │        │ readers!         │ readers!                │  │
│  └────────┼──────────────────┼─────────────────────────┘  │
│           │                  │                            │
│           │ OS Pipe         │ OS Pipe                    │
│           │ (draining)      │ (draining)                 │
│        ┌──▼──┐           ┌──▼──┐                         │
│        │PIPE │           │PIPE │                         │
│        │     │◄──────────│     │◄──── Data flows!        │
│        └──▲──┘           └──▲──┘                         │
│           │                 │                            │
└───────────┼─────────────────┼────────────────────────────┘
            │                 │
            │ Writing         │ Writing
            │ (non-blocking)  │ (non-blocking)
┌───────────┼─────────────────┼────────────────────────────┐
│           │  1cv8.exe       │                            │
│        ┌──┴─────────────────┴──────────────────────┐    │
│        │  Writing to stdout/stderr...              │    │
│        │                                            │    │
│        │  ✓ Writes freely (pipe drains)            │    │
│        │  ✓ Completes work                         │    │
│        │  ✓ Exits normally                         │    │
│        └────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘

                 ✅ NO DEADLOCK! ✅

Goroutines actively read from pipes
    ↓
Pipes drain as 1cv8.exe writes
    ↓
1cv8.exe completes and exits
    ↓
cmd.Wait() returns
    ↓
SUCCESS in < 5 seconds!
```

---

## Почему это происходит?

### 1. OS Pipe Buffer Limitation

**Windows pipe buffer:** Обычно 4KB - 64KB (зависит от версии Windows)

**Проблема:**
- 1cv8.exe может писать МНОГО данных (error messages, debug info, etc.)
- Если вывод > 64KB → pipe заполняется
- Write блокируется до тех пор пока кто-то не прочитает из pipe

### 2. cmd.Run() Behavior

```go
// Go stdlib implementation (упрощенно):
func (c *Cmd) Run() error {
    if err := c.Start(); err != nil {
        return err
    }
    return c.Wait()  // Blocks until process exits
}
```

**Проблема:**
- `Run()` НЕ читает stdout/stderr во время выполнения
- Он только ждет завершения процесса
- Если процесс блокирован на write → `Run()` висит навсегда

### 3. bytes.Buffer не помогает

```go
var stdout bytes.Buffer
cmd.Stdout = &stdout  // Это НЕ читает из pipe!
```

**Ошибочное понимание:**
- Многие думают что `bytes.Buffer` автоматически читает из pipe
- НА САМОМ ДЕЛЕ: Buffer только сохраняет данные ПОСЛЕ того как они прочитаны
- Чтение происходит ТОЛЬКО когда процесс завершается

**Правильно понимать:**
```
Процесс пишет → OS pipe → (КУЛАЖОК) → bytes.Buffer
                           ↑
                   Здесь блокировка!
                   Pipe полон, никто не читает
```

---

## Почему StdoutPipe решает проблему?

### Асинхронное чтение

```go
stdoutPipe, _ := cmd.StdoutPipe()
cmd.Start()

go func() {
    io.Copy(&buffer, stdoutPipe)  // ← Читает ПОСТОЯННО
}()
```

**Что происходит:**
1. Goroutine создается СРАЗУ
2. `io.Copy` ПОСТОЯННО читает из pipe
3. Pipe освобождается → процесс может писать
4. НЕТ блокировки!

### Пример потока данных

```
Time: 0ms
  1cv8.exe: Writes 1KB → Pipe (63KB free)
  Goroutine: Reads 1KB → Buffer (Pipe: 64KB free)

Time: 10ms
  1cv8.exe: Writes 50KB → Pipe (14KB free)
  Goroutine: Reads 30KB → Buffer (Pipe: 44KB free)

Time: 20ms
  1cv8.exe: Writes 100KB → Pipe fills to 64KB, blocks temporarily
  Goroutine: Reads 60KB → Buffer (Pipe: 4KB used → unblocks write)

Time: 100ms
  1cv8.exe: Finished writing, exits
  Goroutine: Reads remaining data, completes

TOTAL TIME: ~100ms (not 600 seconds!)
```

---

## Реальный пример из stacktrace

### Застрявший goroutine

```
goroutine 10 [syscall]:
syscall.ReadFile(...)
internal/poll.(*FD).Read.func1
```

**Что это значит:**
- Goroutine застрял в syscall (Windows ReadFile)
- Он пытается прочитать из pipe
- Pipe пуст потому что subprocess заблокирован
- Subprocess заблокирован потому что его pipe полон
- **DEADLOCK CYCLE**

### Застрявший main thread

```
goroutine 9 [syscall]:
syscall.WaitForSingleObject(0x1f0, 0xffffffff)
os.(*Process).wait(0xc000226800)
os/exec.(*Cmd).Wait(0xc0000da480)
os/exec.(*Cmd).Run(0xc0000da480)
```

**Что это значит:**
- Main thread ждет завершения subprocess
- `WaitForSingleObject` с `0xffffffff` (INFINITE timeout)
- Subprocess не может завершиться (pipe блокирован)
- **ЗАВИСАНИЕ**

---

## Частые заблуждения

### ❌ Миф 1: "bytes.Buffer безлимитный, deadlock невозможен"

**Реальность:**
- bytes.Buffer безлимитный, НО
- OS pipe buffer ограничен (4-64KB)
- Блокировка происходит в pipe, не в Buffer

### ❌ Миф 2: "Context timeout решит проблему"

```go
ctx, cancel := context.WithTimeout(ctx, 5*time.Minute)
cmd := exec.CommandContext(ctx, ...)
```

**Реальность:**
- Context timeout убьет процесс через 5 минут
- НО процесс уже заблокирован, не может быть убит
- Timeout НЕ помогает при deadlock

### ❌ Миф 3: "Это проблема только на Windows"

**Реальность:**
- На Linux/Mac pipe buffer больше (обычно 64KB)
- НО проблема ВСЁ РАВНО существует
- Просто нужно больше данных чтобы проявилась

---

## Правильное решение: Checklist

✅ **1. Используй StdoutPipe/StderrPipe**
```go
stdoutPipe, _ := cmd.StdoutPipe()
stderrPipe, _ := cmd.StderrPipe()
```

✅ **2. Start вместо Run**
```go
cmd.Start()  // Non-blocking start
```

✅ **3. Читай асинхронно в goroutines**
```go
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
```

✅ **4. Wait после Start**
```go
err := cmd.Wait()
wg.Wait()  // Wait for readers too!
```

✅ **5. Cleanup на всякий случай**
```go
defer func() {
    if cmd.Process != nil {
        cmd.Process.Kill()
    }
}()
```

---

## Дополнительные ресурсы

**Go stdlib docs:**
- https://pkg.go.dev/os/exec#Cmd.StdoutPipe
- https://pkg.go.dev/os/exec#Cmd.StderrPipe

**Известные issues:**
- https://github.com/golang/go/issues/9382
- https://github.com/golang/go/issues/18695

**Best practices:**
- ВСЕГДА используй StdoutPipe/StderrPipe для subprocess с большим выводом
- НЕ используй cmd.Run() с cmd.Stdout = &buffer
- ВСЕГДА читай pipes асинхронно

---

**Автор:** Claude Code
**Дата:** 2025-11-08
**См. также:** `REVIEW_FIXES_REFERENCE.md` для готового кода
