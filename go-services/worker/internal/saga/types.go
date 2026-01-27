// Package saga provides Saga pattern implementation with compensation for distributed transactions.
// It manages long-running workflows across multiple services with rollback capability.
package saga

import (
	"context"
	"errors"
	"time"
)

// SagaStatus represents the current status of a saga execution.
type SagaStatus string

const (
	// SagaStatusPending indicates the saga is created but not started.
	SagaStatusPending SagaStatus = "pending"
	// SagaStatusRunning indicates the saga is currently executing.
	SagaStatusRunning SagaStatus = "running"
	// SagaStatusCompleted indicates the saga finished successfully.
	SagaStatusCompleted SagaStatus = "completed"
	// SagaStatusFailed indicates the saga failed with an error.
	SagaStatusFailed SagaStatus = "failed"
	// SagaStatusCompensating indicates the saga is rolling back.
	SagaStatusCompensating SagaStatus = "compensating"
	// SagaStatusCompensated indicates the saga completed compensation.
	SagaStatusCompensated SagaStatus = "compensated"
	// SagaStatusPartiallyCompensated indicates compensation completed with some failures.
	SagaStatusPartiallyCompensated SagaStatus = "partially_compensated"
)

// IsFinal returns true if the status is a terminal state.
func (s SagaStatus) IsFinal() bool {
	return s == SagaStatusCompleted ||
		s == SagaStatusFailed ||
		s == SagaStatusCompensated ||
		s == SagaStatusPartiallyCompensated
}

// String returns the string representation.
func (s SagaStatus) String() string {
	return string(s)
}

// Errors returned by saga operations.
var (
	// ErrSagaNotFound indicates the saga definition was not found.
	ErrSagaNotFound = errors.New("saga not found")

	// ErrSagaAlreadyRegistered indicates the saga is already registered.
	ErrSagaAlreadyRegistered = errors.New("saga already registered")

	// ErrExecutionNotFound indicates the execution was not found.
	ErrExecutionNotFound = errors.New("execution not found")

	// ErrExecutionAlreadyRunning indicates the execution is already in progress.
	ErrExecutionAlreadyRunning = errors.New("execution already running")

	// ErrExecutionCompleted indicates the execution is in a final state.
	ErrExecutionCompleted = errors.New("execution already completed")

	// ErrStepTimeout indicates a step execution timed out.
	ErrStepTimeout = errors.New("step execution timeout")

	// ErrCompensationFailed indicates compensation failed for one or more steps.
	ErrCompensationFailed = errors.New("compensation failed")

	// ErrInvalidSagaDefinition indicates the saga definition is invalid.
	ErrInvalidSagaDefinition = errors.New("invalid saga definition")

	// ErrContextCancelled indicates the context was cancelled.
	ErrContextCancelled = errors.New("context cancelled")
)

// StepFunc is the function signature for step execution and compensation.
type StepFunc func(ctx context.Context, sagaCtx *SagaContext) error

// RetryPolicy configures retry behavior for steps.
type RetryPolicy struct {
	// MaxRetries is the maximum number of retry attempts.
	MaxRetries int `json:"max_retries"`

	// InitialBackoff is the initial backoff duration.
	InitialBackoff time.Duration `json:"initial_backoff"`

	// MaxBackoff is the maximum backoff duration.
	MaxBackoff time.Duration `json:"max_backoff"`

	// BackoffFactor is the multiplier for exponential backoff.
	BackoffFactor float64 `json:"backoff_factor"`

	// RetryableErrors are error types that should be retried (nil = all errors).
	RetryableErrors []error `json:"-"`
}

// DefaultRetryPolicy returns sensible retry defaults.
func DefaultRetryPolicy() *RetryPolicy {
	return &RetryPolicy{
		MaxRetries:     3,
		InitialBackoff: 100 * time.Millisecond,
		MaxBackoff:     5 * time.Second,
		BackoffFactor:  2.0,
	}
}

// DefaultCompensationRetryPolicy returns retry policy for compensation (more aggressive).
func DefaultCompensationRetryPolicy() *RetryPolicy {
	return &RetryPolicy{
		MaxRetries:     5,
		InitialBackoff: 200 * time.Millisecond,
		MaxBackoff:     10 * time.Second,
		BackoffFactor:  2.0,
	}
}

// CalculateBackoff calculates the backoff duration for a given attempt.
func (p *RetryPolicy) CalculateBackoff(attempt int) time.Duration {
	if attempt <= 0 {
		return p.InitialBackoff
	}

	backoff := p.InitialBackoff
	for i := 0; i < attempt; i++ {
		backoff = time.Duration(float64(backoff) * p.BackoffFactor)
		if backoff > p.MaxBackoff {
			return p.MaxBackoff
		}
	}
	return backoff
}

// Step represents a single step in a saga.
type Step struct {
	// ID is the unique identifier for this step.
	ID string

	// Name is a human-readable name for the step.
	Name string

	// Execute is the main function to execute.
	Execute StepFunc

	// Compensate is the rollback function (optional).
	// If nil, the step is considered non-compensatable.
	Compensate StepFunc

	// Timeout is the maximum duration for step execution.
	// Zero means use saga default or no timeout.
	Timeout time.Duration

	// RetryPolicy configures retry behavior (nil = no retry).
	RetryPolicy *RetryPolicy

	// CompensationRetryPolicy configures retry for compensation (nil = use default).
	CompensationRetryPolicy *RetryPolicy

	// Idempotent indicates the step can be safely re-executed.
	Idempotent bool
}

// Validate checks if the step definition is valid.
func (s *Step) Validate() error {
	if s.ID == "" {
		return errors.New("step ID is required")
	}
	if s.Execute == nil {
		return errors.New("step Execute function is required")
	}
	return nil
}

// HasCompensation returns true if the step has a compensation handler.
func (s *Step) HasCompensation() bool {
	return s.Compensate != nil
}

// SagaDefinition defines a saga with its steps.
type SagaDefinition struct {
	// ID is the unique identifier for this saga.
	ID string

	// Name is a human-readable name.
	Name string

	// Description describes the saga's purpose.
	Description string

	// Steps are the ordered steps to execute.
	Steps []*Step

	// DefaultTimeout is the default timeout for steps without explicit timeout.
	DefaultTimeout time.Duration

	// OnComplete is called when the saga completes successfully (optional).
	OnComplete func(ctx context.Context, sagaCtx *SagaContext) error

	// OnFailed is called when the saga fails (optional).
	OnFailed func(ctx context.Context, sagaCtx *SagaContext, err error) error

	// OnCompensated is called after compensation completes (optional).
	OnCompensated func(ctx context.Context, sagaCtx *SagaContext, results []CompensationResult) error
}

// Validate checks if the saga definition is valid.
func (d *SagaDefinition) Validate() error {
	if d.ID == "" {
		return errors.New("saga ID is required")
	}
	if len(d.Steps) == 0 {
		return errors.New("saga must have at least one step")
	}

	stepIDs := make(map[string]bool)
	for i, step := range d.Steps {
		if err := step.Validate(); err != nil {
			return errors.New("step " + step.ID + ": " + err.Error())
		}
		if stepIDs[step.ID] {
			return errors.New("duplicate step ID: " + step.ID)
		}
		stepIDs[step.ID] = true

		// Set default timeout if not specified
		if step.Timeout == 0 && d.DefaultTimeout > 0 {
			d.Steps[i].Timeout = d.DefaultTimeout
		}
	}

	return nil
}

// GetStep returns a step by ID.
func (d *SagaDefinition) GetStep(stepID string) *Step {
	for _, step := range d.Steps {
		if step.ID == stepID {
			return step
		}
	}
	return nil
}
