// Package saga provides Saga pattern implementation with compensation for distributed transactions.
// It manages long-running workflows across multiple services with rollback capability.
package saga

import (
	"context"
	"encoding/json"
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

// SagaContext holds execution context and data passed between steps.
type SagaContext struct {
	// SagaID is the saga definition ID.
	SagaID string `json:"saga_id"`

	// ExecutionID is the unique execution instance ID.
	ExecutionID string `json:"execution_id"`

	// CorrelationID is used for distributed tracing.
	CorrelationID string `json:"correlation_id"`

	// DatabaseIDs are the 1C database IDs involved in this saga.
	DatabaseIDs []string `json:"database_ids,omitempty"`

	// Variables holds data passed between steps.
	Variables map[string]interface{} `json:"variables"`

	// CurrentStep is the index of the currently executing step.
	CurrentStep int `json:"current_step"`

	// CurrentStepID is the ID of the currently executing step.
	CurrentStepID string `json:"current_step_id"`

	// Status is the current saga status.
	Status SagaStatus `json:"status"`

	// Error holds the error that caused failure (if any).
	Error error `json:"-"`

	// ErrorMessage is the serializable error message.
	ErrorMessage string `json:"error_message,omitempty"`
}

// NewSagaContext creates a new saga context.
func NewSagaContext(sagaID, executionID, correlationID string) *SagaContext {
	return &SagaContext{
		SagaID:        sagaID,
		ExecutionID:   executionID,
		CorrelationID: correlationID,
		Variables:     make(map[string]interface{}),
		Status:        SagaStatusPending,
	}
}

// Set stores a value in the context variables.
func (c *SagaContext) Set(key string, value interface{}) {
	if c.Variables == nil {
		c.Variables = make(map[string]interface{})
	}
	c.Variables[key] = value
}

// Get retrieves a value from the context variables.
func (c *SagaContext) Get(key string) (interface{}, bool) {
	if c.Variables == nil {
		return nil, false
	}
	val, ok := c.Variables[key]
	return val, ok
}

// GetString retrieves a string value from the context variables.
func (c *SagaContext) GetString(key string) string {
	val, ok := c.Get(key)
	if !ok {
		return ""
	}
	str, ok := val.(string)
	if !ok {
		return ""
	}
	return str
}

// GetBool retrieves a boolean value from the context variables.
func (c *SagaContext) GetBool(key string) bool {
	val, ok := c.Get(key)
	if !ok {
		return false
	}
	b, ok := val.(bool)
	return ok && b
}

// GetStringSlice retrieves a string slice from the context variables.
func (c *SagaContext) GetStringSlice(key string) []string {
	val, ok := c.Get(key)
	if !ok {
		return nil
	}
	switch v := val.(type) {
	case []string:
		return v
	case []interface{}:
		result := make([]string, 0, len(v))
		for _, item := range v {
			if str, ok := item.(string); ok {
				result = append(result, str)
			}
		}
		return result
	}
	return nil
}

// SetError sets the error and error message.
func (c *SagaContext) SetError(err error) {
	c.Error = err
	if err != nil {
		c.ErrorMessage = err.Error()
	} else {
		c.ErrorMessage = ""
	}
}

// Clone creates a copy of the context for safe concurrent use.
func (c *SagaContext) Clone() *SagaContext {
	clone := &SagaContext{
		SagaID:        c.SagaID,
		ExecutionID:   c.ExecutionID,
		CorrelationID: c.CorrelationID,
		CurrentStep:   c.CurrentStep,
		CurrentStepID: c.CurrentStepID,
		Status:        c.Status,
		Error:         c.Error,
		ErrorMessage:  c.ErrorMessage,
	}

	if c.DatabaseIDs != nil {
		clone.DatabaseIDs = make([]string, len(c.DatabaseIDs))
		copy(clone.DatabaseIDs, c.DatabaseIDs)
	}

	if c.Variables != nil {
		// Deep copy через JSON для безопасности от race conditions
		data, err := json.Marshal(c.Variables)
		if err == nil {
			json.Unmarshal(data, &clone.Variables)
		} else {
			// Fallback to shallow copy
			clone.Variables = make(map[string]interface{})
			for k, v := range c.Variables {
				clone.Variables[k] = v
			}
		}
	}

	return clone
}

// SagaState represents the persistent state of a saga execution.
type SagaState struct {
	// ExecutionID is the unique execution instance ID.
	ExecutionID string `json:"execution_id"`

	// SagaID is the saga definition ID.
	SagaID string `json:"saga_id"`

	// CorrelationID is used for distributed tracing.
	CorrelationID string `json:"correlation_id"`

	// Status is the current status.
	Status SagaStatus `json:"status"`

	// CurrentStep is the index of the current step.
	CurrentStep int `json:"current_step"`

	// CurrentStepID is the ID of the current step.
	CurrentStepID string `json:"current_step_id,omitempty"`

	// CompletedSteps are step IDs that completed successfully.
	CompletedSteps []string `json:"completed_steps"`

	// CompensationStack is step IDs for rollback (LIFO order).
	CompensationStack []string `json:"compensation_stack"`

	// Variables holds context data.
	Variables map[string]interface{} `json:"variables"`

	// Error is the error message if failed.
	Error string `json:"error,omitempty"`

	// StartedAt is when execution started.
	StartedAt time.Time `json:"started_at"`

	// UpdatedAt is last update time.
	UpdatedAt time.Time `json:"updated_at"`

	// CompletedAt is when execution completed (nil if running).
	CompletedAt *time.Time `json:"completed_at,omitempty"`

	// Locks are database IDs with active locks.
	Locks []string `json:"locks,omitempty"`

	// StepResults holds results for each completed step.
	StepResults map[string]*StepResult `json:"step_results,omitempty"`

	// CompensationResults holds compensation results.
	CompensationResults []CompensationResult `json:"compensation_results,omitempty"`
}

// NewSagaState creates a new saga state.
func NewSagaState(executionID, sagaID, correlationID string) *SagaState {
	now := time.Now()
	return &SagaState{
		ExecutionID:       executionID,
		SagaID:            sagaID,
		CorrelationID:     correlationID,
		Status:            SagaStatusPending,
		CurrentStep:       0,
		CompletedSteps:    make([]string, 0),
		CompensationStack: make([]string, 0),
		Variables:         make(map[string]interface{}),
		StartedAt:         now,
		UpdatedAt:         now,
		StepResults:       make(map[string]*StepResult),
	}
}

// ToContext converts state to saga context.
func (s *SagaState) ToContext() *SagaContext {
	ctx := &SagaContext{
		SagaID:        s.SagaID,
		ExecutionID:   s.ExecutionID,
		CorrelationID: s.CorrelationID,
		CurrentStep:   s.CurrentStep,
		Status:        s.Status,
		ErrorMessage:  s.Error,
	}

	if s.Variables != nil {
		ctx.Variables = make(map[string]interface{})
		for k, v := range s.Variables {
			ctx.Variables[k] = v
		}
	}

	if s.Locks != nil {
		ctx.DatabaseIDs = make([]string, len(s.Locks))
		copy(ctx.DatabaseIDs, s.Locks)
	}

	if s.Error != "" {
		ctx.Error = errors.New(s.Error)
	}

	return ctx
}

// UpdateFromContext updates state from saga context.
func (s *SagaState) UpdateFromContext(ctx *SagaContext) {
	s.CurrentStep = ctx.CurrentStep
	s.CurrentStepID = ctx.CurrentStepID
	s.Status = ctx.Status
	s.UpdatedAt = time.Now()

	if ctx.Error != nil {
		s.Error = ctx.Error.Error()
	}

	if ctx.Variables != nil {
		if s.Variables == nil {
			s.Variables = make(map[string]interface{})
		}
		for k, v := range ctx.Variables {
			s.Variables[k] = v
		}
	}

	if ctx.DatabaseIDs != nil {
		s.Locks = make([]string, len(ctx.DatabaseIDs))
		copy(s.Locks, ctx.DatabaseIDs)
	}
}

// AddCompletedStep adds a step to completed and compensation stack.
func (s *SagaState) AddCompletedStep(stepID string, hasCompensation bool) {
	s.CompletedSteps = append(s.CompletedSteps, stepID)
	if hasCompensation {
		s.CompensationStack = append(s.CompensationStack, stepID)
	}
	s.UpdatedAt = time.Now()
}

// PopCompensationStep removes and returns the next step to compensate.
func (s *SagaState) PopCompensationStep() (string, bool) {
	if len(s.CompensationStack) == 0 {
		return "", false
	}
	last := len(s.CompensationStack) - 1
	stepID := s.CompensationStack[last]
	s.CompensationStack = s.CompensationStack[:last]
	s.UpdatedAt = time.Now()
	return stepID, true
}

// SetCompleted marks the saga as completed.
func (s *SagaState) SetCompleted() {
	now := time.Now()
	s.Status = SagaStatusCompleted
	s.CompletedAt = &now
	s.UpdatedAt = now
}

// SetFailed marks the saga as failed.
func (s *SagaState) SetFailed(err error) {
	now := time.Now()
	s.Status = SagaStatusFailed
	s.CompletedAt = &now
	s.UpdatedAt = now
	if err != nil {
		s.Error = err.Error()
	}
}

// SetCompensating marks the saga as compensating.
func (s *SagaState) SetCompensating() {
	s.Status = SagaStatusCompensating
	s.UpdatedAt = time.Now()
}

// SetCompensated marks the saga as compensated.
func (s *SagaState) SetCompensated(results []CompensationResult) {
	now := time.Now()
	s.CompensationResults = results
	s.CompletedAt = &now
	s.UpdatedAt = now

	// Check if all compensations succeeded
	allSuccess := true
	for _, r := range results {
		if !r.Success {
			allSuccess = false
			break
		}
	}

	if allSuccess {
		s.Status = SagaStatusCompensated
	} else {
		s.Status = SagaStatusPartiallyCompensated
	}
}

// ToJSON serializes the state to JSON.
func (s *SagaState) ToJSON() ([]byte, error) {
	return json.Marshal(s)
}

// SagaStateFromJSON deserializes state from JSON.
func SagaStateFromJSON(data []byte) (*SagaState, error) {
	var state SagaState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, err
	}
	if state.CompletedSteps == nil {
		state.CompletedSteps = make([]string, 0)
	}
	if state.CompensationStack == nil {
		state.CompensationStack = make([]string, 0)
	}
	if state.Variables == nil {
		state.Variables = make(map[string]interface{})
	}
	if state.StepResults == nil {
		state.StepResults = make(map[string]*StepResult)
	}
	return &state, nil
}

// StepResult holds the result of a step execution.
type StepResult struct {
	// StepID is the step identifier.
	StepID string `json:"step_id"`

	// Success indicates if the step completed successfully.
	Success bool `json:"success"`

	// Error is the error message if failed.
	Error string `json:"error,omitempty"`

	// Duration is how long the step took.
	Duration time.Duration `json:"duration"`

	// Retries is the number of retry attempts.
	Retries int `json:"retries"`

	// StartedAt is when the step started.
	StartedAt time.Time `json:"started_at"`

	// CompletedAt is when the step completed.
	CompletedAt time.Time `json:"completed_at"`

	// Output holds step output data (optional).
	Output map[string]interface{} `json:"output,omitempty"`
}

// CompensationResult holds the result of a compensation execution.
type CompensationResult struct {
	// StepID is the step identifier.
	StepID string `json:"step_id"`

	// Success indicates if compensation completed successfully.
	Success bool `json:"success"`

	// Error is the error message if failed.
	Error string `json:"error,omitempty"`

	// Duration is how long compensation took.
	Duration time.Duration `json:"duration"`

	// Retries is the number of retry attempts.
	Retries int `json:"retries"`
}

// SagaResult is the result of saga execution.
type SagaResult struct {
	// ExecutionID is the unique execution instance ID.
	ExecutionID string `json:"execution_id"`

	// SagaID is the saga definition ID.
	SagaID string `json:"saga_id"`

	// Status is the final status.
	Status SagaStatus `json:"status"`

	// Output holds the saga output data.
	Output map[string]interface{} `json:"output,omitempty"`

	// Error is the error that caused failure (if any).
	Error error `json:"-"`

	// ErrorMessage is the serializable error message.
	ErrorMessage string `json:"error_message,omitempty"`

	// Duration is total execution time.
	Duration time.Duration `json:"duration"`

	// CompletedSteps are the steps that completed successfully.
	CompletedSteps []string `json:"completed_steps"`

	// CompensationResults are results of compensation steps.
	CompensationResults []CompensationResult `json:"compensation_results,omitempty"`
}

// SagaOrchestrator defines the interface for saga execution.
type SagaOrchestrator interface {
	// RegisterSaga registers a saga definition.
	RegisterSaga(def *SagaDefinition) error

	// GetSaga returns a registered saga definition.
	GetSaga(sagaID string) (*SagaDefinition, error)

	// Execute starts a new saga execution.
	Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*SagaResult, error)

	// ExecuteWithCorrelation starts a saga with a specific correlation ID.
	ExecuteWithCorrelation(ctx context.Context, sagaID string, input map[string]interface{}, correlationID string) (*SagaResult, error)

	// Resume continues a paused or failed saga execution.
	Resume(ctx context.Context, executionID string) (*SagaResult, error)

	// GetStatus returns the current status of a saga execution.
	GetStatus(ctx context.Context, executionID string) (*SagaState, error)

	// Cancel cancels a running saga execution.
	Cancel(ctx context.Context, executionID string) error

	// Close releases resources.
	Close() error
}

// SagaStore defines the interface for saga state persistence.
type SagaStore interface {
	// SaveState saves or updates saga state.
	SaveState(ctx context.Context, state *SagaState) error

	// LoadState loads saga state by execution ID.
	LoadState(ctx context.Context, executionID string) (*SagaState, error)

	// DeleteState removes saga state.
	DeleteState(ctx context.Context, executionID string) error

	// ListByStatus lists saga executions by status.
	ListByStatus(ctx context.Context, status SagaStatus, limit int) ([]*SagaState, error)

	// AcquireLock acquires an execution lock.
	AcquireLock(ctx context.Context, executionID string, ttl time.Duration) (bool, error)

	// ReleaseLock releases an execution lock.
	ReleaseLock(ctx context.Context, executionID string) error

	// Close releases resources.
	Close() error
}

// SagaEventType defines event types for saga lifecycle.
type SagaEventType string

const (
	// SagaEventStarted is emitted when a saga starts.
	SagaEventStarted SagaEventType = "saga.started"
	// SagaEventStepStarted is emitted when a step starts.
	SagaEventStepStarted SagaEventType = "saga.step.started"
	// SagaEventStepCompleted is emitted when a step completes.
	SagaEventStepCompleted SagaEventType = "saga.step.completed"
	// SagaEventStepFailed is emitted when a step fails.
	SagaEventStepFailed SagaEventType = "saga.step.failed"
	// SagaEventCompleted is emitted when a saga completes successfully.
	SagaEventCompleted SagaEventType = "saga.completed"
	// SagaEventFailed is emitted when a saga fails.
	SagaEventFailed SagaEventType = "saga.failed"
	// SagaEventCompensating is emitted when compensation starts.
	SagaEventCompensating SagaEventType = "saga.compensating"
	// SagaEventCompensated is emitted when compensation completes.
	SagaEventCompensated SagaEventType = "saga.compensated"
	// SagaEventCancelled is emitted when a saga is cancelled.
	SagaEventCancelled SagaEventType = "saga.cancelled"
)

// SagaEvent represents a saga lifecycle event.
type SagaEvent struct {
	// Type is the event type.
	Type SagaEventType `json:"type"`

	// ExecutionID is the saga execution ID.
	ExecutionID string `json:"execution_id"`

	// SagaID is the saga definition ID.
	SagaID string `json:"saga_id"`

	// CorrelationID is the correlation ID.
	CorrelationID string `json:"correlation_id"`

	// StepID is the step ID (for step events).
	StepID string `json:"step_id,omitempty"`

	// Timestamp is when the event occurred.
	Timestamp time.Time `json:"timestamp"`

	// Error is the error message (for failure events).
	Error string `json:"error,omitempty"`

	// Duration is the duration (for completion events).
	Duration time.Duration `json:"duration,omitempty"`

	// Metadata holds additional event data.
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// NewSagaEvent creates a new saga event.
func NewSagaEvent(eventType SagaEventType, executionID, sagaID, correlationID string) *SagaEvent {
	return &SagaEvent{
		Type:          eventType,
		ExecutionID:   executionID,
		SagaID:        sagaID,
		CorrelationID: correlationID,
		Timestamp:     time.Now(),
		Metadata:      make(map[string]interface{}),
	}
}
