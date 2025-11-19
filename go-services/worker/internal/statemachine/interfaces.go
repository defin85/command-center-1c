package statemachine

import (
	"context"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// EventPublisher interface for publishing events (для mock в тестах)
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
	Close() error
}

// EventSubscriber interface for subscribing to events (для mock в тестах)
type EventSubscriber interface {
	Subscribe(channel string, handler events.HandlerFunc) error
	Close() error
}
