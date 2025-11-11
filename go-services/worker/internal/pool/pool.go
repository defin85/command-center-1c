package pool

import (
	"context"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
)

// WorkerPool manages a pool of workers
type WorkerPool struct {
	size        int
	queue       *queue.RedisQueue
	processor   *processor.TaskProcessor
	credsClient credentials.Fetcher
	wg          sync.WaitGroup
	stopChan    chan struct{}
	config      *config.Config
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(size int, queueClient *queue.RedisQueue, credsClient credentials.Fetcher, cfg *config.Config) *WorkerPool {
	return &WorkerPool{
		size:        size,
		queue:       queueClient,
		processor:   processor.NewTaskProcessor(cfg, credsClient),
		credsClient: credsClient,
		stopChan:    make(chan struct{}),
		config:      cfg,
	}
}

// Start starts all workers in the pool
func (p *WorkerPool) Start(ctx context.Context) {
	for i := 0; i < p.size; i++ {
		p.wg.Add(1)
		go p.worker(ctx, i)
	}
}

// Stop stops all workers gracefully
func (p *WorkerPool) Stop() {
	close(p.stopChan)
	p.wg.Wait()
}

// worker is the main worker goroutine
func (p *WorkerPool) worker(ctx context.Context, id int) {
	defer p.wg.Done()

	log := logger.WithFields(map[string]interface{}{
		"worker_id": id,
	})

	log.Info("Worker started")

	for {
		select {
		case <-p.stopChan:
			log.Info("Worker stopping")
			return
		case <-ctx.Done():
			log.Info("Worker context cancelled")
			return
		default:
			// Note: Task dequeuing is now handled by consumer.go
			// This pool is for future parallel processing if needed
			// For now, we just sleep to avoid busy-waiting
			time.Sleep(1 * time.Second)
		}
	}
}

// processTask processes a single task
func (p *WorkerPool) processTask(ctx context.Context, task *models.OperationMessage) {
	log := logger.WithFields(map[string]interface{}{
		"operation_id":   task.OperationID,
		"operation_type": task.OperationType,
	})

	start := time.Now()

	// Process the operation (v2.0)
	result := p.processor.Process(ctx, task)

	// Calculate total duration
	totalDuration := time.Since(start)
	log.Infof("Operation %s completed in %v, status=%s, succeeded=%d, failed=%d",
		task.OperationID, totalDuration, result.Status, result.Summary.Succeeded, result.Summary.Failed)

	// Note: Publishing to Redis results queue happens in consumer.go
	// This is just local processing
}
