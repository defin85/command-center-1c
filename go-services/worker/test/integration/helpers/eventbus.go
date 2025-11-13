package helpers

import (
	"fmt"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// SetupEventBus creates Publisher and SubscriberAdapter for testing
func SetupEventBus(t *testing.T, redisClient *redis.Client) (*events.Publisher, *SubscriberAdapter) {
	// Disable verbose logs in tests
	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-publisher", logger)
	if err != nil {
		t.Fatalf("Failed to create publisher: %v", err)
	}

	// Create subscriber with unique name (prevents conflicts in parallel tests)
	subscriberName := fmt.Sprintf("test-subscriber-%d", time.Now().UnixNano())
	subscriber, err := events.NewSubscriber(redisClient, subscriberName, logger)
	if err != nil {
		t.Fatalf("Failed to create subscriber: %v", err)
	}

	// Wrap subscriber in adapter
	subscriberAdapter := NewSubscriberAdapter(subscriber)

	t.Cleanup(func() {
		publisher.Close()
		subscriber.Close()
	})

	return publisher, subscriberAdapter
}
