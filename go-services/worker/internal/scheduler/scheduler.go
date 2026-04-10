package scheduler

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/robfig/cron/v3"
	"go.uber.org/zap"
)

// Job represents a scheduled job
type Job interface {
	// Name returns the unique name of the job
	Name() string
	// Execute runs the job
	Execute(ctx context.Context) error
}

// Scheduler manages periodic job execution using cron expressions
type Scheduler struct {
	cron     *cron.Cron
	redis    redis.Cmdable
	config   *SchedulerConfig
	metrics  *SchedulerMetrics
	logger   *zap.Logger
	workerID string

	// Registered jobs
	jobs       map[string]Job
	jobEnabled map[string]bool
	jobsMu     sync.RWMutex

	// Lifecycle management
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup

	// State
	started bool
	mu      sync.Mutex
}

// New creates a new scheduler instance
func New(redis redis.Cmdable, workerID string, logger *zap.Logger) *Scheduler {
	config := LoadConfigFromEnv()
	metrics := GetMetrics()

	// Create cron instance with seconds field support
	cronInstance := cron.New(
		cron.WithParser(cron.NewParser(
			cron.SecondOptional|cron.Minute|cron.Hour|cron.Dom|cron.Month|cron.Dow|cron.Descriptor,
		)),
		cron.WithChain(
			cron.Recover(cron.DefaultLogger), // Recover from panics
		),
	)

	return &Scheduler{
		cron:     cronInstance,
		redis:    redis,
		config:   config,
		metrics:  metrics,
		logger:   logger.With(zap.String("component", "scheduler")),
		workerID: workerID,
		jobs:     make(map[string]Job),
		jobEnabled: make(map[string]bool),
	}
}

// NewWithConfig creates a new scheduler with explicit configuration
func NewWithConfig(redis redis.Cmdable, config *SchedulerConfig, workerID string, logger *zap.Logger) *Scheduler {
	s := New(redis, workerID, logger)
	s.config = config
	return s
}

// RegisterJob registers a job with a cron expression
func (s *Scheduler) RegisterJob(cronExpr string, job Job) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.started {
		return fmt.Errorf("cannot register jobs after scheduler has started")
	}

	// Check for duplicate job names
	s.jobsMu.Lock()
	if _, exists := s.jobs[job.Name()]; exists {
		s.jobsMu.Unlock()
		return fmt.Errorf("job %s already registered", job.Name())
	}
	s.jobs[job.Name()] = job
	s.jobEnabled[job.Name()] = true
	s.jobsMu.Unlock()

	// Create wrapper that handles locking and metrics
	wrapper := s.createJobWrapper(job)

	_, err := s.cron.AddFunc(cronExpr, wrapper)
	if err != nil {
		// Remove from jobs map on failure
		s.jobsMu.Lock()
		delete(s.jobs, job.Name())
		s.jobsMu.Unlock()
		return fmt.Errorf("failed to add job %s with cron %s: %w", job.Name(), cronExpr, err)
	}

	s.logger.Info("registered job",
		zap.String("job", job.Name()),
		zap.String("cron", cronExpr),
	)

	return nil
}

// createJobWrapper creates a wrapper function for a job that handles:
// - Feature flag check
// - Distributed locking
// - Metrics recording
// - Error handling
func (s *Scheduler) createJobWrapper(job Job) func() {
	return func() {
		jobName := job.Name()

		// Check if scheduler is enabled (feature flag)
		if !s.IsEnabled() {
			s.logger.Debug("scheduler disabled, skipping job",
				zap.String("job", jobName),
			)
			s.metrics.RecordJobExecution(jobName, JobStatusSkipped, 0)
			return
		}

		if !s.IsJobEnabled(jobName) {
			s.logger.Debug("job disabled by desired state, skipping job",
				zap.String("job", jobName),
			)
			s.metrics.RecordJobExecution(jobName, JobStatusSkipped, 0)
			return
		}

		// Use context with timeout based on lock TTL
		ctx, cancel := context.WithTimeout(s.ctx, s.config.LockTTL)
		defer cancel()

		// Try to acquire distributed lock
		lockStart := time.Now()
		acquired, err := AcquireLockWithRetry(
			ctx,
			s.redis,
			jobName,
			s.workerID,
			s.config.LockTTL,
			s.config.LockMaxRetries,
			s.config.LockRetryDelay,
		)

		if err != nil {
			s.logger.Error("failed to acquire lock",
				zap.String("job", jobName),
				zap.Error(err),
			)
			s.metrics.RecordLockAcquisition(jobName, LockStatusFailed)
			s.metrics.RecordJobExecution(jobName, JobStatusSkipped, 0)
			return
		}

		if !acquired {
			s.logger.Debug("lock not acquired, skipping job (another worker is running it)",
				zap.String("job", jobName),
			)
			s.metrics.RecordLockAcquisition(jobName, LockStatusTimeout)
			s.metrics.RecordJobExecution(jobName, JobStatusSkipped, 0)
			return
		}

		s.metrics.RecordLockAcquisition(jobName, LockStatusAcquired)
		s.logger.Debug("lock acquired",
			zap.String("job", jobName),
		)

		// Execute job with metrics
		s.metrics.RecordJobStart(jobName)
		s.wg.Add(1)

		execStart := time.Now()
		var execErr error

		func() {
			defer func() {
				// Release lock
				lockDuration := time.Since(lockStart).Seconds()
				s.metrics.RecordLockHoldDuration(jobName, lockDuration)

				releaseCtx, releaseCancel := context.WithTimeout(context.Background(), 5*time.Second)
				defer releaseCancel()

				if err := ReleaseLock(releaseCtx, s.redis, jobName, s.workerID); err != nil {
					s.logger.Warn("failed to release lock",
						zap.String("job", jobName),
						zap.Error(err),
					)
				} else {
					s.logger.Debug("lock released",
						zap.String("job", jobName),
					)
				}

				s.metrics.RecordJobEnd(jobName)
				s.wg.Done()
			}()

			// Execute the job
			execErr = job.Execute(ctx)
		}()

		execDuration := time.Since(execStart).Seconds()

		if execErr != nil {
			s.logger.Error("job execution failed",
				zap.String("job", jobName),
				zap.Duration("duration", time.Since(execStart)),
				zap.Error(execErr),
			)
			s.metrics.RecordJobExecution(jobName, JobStatusFailure, execDuration)
		} else {
			s.logger.Info("job executed successfully",
				zap.String("job", jobName),
				zap.Duration("duration", time.Since(execStart)),
			)
			s.metrics.RecordJobExecution(jobName, JobStatusSuccess, execDuration)
		}

		s.metrics.UpdateLastRunTimestamp(jobName, float64(time.Now().Unix()))
	}
}

// Start starts the scheduler
func (s *Scheduler) Start() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.started {
		return fmt.Errorf("scheduler already started")
	}

	s.ctx, s.cancel = context.WithCancel(context.Background())
	s.cron.Start()
	s.started = true

	// Update enabled metric
	s.metrics.SetSchedulerEnabled(s.config.Enabled)

	s.logger.Info("scheduler started",
		zap.Bool("enabled", s.config.Enabled),
		zap.String("worker_id", s.workerID),
		zap.Int("registered_jobs", len(s.jobs)),
	)

	return nil
}

// Stop gracefully stops the scheduler
func (s *Scheduler) Stop() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.started {
		return nil
	}

	s.logger.Info("stopping scheduler...")

	// Cancel context to signal jobs to stop
	if s.cancel != nil {
		s.cancel()
	}

	// Stop accepting new jobs
	ctx := s.cron.Stop()

	// Wait for running jobs with timeout
	done := make(chan struct{})
	go func() {
		s.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		s.logger.Info("all jobs completed")
	case <-time.After(30 * time.Second):
		s.logger.Warn("timeout waiting for jobs to complete")
	}

	// Wait for cron to stop
	<-ctx.Done()

	s.started = false
	s.metrics.SetSchedulerEnabled(false)

	s.logger.Info("scheduler stopped")

	return nil
}

// IsEnabled returns whether the scheduler is enabled
func (s *Scheduler) IsEnabled() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.config.Enabled
}

// SetEnabled updates scheduler desired enabled state without restarting the process.
func (s *Scheduler) SetEnabled(enabled bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.config.Enabled = enabled
	s.metrics.SetSchedulerEnabled(enabled)
}

// GetConfig returns the current scheduler configuration
func (s *Scheduler) GetConfig() *SchedulerConfig {
	return s.config
}

// GetRegisteredJobs returns the names of all registered jobs
func (s *Scheduler) GetRegisteredJobs() []string {
	s.jobsMu.RLock()
	defer s.jobsMu.RUnlock()

	names := make([]string, 0, len(s.jobs))
	for name := range s.jobs {
		names = append(names, name)
	}
	return names
}

// SetJobEnabled updates desired state for a registered job.
func (s *Scheduler) SetJobEnabled(jobName string, enabled bool) error {
	s.jobsMu.Lock()
	defer s.jobsMu.Unlock()

	if _, exists := s.jobs[jobName]; !exists {
		return fmt.Errorf("job %s not found", jobName)
	}
	s.jobEnabled[jobName] = enabled
	return nil
}

// IsJobEnabled reports whether a registered job should execute.
func (s *Scheduler) IsJobEnabled(jobName string) bool {
	s.jobsMu.RLock()
	defer s.jobsMu.RUnlock()

	enabled, exists := s.jobEnabled[jobName]
	if !exists {
		return true
	}
	return enabled
}

// RunJobNow triggers immediate execution of a job (for testing/debugging)
func (s *Scheduler) RunJobNow(jobName string) error {
	s.jobsMu.RLock()
	job, exists := s.jobs[jobName]
	s.jobsMu.RUnlock()

	if !exists {
		return fmt.Errorf("job %s not found", jobName)
	}

	// Execute directly without cron scheduling
	wrapper := s.createJobWrapper(job)
	go wrapper()

	return nil
}
