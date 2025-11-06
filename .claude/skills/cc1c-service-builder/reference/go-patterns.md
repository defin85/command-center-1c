# Go Service Patterns

## API Handler Pattern

```go
package handlers

import (
    "net/http"
    "github.com/gin-gonic/gin"
    "command-center/go-services/shared/logger"
)

type YourHandler struct {
    log logger.Logger
    service YourService
}

func NewYourHandler(log logger.Logger, service YourService) *YourHandler {
    return &YourHandler{
        log: log,
        service: service,
    }
}

func (h *YourHandler) HandleListItems(c *gin.Context) {
    items, err := h.service.ListItems(c.Request.Context())
    if err != nil {
        h.log.Error("Failed to list items", "error", err)
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, gin.H{"data": items})
}
```

## Worker Processor Pattern

```go
package processor

import (
    "context"
    "sync"
)

type Processor struct {
    maxConcurrent int
    log logger.Logger
}

func NewProcessor(maxConcurrent int, log logger.Logger) *Processor {
    return &Processor{
        maxConcurrent: maxConcurrent,
        log: log,
    }
}

func (p *Processor) Process(ctx context.Context, tasks []Task) error {
    sem := make(chan struct{}, p.maxConcurrent)
    var wg sync.WaitGroup
    errChan := make(chan error, len(tasks))

    for _, task := range tasks {
        wg.Add(1)
        go func(t Task) {
            defer wg.Done()
            sem <- struct{}{}        // acquire
            defer func() { <-sem }() // release

            if err := p.processTask(ctx, t); err != nil {
                errChan <- err
            }
        }(task)
    }

    wg.Wait()
    close(errChan)

    // Collect errors
    for err := range errChan {
        if err != nil {
            return err // Return first error
        }
    }

    return nil
}

func (p *Processor) processTask(ctx context.Context, task Task) error {
    p.log.Info("Processing task", "id", task.ID)
    // Process task
    return nil
}
```

## Shared Library Pattern

```go
// go-services/shared/yourpackage/interface.go
package yourpackage

type YourInterface interface {
    DoSomething(ctx context.Context, input Input) (Output, error)
}

// go-services/shared/yourpackage/implementation.go
package yourpackage

type implementation struct {
    config Config
}

func New(config Config) YourInterface {
    return &implementation{config: config}
}

func (i *implementation) DoSomething(ctx context.Context, input Input) (Output, error) {
    // Implementation
    return Output{}, nil
}
```
