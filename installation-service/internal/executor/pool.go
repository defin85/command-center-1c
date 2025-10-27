package executor

import (
	"context"
	"sync"
	"time"

	"github.com/rs/zerolog/log"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/onec"
)

// ProgressPublisher interface for publishing progress events
type ProgressPublisher interface {
	PublishTaskStarted(ctx context.Context, task Task) error
	PublishTaskCompleted(ctx context.Context, result TaskResult) error
	PublishTaskFailed(ctx context.Context, result TaskResult) error
}

// Pool manages a pool of workers for parallel task execution
type Pool struct {
	config     *config.ExecutorConfig
	onecCfg    *config.OneCConfig
	installer  *onec.Installer
	publisher  ProgressPublisher
	taskChan   chan Task
	resultChan chan TaskResult
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
}

// NewPool creates a new worker pool
func NewPool(execCfg *config.ExecutorConfig, onecCfg *config.OneCConfig, pub ProgressPublisher) *Pool {
	ctx, cancel := context.WithCancel(context.Background())

	return &Pool{
		config:     execCfg,
		onecCfg:    onecCfg,
		installer:  onec.NewInstaller(onecCfg),
		publisher:  pub,
		taskChan:   make(chan Task, execCfg.MaxParallel*2),
		resultChan: make(chan TaskResult, execCfg.MaxParallel*2),
		ctx:        ctx,
		cancel:     cancel,
	}
}

// Start initializes and starts all workers in the pool
func (p *Pool) Start() {
	log.Info().Int("workers", p.config.MaxParallel).Msg("Starting worker pool")

	for i := 0; i < p.config.MaxParallel; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}
}

// worker is the main worker goroutine
func (p *Pool) worker(id int) {
	defer p.wg.Done()

	// Panic recovery to prevent worker death
	defer func() {
		if r := recover(); r != nil {
			log.Error().
				Int("worker_id", id).
				Interface("panic", r).
				Msg("Worker panicked, recovering")
		}
	}()

	log.Info().Int("worker_id", id).Msg("Worker started")

	for {
		select {
		case <-p.ctx.Done():
			log.Info().Int("worker_id", id).Msg("Worker stopping")
			return
		case task := <-p.taskChan:
			log.Info().
				Int("worker_id", id).
				Str("task_id", task.TaskID).
				Int("database_id", task.DatabaseID).
				Str("database_name", task.DatabaseName).
				Msg("Processing task")

			result := p.executeTask(task)

			select {
			case p.resultChan <- result:
			case <-p.ctx.Done():
				return
			}
		}
	}
}

// executeTask executes a single installation task
func (p *Pool) executeTask(task Task) TaskResult {
	// Publish task_started event
	if err := p.publisher.PublishTaskStarted(p.ctx, task); err != nil {
		log.Error().Err(err).Msg("Failed to publish task started event")
	}

	startTime := time.Now()

	// Convert task to InstallRequest
	req := onec.InstallRequest{
		TaskID:           task.TaskID,
		DatabaseID:       task.DatabaseID,
		DatabaseName:     task.DatabaseName,
		ConnectionString: task.ConnectionString,
		Username:         task.Username,
		Password:         task.Password,
		ExtensionPath:    task.ExtensionPath,
		ExtensionName:    task.ExtensionName,
	}

	// Real installation via 1cv8.exe with retry mechanism
	err := p.installer.InstallExtensionWithRetry(
		p.ctx,
		req,
		p.config.RetryAttempts,
		time.Duration(p.config.RetryDelay)*time.Second,
	)

	duration := int(time.Since(startTime).Seconds())

	result := TaskResult{
		TaskID:          task.TaskID,
		DatabaseID:      task.DatabaseID,
		DatabaseName:    task.DatabaseName,
		DurationSeconds: duration,
	}

	if err != nil {
		result.Status = "failed"
		result.ErrorMessage = err.Error()

		log.Error().
			Err(err).
			Str("task_id", task.TaskID).
			Int("database_id", task.DatabaseID).
			Str("database_name", task.DatabaseName).
			Msg("Task failed")

		// Publish task_failed event
		if err := p.publisher.PublishTaskFailed(p.ctx, result); err != nil {
			log.Error().Err(err).Msg("Failed to publish task failed event")
		}
	} else {
		result.Status = "success"
		result.ErrorMessage = ""

		// Publish task_completed event
		if err := p.publisher.PublishTaskCompleted(p.ctx, result); err != nil {
			log.Error().Err(err).Msg("Failed to publish task completed event")
		}
	}

	return result
}

// TaskChannel returns the channel for submitting tasks
func (p *Pool) TaskChannel() chan<- Task {
	return p.taskChan
}

// ResultChannel returns the channel for receiving results
func (p *Pool) ResultChannel() <-chan TaskResult {
	return p.resultChan
}

// Stop gracefully stops the worker pool
func (p *Pool) Stop() {
	log.Info().Msg("Stopping worker pool")
	p.cancel()
	p.wg.Wait()
	close(p.taskChan)
	close(p.resultChan)
}
