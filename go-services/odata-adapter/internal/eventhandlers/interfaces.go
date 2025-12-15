package eventhandlers

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"

	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
)

// ODataClient defines the interface for OData operations.
// This interface allows for easier testing with mocks.
type ODataClient interface {
	// Query executes SELECT query and returns results.
	Query(ctx context.Context, creds sharedodata.ODataCredentials, entity string, query *sharedodata.QueryParams) ([]map[string]interface{}, error)

	// Create creates a new entity and returns the created entity.
	Create(ctx context.Context, creds sharedodata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error)

	// Update updates an existing entity.
	Update(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string, data map[string]interface{}) error

	// Delete deletes an entity.
	Delete(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string) error

	// ExecuteBatch executes batch operation with multiple items (atomic changeset).
	ExecuteBatch(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error)
}

// EventPublisher defines the interface for publishing events.
// This interface allows for easier testing with mocks.
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
	Close() error
}

// RedisClient defines minimal Redis interface for idempotency checks.
type RedisClient interface {
	SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd
}

// MetricsRecorder defines the interface for recording Prometheus metrics.
// This interface allows for easier testing with mocks.
type MetricsRecorder interface {
	// RecordOperation records an OData operation execution
	RecordOperation(operation, status string, duration float64)
	// RecordTransaction records a 1C transaction duration (CRITICAL: must be < 15s!)
	RecordTransaction(operation string, duration float64)
	// RecordBatch records a batch operation with item counts
	RecordBatch(operation string, size int, successCount, failCount int)
}

// TimelineRecorder defines the interface for recording operation timeline events.
// This interface allows for easier testing with mocks.
type TimelineRecorder interface {
	// Record adds a timeline event for an operation (async, non-blocking)
	// Metadata supports any JSON-serializable values (strings, numbers, bools, etc.)
	Record(ctx context.Context, operationID, event string, metadata map[string]interface{})
}
