package eventhandlers

import "context"

// InfobaseManager defines the interface for infobase management operations
// This interface allows for easier testing with mocks
type InfobaseManager interface {
	LockInfobase(ctx context.Context, clusterID, infobaseID string) error
	UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error
	TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error)
	GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error)
}

// EventPublisher defines the interface for publishing events
// This interface allows for easier testing with mocks
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
	Close() error
}
