# Reference Implementation для исправления subprocess bugs

## Проблема
Integration tests зависают на 600 секунд из-за deadlock в subprocess handling.

## Root Cause
`bytes.Buffer` + `cmd.Run()` на Windows вызывает deadlock когда subprocess пишет много данных в stdout/stderr.

## Решение: Async Stdout/Stderr Reading

### 1. Исправление ExtensionDeleter

**Файл:** `internal/service/extension_deleter.go`

```go
package service

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"time"

	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionDeleter handles deletion of 1C extensions
type ExtensionDeleter struct {
	exe1cv8Path string
	timeout     time.Duration
	semaphore   chan struct{} // Limit concurrent subprocess
}

// NewExtensionDeleter creates a new ExtensionDeleter
func NewExtensionDeleter(exe1cv8Path string, timeout time.Duration) *ExtensionDeleter {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &ExtensionDeleter{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
		semaphore:   make(chan struct{}, 10), // Max 10 concurrent 1cv8.exe processes
	}
}

// DeleteRequest contains parameters for extension deletion
type DeleteRequest struct {
	Server        string
	InfobaseName  string
	Username      string
	Password      string
	ExtensionName string
}

// DeleteExtension deletes an extension from a 1C infobase
func (d *ExtensionDeleter) DeleteExtension(ctx context.Context, req DeleteRequest) error {
	// Acquire semaphore to limit concurrent subprocess
	select {
	case d.semaphore <- struct{}{}:
		defer func() { <-d.semaphore }()
	case <-ctx.Done():
		return ctx.Err()
	}

	ctx, cancel := context.WithTimeout(ctx, d.timeout)
	defer cancel()

	// Build command: 1cv8.exe DESIGNER /F server\infobase /N user /P pass /DeleteCfg -Extension name
	cmd := exec.CommandContext(ctx,
		d.exe1cv8Path,
		"DESIGNER",
		"/F", fmt.Sprintf("%s\\%s", req.Server, req.InfobaseName),
		"/N", req.Username,
		"/P", req.Password,
		"/DeleteCfg",
		"-Extension", req.ExtensionName,
	)

	// CRITICAL FIX: Use pipes for async reading to avoid deadlock
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	// Start the subprocess
	if err := cmd.Start(); err != nil {
		return v8errors.ParseV8Error("", "", err)
	}

	// Ensure subprocess is killed on cleanup
	defer func() {
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
	}()

	// Read stdout and stderr asynchronously
	var stdoutBuf, stderrBuf bytes.Buffer
	var wg sync.WaitGroup

	wg.Add(2)

	// Read stdout in goroutine
	go func() {
		defer wg.Done()
		io.Copy(&stdoutBuf, stdoutPipe)
	}()

	// Read stderr in goroutine
	go func() {
		defer wg.Done()
		io.Copy(&stderrBuf, stderrPipe)
	}()

	// Wait for subprocess to complete
	errChan := make(chan error, 1)
	go func() {
		errChan <- cmd.Wait()
	}()

	// Handle completion or context cancellation
	var cmdErr error
	select {
	case cmdErr = <-errChan:
		// Process completed normally
	case <-ctx.Done():
		// Context cancelled - kill subprocess
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		<-errChan // Wait for Wait() to return
		wg.Wait() // Wait for readers to complete
		return fmt.Errorf("operation cancelled: %w", ctx.Err())
	}

	// Wait for stdout/stderr readers to complete
	wg.Wait()

	if cmdErr != nil {
		// Parse V8 error from stdout/stderr
		return v8errors.ParseV8Error(stdoutBuf.String(), stderrBuf.String(), cmdErr)
	}

	return nil
}
```

### 2. Исправление ExtensionLister

**Файл:** `internal/service/extension_lister.go`

```go
package service

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"github.com/command-center-1c/batch-service/pkg/v8errors"
)

// ExtensionLister handles listing of 1C extensions
type ExtensionLister struct {
	exe1cv8Path string
	timeout     time.Duration
	semaphore   chan struct{} // Limit concurrent subprocess
}

// NewExtensionLister creates a new ExtensionLister
func NewExtensionLister(exe1cv8Path string, timeout time.Duration) *ExtensionLister {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if timeout == 0 {
		timeout = 5 * time.Minute
	}

	return &ExtensionLister{
		exe1cv8Path: exe1cv8Path,
		timeout:     timeout,
		semaphore:   make(chan struct{}, 10),
	}
}

// ListRequest contains parameters for listing extensions
type ListRequest struct {
	Server       string
	InfobaseName string
	Username     string
	Password     string
}

// ExtensionInfo represents information about an extension
type ExtensionInfo struct {
	Name    string `json:"name"`
	Version string `json:"version,omitempty"`
}

// ListExtensions returns a list of extensions installed in the infobase
func (l *ExtensionLister) ListExtensions(ctx context.Context, req ListRequest) ([]ExtensionInfo, error) {
	// Acquire semaphore
	select {
	case l.semaphore <- struct{}{}:
		defer func() { <-l.semaphore }()
	case <-ctx.Done():
		return nil, ctx.Err()
	}

	ctx, cancel := context.WithTimeout(ctx, l.timeout)
	defer cancel()

	// Create temporary file for report
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("extensions_report_%d.txt", time.Now().UnixNano()))

	// Ensure cleanup even on panic
	defer func() {
		if err := os.Remove(tmpFile); err != nil && !os.IsNotExist(err) {
			log.Printf("WARNING: Failed to cleanup temp file %s: %v", tmpFile, err)
		}
	}()

	// Build command
	cmd := exec.CommandContext(ctx,
		l.exe1cv8Path,
		"DESIGNER",
		"/F", fmt.Sprintf("%s\\%s", req.Server, req.InfobaseName),
		"/N", req.Username,
		"/P", req.Password,
		"/ConfigurationRepositoryReport", tmpFile,
	)

	// CRITICAL FIX: Use pipes for async reading
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stdout pipe: %w", err)
	}

	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	// Start subprocess
	if err := cmd.Start(); err != nil {
		return nil, v8errors.ParseV8Error("", "", err)
	}

	// Ensure subprocess cleanup
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
	errChan := make(chan error, 1)
	go func() {
		errChan <- cmd.Wait()
	}()

	var cmdErr error
	select {
	case cmdErr = <-errChan:
		// Completed
	case <-ctx.Done():
		// Cancelled
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		<-errChan
		wg.Wait()
		return nil, fmt.Errorf("operation cancelled: %w", ctx.Err())
	}

	// Wait for readers
	wg.Wait()

	if cmdErr != nil {
		return nil, v8errors.ParseV8Error(stdoutBuf.String(), stderrBuf.String(), cmdErr)
	}

	// Read report file
	content, err := os.ReadFile(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read report file: %w", err)
	}

	// Parse extensions from report
	extensions := parseExtensionsFromReport(string(content))

	return extensions, nil
}

// parseExtensionsFromReport parses the ConfigurationRepositoryReport output
func parseExtensionsFromReport(content string) []ExtensionInfo {
	// WARNING: This is a stub implementation
	log.Println("WARNING: ListExtensions uses stub implementation")
	log.Println("ConfigurationRepositoryReport format needs empirical testing")
	log.Printf("Report content length: %d bytes", len(content))

	return []ExtensionInfo{}
}
```

### 3. Добавление Input Validation

**Файл:** `internal/service/validation.go` (НОВЫЙ)

```go
package service

import (
	"errors"
	"fmt"
	"strings"
)

// ValidateExtensionName validates extension name for security
func ValidateExtensionName(name string) error {
	if len(name) == 0 {
		return errors.New("extension name cannot be empty")
	}

	if len(name) > 255 {
		return errors.New("extension name too long (max 255 characters)")
	}

	// Check for dangerous characters that could lead to command injection
	dangerousChars := []string{";", "|", "&", "$", "`", "\n", "\r", "\t", "\"", "'"}
	for _, char := range dangerousChars {
		if strings.Contains(name, char) {
			return fmt.Errorf("extension name contains invalid character: %s", char)
		}
	}

	return nil
}

// ValidateInfobaseName validates infobase name
func ValidateInfobaseName(name string) error {
	if len(name) == 0 {
		return errors.New("infobase name cannot be empty")
	}

	if len(name) > 255 {
		return errors.New("infobase name too long (max 255 characters)")
	}

	return nil
}

// ValidateServerAddress validates server address
func ValidateServerAddress(addr string) error {
	if len(addr) == 0 {
		return errors.New("server address cannot be empty")
	}

	// Basic validation - more sophisticated checks can be added
	if len(addr) > 255 {
		return errors.New("server address too long")
	}

	return nil
}
```

### 4. Обновление DeleteExtension для использования валидации

```go
// В extension_deleter.go, в начале DeleteExtension():
func (d *ExtensionDeleter) DeleteExtension(ctx context.Context, req DeleteRequest) error {
	// Validate inputs
	if err := ValidateExtensionName(req.ExtensionName); err != nil {
		return fmt.Errorf("invalid extension name: %w", err)
	}

	if err := ValidateInfobaseName(req.InfobaseName); err != nil {
		return fmt.Errorf("invalid infobase name: %w", err)
	}

	if err := ValidateServerAddress(req.Server); err != nil {
		return fmt.Errorf("invalid server address: %w", err)
	}

	// ... rest of existing code
}
```

### 5. ~~Django Client с Retry~~ (REMOVED)

> **NOTE:** This component was removed in favor of event-driven architecture.
> HTTP callbacks are no longer used. Instead, batch-service publishes events to Redis Streams:
> - `events:batch-service:extension:install-started`
> - `events:batch-service:extension:installed`
> - `events:batch-service:extension:install-failed`
>
> Django EventSubscriber (`apps/operations/event_subscriber.py`) handles these events.

## Тестирование исправлений

### Запуск integration tests после исправлений:

```bash
cd go-services/batch-service
go test -v -timeout 30s ./tests/integration/
```

**Ожидаемый результат:**
- Все tests должны завершиться за < 10 секунд
- НЕ должно быть timeout
- Tests должны правильно обрабатывать ошибки "1cv8.exe not found"

### Проверка unit tests:

```bash
go test -v ./internal/service/
go test -v ./pkg/v8errors/
```

**Все должно пройти успешно.**

## Дополнительные улучшения

### Добавить Prometheus metrics (опционально)

**Файл:** `internal/service/metrics.go` (НОВЫЙ)

```go
package service

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	SubprocessTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "batch_service_subprocess_total",
			Help: "Total subprocess calls",
		},
		[]string{"operation", "status"},
	)

	SubprocessDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "batch_service_subprocess_duration_seconds",
			Help:    "Subprocess execution time in seconds",
			Buckets: prometheus.ExponentialBuckets(0.1, 2, 10), // 0.1s to ~100s
		},
		[]string{"operation"},
	)

	SubprocessConcurrent = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "batch_service_subprocess_concurrent",
			Help: "Number of concurrent subprocess",
		},
	)
)
```

**Использование в DeleteExtension:**

```go
func (d *ExtensionDeleter) DeleteExtension(ctx context.Context, req DeleteRequest) error {
	start := time.Now()
	SubprocessConcurrent.Inc()

	defer func() {
		SubprocessConcurrent.Dec()
		SubprocessDuration.WithLabelValues("delete_extension").Observe(time.Since(start).Seconds())
	}()

	// ... existing code

	if err != nil {
		SubprocessTotal.WithLabelValues("delete_extension", "failure").Inc()
		return err
	}

	SubprocessTotal.WithLabelValues("delete_extension", "success").Inc()
	return nil
}
```

## Checklist перед merge

- [ ] Исправлен subprocess deadlock (StdoutPipe/StderrPipe)
- [ ] Добавлен context cancellation handling
- [ ] Добавлен zombie process cleanup
- [ ] Добавлен semaphore для concurrency control
- [ ] Добавлена input validation (ValidateExtensionName)
- [ ] Добавлен retry mechanism для Django callback
- [ ] Улучшен temporary file cleanup
- [ ] Integration tests проходят успешно
- [ ] Unit tests проходят успешно
- [ ] Нет memory leaks (проверить с race detector)
- [ ] Code review пройден

## Команды для финальной проверки

```bash
# Run all tests with race detector
go test -race -v ./...

# Check for memory leaks
go test -v -memprofile=mem.out ./internal/service/
go tool pprof mem.out

# Run integration tests
go test -v -timeout 30s ./tests/integration/

# Build to verify compilation
go build -o bin/cc1c-batch-service.exe ./cmd/main.go
```

---

**Автор:** Claude Code (Code Reviewer)
**Дата:** 2025-11-08
**Версия:** 1.0
