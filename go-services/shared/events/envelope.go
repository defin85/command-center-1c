package events

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
)

const (
	// EnvelopeVersion is the current version of the envelope format
	EnvelopeVersion = "1.0"

	// DefaultMaxPayloadSize is the maximum payload size in bytes (1MB)
	DefaultMaxPayloadSize = 1 * 1024 * 1024
)

// Envelope represents a message envelope for event-driven communication
type Envelope struct {
	// Version is the envelope format version (e.g., "1.0")
	Version string `json:"version"`

	// MessageID is a unique identifier for this message (UUID v4)
	MessageID string `json:"message_id"`

	// CorrelationID is used for distributed tracing across services
	CorrelationID string `json:"correlation_id"`

	// Timestamp is when the message was created (ISO8601 format)
	Timestamp time.Time `json:"timestamp"`

	// EventType describes the type of event (e.g., "commands:cluster-service:infobase:lock")
	EventType string `json:"event_type"`

	// ServiceName is the name of the service that created this message
	ServiceName string `json:"service_name"`

	// Payload contains the actual event data as JSON
	Payload json.RawMessage `json:"payload"`

	// Metadata contains additional information like retry_count, timeout_seconds, idempotency_key
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// NewEnvelope creates a new message envelope with auto-generated MessageID and Timestamp
func NewEnvelope(eventType, serviceName string, payload interface{}, correlationID string) (*Envelope, error) {
	// Marshal payload to JSON
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, ErrInvalidPayload
	}

	// Generate correlation ID if not provided
	if correlationID == "" {
		correlationID = uuid.New().String()
	}

	envelope := &Envelope{
		Version:       EnvelopeVersion,
		MessageID:     uuid.New().String(),
		CorrelationID: correlationID,
		Timestamp:     time.Now().UTC(),
		EventType:     eventType,
		ServiceName:   serviceName,
		Payload:       payloadBytes,
		Metadata:      make(map[string]interface{}),
	}

	return envelope, nil
}

// MarshalJSON implements json.Marshaler
func (e *Envelope) MarshalJSON() ([]byte, error) {
	type Alias Envelope
	return json.Marshal(&struct {
		Timestamp string `json:"timestamp"`
		*Alias
	}{
		Timestamp: e.Timestamp.Format(time.RFC3339),
		Alias:     (*Alias)(e),
	})
}

// UnmarshalJSON implements json.Unmarshaler
func (e *Envelope) UnmarshalJSON(data []byte) error {
	type Alias Envelope
	aux := &struct {
		Timestamp string `json:"timestamp"`
		*Alias
	}{
		Alias: (*Alias)(e),
	}

	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	// Parse timestamp
	timestamp, err := time.Parse(time.RFC3339, aux.Timestamp)
	if err != nil {
		return err
	}
	e.Timestamp = timestamp

	return nil
}

// Validate checks if the envelope is valid
func (e *Envelope) Validate() error {
	if e == nil {
		return ErrInvalidEnvelope
	}

	if e.Version != EnvelopeVersion {
		return ErrInvalidVersion
	}

	if e.MessageID == "" {
		return ErrEmptyMessageID
	}

	if e.EventType == "" {
		return ErrEmptyEventType
	}

	if e.ServiceName == "" {
		return ErrEmptyServiceName
	}

	if len(e.Payload) == 0 {
		return ErrEmptyPayload
	}

	// Check payload size
	if len(e.Payload) > DefaultMaxPayloadSize {
		return fmt.Errorf("payload size %d bytes: %w", len(e.Payload), ErrPayloadTooLarge)
	}

	return nil
}

// SetMetadata sets a metadata value
func (e *Envelope) SetMetadata(key string, value interface{}) {
	if e.Metadata == nil {
		e.Metadata = make(map[string]interface{})
	}
	e.Metadata[key] = value
}

// GetMetadata gets a metadata value
func (e *Envelope) GetMetadata(key string) (interface{}, bool) {
	if e.Metadata == nil {
		return nil, false
	}
	val, ok := e.Metadata[key]
	return val, ok
}

// GetRetryCount returns the retry count from metadata, or 0 if not set
func (e *Envelope) GetRetryCount() int {
	if val, ok := e.GetMetadata("retry_count"); ok {
		if count, ok := val.(int); ok {
			return count
		}
		// Try float64 (JSON unmarshaling numbers as float64)
		if count, ok := val.(float64); ok {
			return int(count)
		}
	}
	return 0
}

// IncrementRetryCount increments the retry count in metadata
func (e *Envelope) IncrementRetryCount() {
	count := e.GetRetryCount()
	e.SetMetadata("retry_count", count+1)
}

// GetIdempotencyKey returns the idempotency key from metadata, or empty string if not set
func (e *Envelope) GetIdempotencyKey() string {
	if val, ok := e.GetMetadata("idempotency_key"); ok {
		if key, ok := val.(string); ok {
			return key
		}
	}
	return ""
}

// SetIdempotencyKey sets the idempotency key in metadata
func (e *Envelope) SetIdempotencyKey(key string) {
	e.SetMetadata("idempotency_key", key)
}
