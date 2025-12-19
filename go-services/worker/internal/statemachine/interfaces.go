package statemachine

import "context"

// EventPublisher interface for publishing events (для mock в тестах)
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
	Close() error
}
