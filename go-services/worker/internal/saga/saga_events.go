package saga

import "time"

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
