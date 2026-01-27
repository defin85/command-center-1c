package saga

import (
	"context"
	"encoding/json"
	"errors"
	"time"
)

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
		// Deep copy via JSON to avoid race conditions.
		data, err := json.Marshal(c.Variables)
		if err == nil {
			_ = json.Unmarshal(data, &clone.Variables)
		} else {
			// Fallback to shallow copy.
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
}

// PopCompensationStep pops a step from compensation stack.
func (s *SagaState) PopCompensationStep() (string, bool) {
	if len(s.CompensationStack) == 0 {
		return "", false
	}
	last := len(s.CompensationStack) - 1
	stepID := s.CompensationStack[last]
	s.CompensationStack = s.CompensationStack[:last]
	return stepID, true
}

// SetCompleted marks the saga as completed.
func (s *SagaState) SetCompleted() {
	s.Status = SagaStatusCompleted
	now := time.Now()
	s.CompletedAt = &now
	s.UpdatedAt = now
}

// SetFailed marks the saga as failed.
func (s *SagaState) SetFailed(err error) {
	s.Status = SagaStatusFailed
	now := time.Now()
	s.CompletedAt = &now
	s.UpdatedAt = now
	if err != nil {
		s.Error = err.Error()
	}
}

// SetCompensating marks saga as compensating.
func (s *SagaState) SetCompensating() {
	s.Status = SagaStatusCompensating
	s.UpdatedAt = time.Now()
}

// SetCompensated marks saga as compensated with results.
func (s *SagaState) SetCompensated(results []CompensationResult) {
	s.CompensationResults = results
	now := time.Now()
	s.CompletedAt = &now
	s.UpdatedAt = now

	// Determine final compensation status
	allSuccess := true
	anySuccess := false
	for _, r := range results {
		if r.Success {
			anySuccess = true
		} else {
			allSuccess = false
		}
	}

	if allSuccess {
		s.Status = SagaStatusCompensated
	} else if anySuccess {
		s.Status = SagaStatusPartiallyCompensated
	} else {
		s.Status = SagaStatusFailed
	}
}

// ToJSON serializes state to JSON.
func (s *SagaState) ToJSON() ([]byte, error) {
	return json.Marshal(s)
}

// SagaStateFromJSON deserializes state from JSON.
func SagaStateFromJSON(data []byte) (*SagaState, error) {
	var state SagaState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, err
	}
	return &state, nil
}

// StepResult represents the result of a step execution.
type StepResult struct {
	StepID      string        `json:"step_id"`
	Success     bool          `json:"success"`
	Error       string        `json:"error,omitempty"`
	StartedAt   time.Time     `json:"started_at"`
	CompletedAt time.Time     `json:"completed_at"`
	Duration    time.Duration `json:"duration"`
	Retries     int           `json:"retries"`
}

// CompensationResult represents the result of a compensation step.
type CompensationResult struct {
	StepID      string        `json:"step_id"`
	Success     bool          `json:"success"`
	Error       string        `json:"error,omitempty"`
	StartedAt   time.Time     `json:"started_at"`
	CompletedAt time.Time     `json:"completed_at"`
	Duration    time.Duration `json:"duration"`
	Retries     int           `json:"retries"`
}

// SagaResult is the final result of saga execution.
type SagaResult struct {
	ExecutionID string `json:"execution_id"`
	SagaID      string `json:"saga_id"`
	Status      SagaStatus

	CompletedSteps []string `json:"completed_steps"`

	Error        error  `json:"-"`
	ErrorMessage string `json:"error_message,omitempty"`

	Duration time.Duration `json:"duration"`

	Output map[string]interface{} `json:"output,omitempty"`

	CompensationResults []CompensationResult `json:"compensation_results,omitempty"`
}

// SagaOrchestrator defines the interface for saga orchestration.
type SagaOrchestrator interface {
	RegisterSaga(def *SagaDefinition) error
	GetSaga(sagaID string) (*SagaDefinition, error)

	Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*SagaResult, error)
	ExecuteWithCorrelation(ctx context.Context, sagaID string, input map[string]interface{}, correlationID string) (*SagaResult, error)

	Resume(ctx context.Context, executionID string) (*SagaResult, error)
	GetStatus(ctx context.Context, executionID string) (*SagaState, error)
	Cancel(ctx context.Context, executionID string) error

	Close() error
}

// SagaStore defines the interface for persisting saga state.
type SagaStore interface {
	SaveState(ctx context.Context, state *SagaState) error
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
