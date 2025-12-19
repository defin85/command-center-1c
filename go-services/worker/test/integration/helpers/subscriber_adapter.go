package helpers

import (
	"context"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// SubscriberAdapter adapts events.Subscriber for integration helpers.
type SubscriberAdapter struct {
	subscriber *events.Subscriber
}

// NewSubscriberAdapter creates adapter for events.Subscriber
func NewSubscriberAdapter(subscriber *events.Subscriber) *SubscriberAdapter {
	return &SubscriberAdapter{subscriber: subscriber}
}

// Subscribe forwards event subscriptions.
func (a *SubscriberAdapter) Subscribe(channel string, handler events.HandlerFunc) error {
	return a.subscriber.Subscribe(channel, handler)
}

// Close closes the underlying subscriber.
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
