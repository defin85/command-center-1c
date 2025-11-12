package events

import "errors"

var (
	// ErrInvalidEnvelope indicates that the envelope structure is invalid
	ErrInvalidEnvelope = errors.New("invalid envelope")

	// ErrEmptyEventType indicates that the event type is empty
	ErrEmptyEventType = errors.New("empty event type")

	// ErrEmptyPayload indicates that the payload is empty
	ErrEmptyPayload = errors.New("empty payload")

	// ErrEmptyServiceName indicates that the service name is empty
	ErrEmptyServiceName = errors.New("empty service name")

	// ErrEmptyMessageID indicates that the message ID is empty
	ErrEmptyMessageID = errors.New("empty message ID")

	// ErrInvalidVersion indicates that the envelope version is invalid
	ErrInvalidVersion = errors.New("invalid envelope version")

	// ErrPublisherClosed indicates that the publisher is already closed
	ErrPublisherClosed = errors.New("publisher is closed")

	// ErrSubscriberClosed indicates that the subscriber is already closed
	ErrSubscriberClosed = errors.New("subscriber is closed")

	// ErrRedisUnavailable indicates that Redis is not available
	ErrRedisUnavailable = errors.New("redis unavailable")

	// ErrInvalidPayload indicates that the payload cannot be marshaled to JSON
	ErrInvalidPayload = errors.New("invalid payload: cannot marshal to JSON")

	// ErrMalformedMessage indicates that the received message cannot be unmarshaled
	ErrMalformedMessage = errors.New("malformed message: cannot unmarshal JSON")

	// ErrHandlerPanic indicates that the handler function panicked
	ErrHandlerPanic = errors.New("handler panic")

	// ErrPayloadTooLarge indicates that the payload size exceeds maximum allowed
	ErrPayloadTooLarge = errors.New("payload size exceeds maximum allowed")

	// ErrEmptyConsumerGroup indicates that the consumer group is empty
	ErrEmptyConsumerGroup = errors.New("empty consumer group")
)
