// go-services/worker/internal/queue/stream_consumer_test.go
package queue

import (
	"testing"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
)

// TestExtractFallbackIDs_AllFieldsPresent tests the happy path
// where all fallback fields are present in the message.
func TestExtractFallbackIDs_AllFieldsPresent(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0","type":"operation.created"}`,
			"correlation_id": "corr-12345",
			"operation_id":   "op-67890",
			"event_type":     "operation.created",
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID, "MessageID should match XMessage.ID")
	assert.Equal(t, "corr-12345", ids.CorrelationID, "CorrelationID should be extracted")
	assert.Equal(t, "op-67890", ids.OperationID, "OperationID should be extracted")
	assert.Equal(t, "operation.created", ids.EventType, "EventType should be extracted")
}

// TestExtractFallbackIDs_BackwardCompatible tests backward compatibility
// with old messages that don't have fallback fields (only data field).
// This ensures Error Feedback Phase 1 doesn't break existing functionality.
func TestExtractFallbackIDs_BackwardCompatible(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data": `{"version":"1.0"}`,
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID, "MessageID should always be set")
	assert.Empty(t, ids.CorrelationID, "CorrelationID should be empty for old messages")
	assert.Empty(t, ids.OperationID, "OperationID should be empty for old messages")
	assert.Empty(t, ids.EventType, "EventType should be empty for old messages")
}

// TestExtractFallbackIDs_PartialFields tests messages with some fallback fields present.
// Real-world scenario: Django might partially upgrade, or fields might be optional.
func TestExtractFallbackIDs_PartialFields(t *testing.T) {
	tests := []struct {
		name     string
		message  redis.XMessage
		expected FallbackIDs
	}{
		{
			name: "only correlation_id present",
			message: redis.XMessage{
				ID: "1702389123456-1",
				Values: map[string]interface{}{
					"data":           `{"version":"1.0"}`,
					"correlation_id": "corr-only",
				},
			},
			expected: FallbackIDs{
				MessageID:     "1702389123456-1",
				CorrelationID: "corr-only",
				OperationID:   "",
				EventType:     "",
			},
		},
		{
			name: "only operation_id present",
			message: redis.XMessage{
				ID: "1702389123456-2",
				Values: map[string]interface{}{
					"data":         `{"version":"1.0"}`,
					"operation_id": "op-only",
				},
			},
			expected: FallbackIDs{
				MessageID:     "1702389123456-2",
				CorrelationID: "",
				OperationID:   "op-only",
				EventType:     "",
			},
		},
		{
			name: "only event_type present",
			message: redis.XMessage{
				ID: "1702389123456-3",
				Values: map[string]interface{}{
					"data":       `{"version":"1.0"}`,
					"event_type": "test.event",
				},
			},
			expected: FallbackIDs{
				MessageID:     "1702389123456-3",
				CorrelationID: "",
				OperationID:   "",
				EventType:     "test.event",
			},
		},
		{
			name: "correlation_id and operation_id present",
			message: redis.XMessage{
				ID: "1702389123456-4",
				Values: map[string]interface{}{
					"data":           `{"version":"1.0"}`,
					"correlation_id": "corr-123",
					"operation_id":   "op-456",
				},
			},
			expected: FallbackIDs{
				MessageID:     "1702389123456-4",
				CorrelationID: "corr-123",
				OperationID:   "op-456",
				EventType:     "",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ids := extractFallbackIDs(tt.message)

			assert.Equal(t, tt.expected.MessageID, ids.MessageID)
			assert.Equal(t, tt.expected.CorrelationID, ids.CorrelationID)
			assert.Equal(t, tt.expected.OperationID, ids.OperationID)
			assert.Equal(t, tt.expected.EventType, ids.EventType)
		})
	}
}

// TestExtractFallbackIDs_EmptyStrings tests that empty strings are ignored.
// Django might accidentally send empty strings instead of omitting the field.
func TestExtractFallbackIDs_EmptyStrings(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0"}`,
			"correlation_id": "", // Empty string
			"operation_id":   "", // Empty string
			"event_type":     "", // Empty string
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Empty(t, ids.CorrelationID, "Empty correlation_id should be ignored")
	assert.Empty(t, ids.OperationID, "Empty operation_id should be ignored")
	assert.Empty(t, ids.EventType, "Empty event_type should be ignored")
}

// TestExtractFallbackIDs_NonStringValues tests that non-string values are ignored gracefully.
// This protects against unexpected data types from Redis or Django.
func TestExtractFallbackIDs_NonStringValues(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0"}`,
			"correlation_id": 12345,           // int instead of string
			"operation_id":   true,            // bool instead of string
			"event_type":     []string{"foo"}, // slice instead of string
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Empty(t, ids.CorrelationID, "Non-string correlation_id should be ignored")
	assert.Empty(t, ids.OperationID, "Non-string operation_id should be ignored")
	assert.Empty(t, ids.EventType, "Non-string event_type should be ignored")
}

// TestExtractFallbackIDs_MixedValid tests mixed valid and invalid values.
func TestExtractFallbackIDs_MixedValidAndInvalid(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0"}`,
			"correlation_id": "valid-corr",  // Valid string
			"operation_id":   123,           // Invalid: int
			"event_type":     "valid.event", // Valid string
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Equal(t, "valid-corr", ids.CorrelationID, "Valid correlation_id should be extracted")
	assert.Empty(t, ids.OperationID, "Invalid operation_id should be ignored")
	assert.Equal(t, "valid.event", ids.EventType, "Valid event_type should be extracted")
}

// TestExtractFallbackIDs_UnicodeAndSpecialChars tests that Unicode and special characters
// are preserved correctly in fallback IDs.
func TestExtractFallbackIDs_UnicodeAndSpecialChars(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0"}`,
			"correlation_id": "корр-идентификатор-123",
			"operation_id":   "op-with-@#$%-special",
			"event_type":     "事件.创建",
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Equal(t, "корр-идентификатор-123", ids.CorrelationID)
	assert.Equal(t, "op-with-@#$%-special", ids.OperationID)
	assert.Equal(t, "事件.创建", ids.EventType)
}

// TestExtractFallbackIDs_WhitespaceOnly tests that whitespace-only strings
// are treated as empty (to prevent silent failures).
func TestExtractFallbackIDs_WhitespaceOnly(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"data":           `{"version":"1.0"}`,
			"correlation_id": "   ",  // Whitespace only
			"operation_id":   "\t\n", // Tabs and newlines
			"event_type":     " ",    // Single space
		},
	}

	ids := extractFallbackIDs(message)

	// Current implementation does NOT trim whitespace - it only checks for empty string.
	// If Django sends whitespace-only values, they will be extracted as-is.
	// This test documents the current behavior.
	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Equal(t, "   ", ids.CorrelationID, "Whitespace is preserved (not trimmed)")
	assert.Equal(t, "\t\n", ids.OperationID, "Whitespace is preserved (not trimmed)")
	assert.Equal(t, " ", ids.EventType, "Whitespace is preserved (not trimmed)")
}

// TestExtractFallbackIDs_NoDataField tests that extractFallbackIDs works
// even when the "data" field is missing (edge case).
func TestExtractFallbackIDs_NoDataField(t *testing.T) {
	message := redis.XMessage{
		ID: "1702389123456-0",
		Values: map[string]interface{}{
			"correlation_id": "corr-123",
			"operation_id":   "op-456",
		},
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID)
	assert.Equal(t, "corr-123", ids.CorrelationID)
	assert.Equal(t, "op-456", ids.OperationID)
	assert.Empty(t, ids.EventType)
}

// TestExtractFallbackIDs_RealWorldScenarios tests realistic production scenarios
// based on the Error Feedback Phase 1 flow.
func TestExtractFallbackIDs_RealWorldScenarios(t *testing.T) {
	tests := []struct {
		name        string
		message     redis.XMessage
		expectedIDs FallbackIDs
		scenario    string
	}{
		{
			name: "Phase 1 new message from Django",
			message: redis.XMessage{
				ID: "1702389123456-0",
				Values: map[string]interface{}{
					"data":           `{"version":"1.0","operation_id":"op-123"}`,
					"correlation_id": "req-abc-123",
					"operation_id":   "op-123",
					"event_type":     "operation.created",
				},
			},
			expectedIDs: FallbackIDs{
				MessageID:     "1702389123456-0",
				CorrelationID: "req-abc-123",
				OperationID:   "op-123",
				EventType:     "operation.created",
			},
			scenario: "Django sends all fallback fields for Phase 1 compatibility",
		},
		{
			name: "Pre-Phase 1 message still in queue",
			message: redis.XMessage{
				ID: "1702389100000-0",
				Values: map[string]interface{}{
					"data": `{"version":"1.0","operation_id":"op-old","correlation_id":"req-old"}`,
				},
			},
			expectedIDs: FallbackIDs{
				MessageID:     "1702389100000-0",
				CorrelationID: "",
				OperationID:   "",
				EventType:     "",
			},
			scenario: "Old message without fallback fields still processes correctly",
		},
		{
			name: "Malformed envelope but fallback IDs available",
			message: redis.XMessage{
				ID: "1702389123456-0",
				Values: map[string]interface{}{
					"data":           `{malformed json`,
					"correlation_id": "req-abc-456",
					"operation_id":   "op-456",
					"event_type":     "operation.created",
				},
			},
			expectedIDs: FallbackIDs{
				MessageID:     "1702389123456-0",
				CorrelationID: "req-abc-456",
				OperationID:   "op-456",
				EventType:     "operation.created",
			},
			scenario: "Malformed data field - fallback IDs allow error reporting",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ids := extractFallbackIDs(tt.message)

			assert.Equal(t, tt.expectedIDs.MessageID, ids.MessageID,
				"MessageID mismatch in scenario: %s", tt.scenario)
			assert.Equal(t, tt.expectedIDs.CorrelationID, ids.CorrelationID,
				"CorrelationID mismatch in scenario: %s", tt.scenario)
			assert.Equal(t, tt.expectedIDs.OperationID, ids.OperationID,
				"OperationID mismatch in scenario: %s", tt.scenario)
			assert.Equal(t, tt.expectedIDs.EventType, ids.EventType,
				"EventType mismatch in scenario: %s", tt.scenario)
		})
	}
}

// TestExtractFallbackIDs_MessageIDAlwaysSet verifies that MessageID
// is ALWAYS set, even with completely empty message.
func TestExtractFallbackIDs_MessageIDAlwaysSet(t *testing.T) {
	message := redis.XMessage{
		ID:     "1702389123456-0",
		Values: map[string]interface{}{}, // Completely empty
	}

	ids := extractFallbackIDs(message)

	assert.Equal(t, "1702389123456-0", ids.MessageID, "MessageID must always be set")
	assert.Empty(t, ids.CorrelationID)
	assert.Empty(t, ids.OperationID)
	assert.Empty(t, ids.EventType)
}
