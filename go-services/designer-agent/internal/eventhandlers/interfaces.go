// Package eventhandlers provides event handlers for Designer commands.
// Handlers process commands from Redis Streams and publish results/progress events.
package eventhandlers

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/designer-agent/internal/ssh"
)

// SSHExecutor defines interface for SSH command execution via pool.
type SSHExecutor interface {
	// GetClient gets or creates an SSH client for the given configuration.
	GetClient(ctx context.Context, cfg ssh.ClientConfig) (*ssh.Client, error)

	// ReleaseClient returns a client to the pool for reuse.
	ReleaseClient(client *ssh.Client)

	// RemoveClient removes a client from the pool and closes it.
	RemoveClient(client *ssh.Client)
}

// EventPublisher defines interface for publishing events to Redis Streams.
type EventPublisher interface {
	// Publish publishes an event to the specified channel.
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error

	// Close closes the publisher.
	Close() error
}

// RedisClient defines minimal Redis interface for idempotency checks.
type RedisClient interface {
	// SetNX sets key to value if it does not exist (for idempotency).
	SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd
}
