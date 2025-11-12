package events_test

import (
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
)

func TestGenerateCorrelationID(t *testing.T) {
	id1 := events.GenerateCorrelationID()
	id2 := events.GenerateCorrelationID()

	// Check that IDs are valid UUIDs
	_, err1 := uuid.Parse(id1)
	assert.NoError(t, err1)

	_, err2 := uuid.Parse(id2)
	assert.NoError(t, err2)

	// Check that IDs are unique
	assert.NotEqual(t, id1, id2)
}

func TestGenerateMessageID(t *testing.T) {
	id1 := events.GenerateMessageID()
	id2 := events.GenerateMessageID()

	// Check that IDs are valid UUIDs
	_, err1 := uuid.Parse(id1)
	assert.NoError(t, err1)

	_, err2 := uuid.Parse(id2)
	assert.NoError(t, err2)

	// Check that IDs are unique
	assert.NotEqual(t, id1, id2)
}

func TestGenerateIdempotencyKey(t *testing.T) {
	tests := []struct {
		name          string
		correlationID string
		eventType     string
		wantSame      bool
	}{
		{
			name:          "same inputs produce same key",
			correlationID: "corr-123",
			eventType:     "test:event",
			wantSame:      true,
		},
		{
			name:          "different correlation ID",
			correlationID: "corr-456",
			eventType:     "test:event",
			wantSame:      false,
		},
		{
			name:          "different event type",
			correlationID: "corr-123",
			eventType:     "test:event2",
			wantSame:      false,
		},
	}

	baseKey := events.GenerateIdempotencyKey("corr-123", "test:event")
	assert.NotEmpty(t, baseKey)
	assert.Len(t, baseKey, 64) // SHA256 produces 64 hex characters

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := events.GenerateIdempotencyKey(tt.correlationID, tt.eventType)
			assert.NotEmpty(t, key)

			if tt.wantSame {
				assert.Equal(t, baseKey, key, "same inputs should produce same key")
			} else {
				assert.NotEqual(t, baseKey, key, "different inputs should produce different keys")
			}
		})
	}
}

func TestGenerateIdempotencyKey_Consistency(t *testing.T) {
	// Generate the same key multiple times
	correlationID := "test-correlation"
	eventType := "test:event"

	key1 := events.GenerateIdempotencyKey(correlationID, eventType)
	key2 := events.GenerateIdempotencyKey(correlationID, eventType)
	key3 := events.GenerateIdempotencyKey(correlationID, eventType)

	// All keys should be identical
	assert.Equal(t, key1, key2)
	assert.Equal(t, key2, key3)
}

func TestValidateEnvelope(t *testing.T) {
	// Test nil envelope
	err := events.ValidateEnvelope(nil)
	assert.ErrorIs(t, err, events.ErrInvalidEnvelope)

	// Test valid envelope
	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, "")
	assert.NoError(t, err)

	err = events.ValidateEnvelope(envelope)
	assert.NoError(t, err)

	// Test invalid envelope (empty event type)
	envelope.EventType = ""
	err = events.ValidateEnvelope(envelope)
	assert.ErrorIs(t, err, events.ErrEmptyEventType)
}
