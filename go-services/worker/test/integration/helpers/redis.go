package helpers

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/statemachine"
	"github.com/redis/go-redis/v9"
)

// SetupTestRedis creates a Redis client for testing and ensures it's available
func SetupTestRedis(t *testing.T) *redis.Client {
	client := redis.NewClient(&redis.Options{
		Addr: "127.0.0.1:6380", // Test Redis from docker-compose.test.yml (use IPv4 explicitly)
		DB:   1,                 // Use DB 1 for tests
	})

	// Check availability
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := client.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Test Redis not available on localhost:6380: %v. Start test Redis: docker-compose -f docker-compose.test.yml up -d redis-test", err)
	}

	// Cleanup before suite
	if err := client.FlushDB(context.Background()).Err(); err != nil {
		t.Fatalf("Failed to flush test DB: %v", err)
	}

	t.Cleanup(func() {
		client.Close()
	})

	return client
}

// TestConfig returns State Machine configuration optimized for fast testing (10x faster)
func TestConfig() *statemachine.Config {
	return &statemachine.Config{
		// Timeouts - 10x faster than production
		TimeoutLockJobs:      3 * time.Second,  // Production: 30s
		TimeoutTerminate:     9 * time.Second,  // Production: 90s
		TimeoutInstall:       30 * time.Second, // Production: 5min
		TimeoutUnlock:        3 * time.Second,  // Production: 30s
		TimeoutCompensation:  12 * time.Second, // Production: 2min

		// Retry configuration
		MaxRetries:        2,
		RetryInitialDelay: 200 * time.Millisecond,
		RetryMaxDelay:     1 * time.Second,
		RetryMultiplier:   2.0,

		// Persistence
		StateTTL: 1 * time.Hour,

		// Deduplication
		DeduplicationTTL: 5 * time.Minute,
	}
}
