package events

import (
	"crypto/sha256"
	"encoding/hex"

	"github.com/google/uuid"
)

// GenerateCorrelationID creates a new correlation ID (UUID v4)
func GenerateCorrelationID() string {
	return uuid.New().String()
}

// GenerateMessageID creates a new message ID (UUID v4)
func GenerateMessageID() string {
	return uuid.New().String()
}

// GenerateIdempotencyKey creates an idempotency key based on correlation ID and event type
// The key is a SHA256 hash of the combination of correlationID and eventType
func GenerateIdempotencyKey(correlationID, eventType string) string {
	data := correlationID + ":" + eventType
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

// ValidateEnvelope checks if an envelope is valid
// This is a convenience function that delegates to Envelope.Validate()
func ValidateEnvelope(envelope *Envelope) error {
	if envelope == nil {
		return ErrInvalidEnvelope
	}
	return envelope.Validate()
}
