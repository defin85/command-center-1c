package odata

import "fmt"

// Redis Streams channels for OData commands (legacy stream-based execution).
// Worker publishes commands to these streams, adapters consume them.
const (
	// StreamCommandsQuery is the stream for query commands
	StreamCommandsQuery = "commands:odata:query"

	// StreamCommandsCreate is the stream for create commands
	StreamCommandsCreate = "commands:odata:create"

	// StreamCommandsUpdate is the stream for update commands
	StreamCommandsUpdate = "commands:odata:update"

	// StreamCommandsDelete is the stream for delete commands
	StreamCommandsDelete = "commands:odata:delete"

	// StreamCommandsBatch is the stream for batch commands
	StreamCommandsBatch = "commands:odata:batch"
)

// Redis Streams channels for OData events (results).
// Adapters publish results to these streams, Worker consumes them.
const (
	// StreamEventsCompleted is the stream for successful command completions
	StreamEventsCompleted = "events:odata:completed"

	// StreamEventsFailed is the stream for failed command executions
	StreamEventsFailed = "events:odata:failed"
)

// Consumer group names for OData stream consumers.
const (
	// ConsumerGroupOData is the consumer group name for OData adapter instances.
	// Multiple adapter instances in this group will load-balance commands.
	ConsumerGroupOData = "odata-adapter-group"

	// ConsumerGroupWorker is the consumer group name for Worker instances
	// consuming OData results.
	ConsumerGroupWorker = "worker-odata-results-group"
)

// commandStreamMap maps command types to their Redis Streams channels.
var commandStreamMap = map[string]string{
	CommandTypeQuery:  StreamCommandsQuery,
	CommandTypeCreate: StreamCommandsCreate,
	CommandTypeUpdate: StreamCommandsUpdate,
	CommandTypeDelete: StreamCommandsDelete,
	CommandTypeBatch:  StreamCommandsBatch,
}

// GetCommandStream returns the Redis Stream channel for the given command type.
// Returns an error if the command type is not recognized.
func GetCommandStream(commandType string) (string, error) {
	stream, ok := commandStreamMap[commandType]
	if !ok {
		return "", fmt.Errorf("%w: %s", ErrInvalidCommandType, commandType)
	}
	return stream, nil
}

// MustGetCommandStream returns the Redis Stream channel for the given command type.
// Panics if the command type is not recognized.
func MustGetCommandStream(commandType string) string {
	stream, err := GetCommandStream(commandType)
	if err != nil {
		panic(err)
	}
	return stream
}

// AllCommandStreams returns a list of all command stream names.
// Useful for subscribing to all OData commands at once.
func AllCommandStreams() []string {
	return []string{
		StreamCommandsQuery,
		StreamCommandsCreate,
		StreamCommandsUpdate,
		StreamCommandsDelete,
		StreamCommandsBatch,
	}
}

// AllEventStreams returns a list of all event stream names.
// Useful for subscribing to all OData results at once.
func AllEventStreams() []string {
	return []string{
		StreamEventsCompleted,
		StreamEventsFailed,
	}
}
