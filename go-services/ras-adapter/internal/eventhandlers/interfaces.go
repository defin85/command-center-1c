package eventhandlers

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"
)

// SessionManager defines the interface for session management operations
// This interface allows for easier testing with mocks
type SessionManager interface {
	TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error)
	GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error)
}

// InfobaseManager defines the interface for infobase management operations
// This interface allows for easier testing with mocks
type InfobaseManager interface {
	LockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
	UnlockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
}

// EventPublisher defines the interface for publishing events
// This interface allows for easier testing with mocks
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
	Close() error
}

// RedisClient defines minimal Redis interface for idempotency checks
type RedisClient interface {
	SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd
}
