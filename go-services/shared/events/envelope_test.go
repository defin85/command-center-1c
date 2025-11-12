package events_test

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewEnvelope(t *testing.T) {
	tests := []struct {
		name          string
		eventType     string
		serviceName   string
		payload       interface{}
		correlationID string
		wantErr       bool
	}{
		{
			name:          "valid envelope",
			eventType:     "test:event",
			serviceName:   "test-service",
			payload:       map[string]string{"key": "value"},
			correlationID: "correlation-123",
			wantErr:       false,
		},
		{
			name:          "auto-generate correlation ID",
			eventType:     "test:event",
			serviceName:   "test-service",
			payload:       map[string]string{"key": "value"},
			correlationID: "",
			wantErr:       false,
		},
		{
			name:          "invalid payload",
			eventType:     "test:event",
			serviceName:   "test-service",
			payload:       make(chan int), // channels cannot be marshaled to JSON
			correlationID: "",
			wantErr:       true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			envelope, err := events.NewEnvelope(tt.eventType, tt.serviceName, tt.payload, tt.correlationID)

			if tt.wantErr {
				assert.Error(t, err)
				assert.Nil(t, envelope)
				return
			}

			require.NoError(t, err)
			require.NotNil(t, envelope)

			// Check fields
			assert.Equal(t, events.EnvelopeVersion, envelope.Version)
			assert.NotEmpty(t, envelope.MessageID)
			assert.NotEmpty(t, envelope.CorrelationID)
			assert.Equal(t, tt.eventType, envelope.EventType)
			assert.Equal(t, tt.serviceName, envelope.ServiceName)
			assert.NotEmpty(t, envelope.Payload)

			// Check timestamp is recent
			assert.WithinDuration(t, time.Now(), envelope.Timestamp, time.Second)

			// If correlation ID was provided, check it
			if tt.correlationID != "" {
				assert.Equal(t, tt.correlationID, envelope.CorrelationID)
			}
		})
	}
}

func TestEnvelope_Validate(t *testing.T) {
	tests := []struct {
		name     string
		envelope *events.Envelope
		wantErr  error
	}{
		{
			name: "valid envelope",
			envelope: &events.Envelope{
				Version:       events.EnvelopeVersion,
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "test:event",
				ServiceName:   "test-service",
				Payload:       json.RawMessage(`{"key":"value"}`),
			},
			wantErr: nil,
		},
		{
			name:     "nil envelope",
			envelope: nil,
			wantErr:  events.ErrInvalidEnvelope,
		},
		{
			name: "invalid version",
			envelope: &events.Envelope{
				Version:       "2.0",
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "test:event",
				ServiceName:   "test-service",
				Payload:       json.RawMessage(`{"key":"value"}`),
			},
			wantErr: events.ErrInvalidVersion,
		},
		{
			name: "empty message ID",
			envelope: &events.Envelope{
				Version:       events.EnvelopeVersion,
				MessageID:     "",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "test:event",
				ServiceName:   "test-service",
				Payload:       json.RawMessage(`{"key":"value"}`),
			},
			wantErr: events.ErrEmptyMessageID,
		},
		{
			name: "empty event type",
			envelope: &events.Envelope{
				Version:       events.EnvelopeVersion,
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "",
				ServiceName:   "test-service",
				Payload:       json.RawMessage(`{"key":"value"}`),
			},
			wantErr: events.ErrEmptyEventType,
		},
		{
			name: "empty service name",
			envelope: &events.Envelope{
				Version:       events.EnvelopeVersion,
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "test:event",
				ServiceName:   "",
				Payload:       json.RawMessage(`{"key":"value"}`),
			},
			wantErr: events.ErrEmptyServiceName,
		},
		{
			name: "empty payload",
			envelope: &events.Envelope{
				Version:       events.EnvelopeVersion,
				MessageID:     "msg-123",
				CorrelationID: "corr-123",
				Timestamp:     time.Now(),
				EventType:     "test:event",
				ServiceName:   "test-service",
				Payload:       json.RawMessage{},
			},
			wantErr: events.ErrEmptyPayload,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.envelope.Validate()
			if tt.wantErr != nil {
				assert.ErrorIs(t, err, tt.wantErr)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestEnvelope_MarshalUnmarshalJSON(t *testing.T) {
	original := &events.Envelope{
		Version:       events.EnvelopeVersion,
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now().UTC().Truncate(time.Second), // Truncate for comparison
		EventType:     "test:event",
		ServiceName:   "test-service",
		Payload:       json.RawMessage(`{"key":"value"}`),
		Metadata: map[string]interface{}{
			"retry_count": 1,
			"priority":    "high",
		},
	}

	// Marshal
	data, err := json.Marshal(original)
	require.NoError(t, err)

	// Unmarshal
	var decoded events.Envelope
	err = json.Unmarshal(data, &decoded)
	require.NoError(t, err)

	// Compare
	assert.Equal(t, original.Version, decoded.Version)
	assert.Equal(t, original.MessageID, decoded.MessageID)
	assert.Equal(t, original.CorrelationID, decoded.CorrelationID)
	assert.Equal(t, original.EventType, decoded.EventType)
	assert.Equal(t, original.ServiceName, decoded.ServiceName)
	assert.Equal(t, original.Payload, decoded.Payload)

	// Timestamp should be equal (with some tolerance for JSON serialization)
	assert.WithinDuration(t, original.Timestamp, decoded.Timestamp, time.Second)

	// Check metadata
	assert.Equal(t, original.Metadata["priority"], decoded.Metadata["priority"])
}

func TestEnvelope_Metadata(t *testing.T) {
	envelope := &events.Envelope{
		Version:       events.EnvelopeVersion,
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "test:event",
		ServiceName:   "test-service",
		Payload:       json.RawMessage(`{}`),
	}

	// Set metadata
	envelope.SetMetadata("key1", "value1")
	envelope.SetMetadata("key2", 123)

	// Get metadata
	val1, ok1 := envelope.GetMetadata("key1")
	assert.True(t, ok1)
	assert.Equal(t, "value1", val1)

	val2, ok2 := envelope.GetMetadata("key2")
	assert.True(t, ok2)
	assert.Equal(t, 123, val2)

	// Get non-existent key
	_, ok3 := envelope.GetMetadata("key3")
	assert.False(t, ok3)
}

func TestEnvelope_RetryCount(t *testing.T) {
	envelope := &events.Envelope{
		Version:       events.EnvelopeVersion,
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "test:event",
		ServiceName:   "test-service",
		Payload:       json.RawMessage(`{}`),
	}

	// Initial retry count should be 0
	assert.Equal(t, 0, envelope.GetRetryCount())

	// Increment retry count
	envelope.IncrementRetryCount()
	assert.Equal(t, 1, envelope.GetRetryCount())

	envelope.IncrementRetryCount()
	assert.Equal(t, 2, envelope.GetRetryCount())
}

func TestEnvelope_IdempotencyKey(t *testing.T) {
	envelope := &events.Envelope{
		Version:       events.EnvelopeVersion,
		MessageID:     "msg-123",
		CorrelationID: "corr-123",
		Timestamp:     time.Now(),
		EventType:     "test:event",
		ServiceName:   "test-service",
		Payload:       json.RawMessage(`{}`),
	}

	// Initial idempotency key should be empty
	assert.Empty(t, envelope.GetIdempotencyKey())

	// Set idempotency key
	envelope.SetIdempotencyKey("idempotency-key-123")
	assert.Equal(t, "idempotency-key-123", envelope.GetIdempotencyKey())
}

func TestEnvelope_Validate_PayloadTooLarge(t *testing.T) {
	hugePayload := make([]byte, 2*1024*1024) // 2MB
	envelope := &events.Envelope{
		Version:       events.EnvelopeVersion,
		MessageID:     "test-id",
		CorrelationID: "test-corr",
		Timestamp:     time.Now(),
		EventType:     "test.event",
		ServiceName:   "test-service",
		Payload:       hugePayload,
	}

	err := envelope.Validate()
	assert.ErrorIs(t, err, events.ErrPayloadTooLarge)
}
