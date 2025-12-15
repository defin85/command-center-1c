package eventhandlers

import (
	"context"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/redis/go-redis/v9"
)

// CredentialsFetcher is an alias for credentials.Fetcher interface
// This allows event handlers to fetch database credentials from Orchestrator
type CredentialsFetcher = credentials.Fetcher

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

// SessionBlocker defines the interface for session blocking operations (deny new connections)
// This interface allows for easier testing with mocks
type SessionBlocker interface {
	BlockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string,
		deniedFrom, deniedTo time.Time, message, permissionCode, parameter string) error
}

// SessionUnblocker defines the interface for session unblocking operations (allow new connections)
// This interface allows for easier testing with mocks
type SessionUnblocker interface {
	UnblockSessions(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error
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

// MetricsRecorder defines the interface for recording Prometheus metrics.
// This interface allows for easier testing with mocks.
type MetricsRecorder interface {
	// RecordCommand records a RAS command execution
	RecordCommand(commandType, status string, duration float64)
}

// TimelineRecorder defines the interface for recording operation timeline events.
// This interface allows for easier testing with mocks.
type TimelineRecorder interface {
	// Record adds a timeline event for an operation (async, non-blocking)
	// Metadata supports any JSON-serializable values (strings, numbers, bools, etc.)
	Record(ctx context.Context, operationID, event string, metadata map[string]interface{})
}
