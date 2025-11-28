package statemachine

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"time"
)

// CompensationConfig defines retry behavior for compensation actions
type CompensationConfig struct {
	MaxRetries    int           // Default: 3
	InitialDelay  time.Duration // Default: 2s
	MaxDelay      time.Duration // Default: 30s
	JitterRange   time.Duration // Default: 300ms
	BackoffFactor float64       // Default: 2.0
}

// DefaultCompensationConfig returns default compensation configuration
func DefaultCompensationConfig() *CompensationConfig {
	return &CompensationConfig{
		MaxRetries:    3,
		InitialDelay:  2 * time.Second,
		MaxDelay:      30 * time.Second,
		JitterRange:   300 * time.Millisecond,
		BackoffFactor: 2.0,
	}
}

// CompensationResult represents the result of a compensation action execution
type CompensationResult struct {
	Name          string        `json:"name"`
	Success       bool          `json:"success"`
	Attempts      int           `json:"attempts"`
	TotalDuration time.Duration `json:"total_duration"`
	Error         string        `json:"error,omitempty"`
	ExecutedAt    time.Time     `json:"executed_at"`
}

// AuditLogger interface for logging compensation actions to audit log
type AuditLogger interface {
	LogCompensation(ctx context.Context, operationID string, result *CompensationResult) error
}

// MetricsRecorder interface for recording compensation metrics
type MetricsRecorder interface {
	RecordCompensation(name string, success bool, duration time.Duration, attempts int)
}

// CompensationExecutor executes compensation actions with retry logic
type CompensationExecutor struct {
	config      *CompensationConfig
	auditLogger AuditLogger
	metrics     MetricsRecorder
	rng         *rand.Rand
	rngMu       sync.Mutex // Mutex for thread-safe random number generation
}

// NewCompensationExecutor creates a new CompensationExecutor
func NewCompensationExecutor(config *CompensationConfig, auditLogger AuditLogger, metrics MetricsRecorder) *CompensationExecutor {
	if config == nil {
		config = DefaultCompensationConfig()
	}

	return &CompensationExecutor{
		config:      config,
		auditLogger: auditLogger,
		metrics:     metrics,
		rng:         rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// ExecuteWithRetry executes a compensation action with exponential backoff retry
func (e *CompensationExecutor) ExecuteWithRetry(ctx context.Context, operationID string, comp CompensationAction) *CompensationResult {
	startTime := time.Now()
	result := &CompensationResult{
		Name:       comp.Name,
		ExecutedAt: startTime,
	}

	var lastErr error
	delay := e.config.InitialDelay

	for attempt := 1; attempt <= e.config.MaxRetries; attempt++ {
		result.Attempts = attempt

		fmt.Printf("[CompensationExecutor] Executing compensation '%s' (attempt %d/%d, operation_id=%s)\n",
			comp.Name, attempt, e.config.MaxRetries, operationID)

		// Check context before execution
		if ctx.Err() != nil {
			fmt.Printf("[CompensationExecutor] Context cancelled before attempt %d for '%s'\n",
				attempt, comp.Name)
			result.Success = false
			result.Error = fmt.Sprintf("context cancelled: %v", ctx.Err())
			result.TotalDuration = time.Since(startTime)
			e.recordAndLog(ctx, operationID, result)
			return result
		}

		// Execute compensation action
		attemptStart := time.Now()
		err := comp.Action(ctx)
		attemptDuration := time.Since(attemptStart)

		if err == nil {
			fmt.Printf("[CompensationExecutor] Compensation '%s' succeeded on attempt %d (duration=%v)\n",
				comp.Name, attempt, attemptDuration)
			result.Success = true
			result.TotalDuration = time.Since(startTime)
			e.recordAndLog(ctx, operationID, result)
			return result
		}

		lastErr = err
		fmt.Printf("[CompensationExecutor] Compensation '%s' failed on attempt %d: %v (duration=%v)\n",
			comp.Name, attempt, err, attemptDuration)

		// Don't wait after the last attempt
		if attempt < e.config.MaxRetries {
			// Calculate delay with jitter
			jitter := e.calculateJitter()
			waitDelay := delay + jitter

			fmt.Printf("[CompensationExecutor] Waiting %v before retry (base=%v, jitter=%v)\n",
				waitDelay, delay, jitter)

			// Wait with context cancellation support
			select {
			case <-ctx.Done():
				fmt.Printf("[CompensationExecutor] Context cancelled while waiting for retry\n")
				result.Success = false
				result.Error = fmt.Sprintf("context cancelled during retry wait: %v (last error: %v)", ctx.Err(), lastErr)
				result.TotalDuration = time.Since(startTime)
				e.recordAndLog(ctx, operationID, result)
				return result
			case <-time.After(waitDelay):
				// Continue to next attempt
			}

			// Calculate next delay with exponential backoff
			delay = e.calculateNextDelay(delay)
		}
	}

	// All retries exhausted
	fmt.Printf("[CompensationExecutor] Compensation '%s' failed after %d attempts (total_duration=%v)\n",
		comp.Name, e.config.MaxRetries, time.Since(startTime))

	result.Success = false
	if lastErr != nil {
		result.Error = lastErr.Error()
	}
	result.TotalDuration = time.Since(startTime)
	e.recordAndLog(ctx, operationID, result)

	return result
}

// calculateJitter returns a random jitter value within the configured range
// Thread-safe: uses mutex for random number generation
func (e *CompensationExecutor) calculateJitter() time.Duration {
	if e.config.JitterRange <= 0 {
		return 0
	}
	// Random value in range [-JitterRange/2, +JitterRange/2]
	halfRange := int64(e.config.JitterRange / 2)

	e.rngMu.Lock()
	jitter := e.rng.Int63n(int64(e.config.JitterRange)) - halfRange
	e.rngMu.Unlock()

	return time.Duration(jitter)
}

// calculateNextDelay calculates the next delay using exponential backoff
func (e *CompensationExecutor) calculateNextDelay(currentDelay time.Duration) time.Duration {
	nextDelay := time.Duration(float64(currentDelay) * e.config.BackoffFactor)
	if nextDelay > e.config.MaxDelay {
		nextDelay = e.config.MaxDelay
	}
	return nextDelay
}

// recordAndLog records metrics and logs to audit
func (e *CompensationExecutor) recordAndLog(ctx context.Context, operationID string, result *CompensationResult) {
	// Record metrics if available
	if e.metrics != nil {
		e.metrics.RecordCompensation(result.Name, result.Success, result.TotalDuration, result.Attempts)
	}

	// Log to audit if available
	if e.auditLogger != nil {
		if err := e.auditLogger.LogCompensation(ctx, operationID, result); err != nil {
			fmt.Printf("[CompensationExecutor] Failed to log compensation to audit: %v\n", err)
		}
	}
}

// CompensationSummary aggregates results of multiple compensation actions
type CompensationSummary struct {
	OperationID    string               `json:"operation_id"`
	TotalActions   int                  `json:"total_actions"`
	SuccessCount   int                  `json:"success_count"`
	FailedCount    int                  `json:"failed_count"`
	TotalDuration  time.Duration        `json:"total_duration"`
	Results        []*CompensationResult `json:"results"`
	CompletedAt    time.Time            `json:"completed_at"`
}

// AllSucceeded returns true if all compensation actions succeeded
func (s *CompensationSummary) AllSucceeded() bool {
	return s.FailedCount == 0
}

// NewCompensationSummary creates a new CompensationSummary from results
func NewCompensationSummary(operationID string, results []*CompensationResult) *CompensationSummary {
	summary := &CompensationSummary{
		OperationID:  operationID,
		TotalActions: len(results),
		Results:      results,
		CompletedAt:  time.Now(),
	}

	var totalDuration time.Duration
	for _, r := range results {
		if r.Success {
			summary.SuccessCount++
		} else {
			summary.FailedCount++
		}
		totalDuration += r.TotalDuration
	}
	summary.TotalDuration = totalDuration

	return summary
}
