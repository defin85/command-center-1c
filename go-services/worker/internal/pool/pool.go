package pool

import (
	"context"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
	"github.com/commandcenter1c/commandcenter/worker/internal/queue"
)

// WorkerPool manages a pool of workers
type WorkerPool struct {
	size       int
	queue      *queue.RedisQueue
	processor  *processor.TaskProcessor
	wg         sync.WaitGroup
	stopChan   chan struct{}
	config     *config.Config
}

// NewWorkerPool creates a new worker pool
func NewWorkerPool(size int, queueClient *queue.RedisQueue, cfg *config.Config) *WorkerPool {
	return &WorkerPool{
		size:      size,
		queue:     queueClient,
		processor: processor.NewTaskProcessor(cfg),
		stopChan:  make(chan struct{}),
		config:    cfg,
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
			// Try to dequeue a task (with timeout)
			task, err := p.queue.DequeueTask(ctx, 5*time.Second)
			if err != nil {
				log.Errorf("Failed to dequeue task: %v", err)
				time.Sleep(1 * time.Second)
				continue
			}

			if task == nil {
				// No task available, continue waiting
				continue
			}

			log.Infof("Processing task: %s", task.ID)
			p.processTask(ctx, task)
		}
	}
}

// processTask processes a single task
func (p *WorkerPool) processTask(ctx context.Context, task *models.Operation) {
	log := logger.WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_type": task.Type,
	})

	start := time.Now()

	// Update task status to processing
	if err := p.queue.UpdateTaskStatus(ctx, task.ID, models.OperationStatusProcessing); err != nil {
		log.Errorf("Failed to update task status: %v", err)
	}

	// Process the task
	result := p.processor.Process(ctx, task)
	result.Duration = time.Since(start)

	// Publish result
	if err := p.queue.PublishResult(ctx, result); err != nil {
		log.Errorf("Failed to publish result: %v", err)
	}

	// Update task status
	status := models.OperationStatusCompleted
	if !result.Success {
		status = models.OperationStatusFailed
	}

	if err := p.queue.UpdateTaskStatus(ctx, task.ID, status); err != nil {
		log.Errorf("Failed to update final task status: %v", err)
	}

	log.Infof("Task completed in %v (success: %v)", result.Duration, result.Success)
}
