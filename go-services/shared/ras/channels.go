package ras

import "fmt"

// Redis Streams channels for RAS commands.
// Worker publishes commands to these streams, ras-adapter consumes them.
const (
	// StreamCommandsLock is the stream for lock commands
	StreamCommandsLock = "commands:ras:lock"

	// StreamCommandsUnlock is the stream for unlock commands
	StreamCommandsUnlock = "commands:ras:unlock"

	// StreamCommandsBlock is the stream for block commands (deny new connections)
	StreamCommandsBlock = "commands:ras:block"

	// StreamCommandsUnblock is the stream for unblock commands (allow new connections)
	StreamCommandsUnblock = "commands:ras:unblock"

	// StreamCommandsTerminate is the stream for terminate commands (kill sessions)
	StreamCommandsTerminate = "commands:ras:terminate"
)

// Redis Streams channels for RAS events (results).
// ras-adapter publishes results to these streams, Worker consumes them.
const (
	// StreamEventsCompleted is the stream for successful command completions
	StreamEventsCompleted = "events:ras:completed"

	// StreamEventsFailed is the stream for failed command executions
	StreamEventsFailed = "events:ras:failed"
)

// Consumer group names for ras-adapter.
const (
	// ConsumerGroupRAS is the consumer group name for ras-adapter instances.
	// Multiple ras-adapter instances in this group will load-balance commands.
	ConsumerGroupRAS = "ras-adapter-group"

	// ConsumerGroupWorker is the consumer group name for Worker instances
	// consuming RAS results.
	ConsumerGroupWorker = "worker-ras-results-group"
)

// commandStreamMap maps command types to their Redis Streams channels.
var commandStreamMap = map[string]string{
	CommandTypeLock:      StreamCommandsLock,
	CommandTypeUnlock:    StreamCommandsUnlock,
	CommandTypeBlock:     StreamCommandsBlock,
	CommandTypeUnblock:   StreamCommandsUnblock,
	CommandTypeTerminate: StreamCommandsTerminate,
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
// Useful for subscribing to all RAS commands at once.
func AllCommandStreams() []string {
	return []string{
		StreamCommandsLock,
		StreamCommandsUnlock,
		StreamCommandsBlock,
		StreamCommandsUnblock,
		StreamCommandsTerminate,
	}
}

// AllEventStreams returns a list of all event stream names.
// Useful for subscribing to all RAS results at once.
func AllEventStreams() []string {
	return []string{
		StreamEventsCompleted,
		StreamEventsFailed,
	}
}
