package helpers

import (
	"context"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// SubscriberAdapter adapts events.Subscriber to statemachine.EventSubscriber interface
type SubscriberAdapter struct {
	subscriber *events.Subscriber
}

// NewSubscriberAdapter creates adapter for events.Subscriber
func NewSubscriberAdapter(subscriber *events.Subscriber) *SubscriberAdapter {
	return &SubscriberAdapter{subscriber: subscriber}
}

// Subscribe implements statemachine.EventSubscriber interface
func (a *SubscriberAdapter) Subscribe(channel string, handler events.HandlerFunc) error {
	return a.subscriber.Subscribe(channel, handler)
}

// Close implements statemachine.EventSubscriber interface
func (a *SubscriberAdapter) Close() error {
	return a.subscriber.Close()
}

// Run starts the subscriber (for MockEventResponder)
func (a *SubscriberAdapter) Run(ctx context.Context) error {
	return a.subscriber.Run(ctx)
}

// GetUnderlying returns underlying subscriber (for advanced usage)
func (a *SubscriberAdapter) GetUnderlying() *events.Subscriber {
	return a.subscriber
}
