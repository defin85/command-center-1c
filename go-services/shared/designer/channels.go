package designer

import "fmt"

// Redis Streams channels for Designer commands.
// Worker publishes commands to these streams, designer-agent consumes them.
const (
	// StreamCommandsExtensionInstall is the stream for extension install commands
	StreamCommandsExtensionInstall = "commands:designer:extension-install"

	// StreamCommandsExtensionRemove is the stream for extension remove commands
	StreamCommandsExtensionRemove = "commands:designer:extension-remove"

	// StreamCommandsConfigUpdate is the stream for config update commands
	StreamCommandsConfigUpdate = "commands:designer:config-update"

	// StreamCommandsConfigLoad is the stream for config load commands
	StreamCommandsConfigLoad = "commands:designer:config-load"

	// StreamCommandsConfigDump is the stream for config dump commands
	StreamCommandsConfigDump = "commands:designer:config-dump"

	// StreamCommandsEpfExport is the stream for EPF export commands
	StreamCommandsEpfExport = "commands:designer:epf-export"

	// StreamCommandsEpfImport is the stream for EPF import commands
	StreamCommandsEpfImport = "commands:designer:epf-import"

	// StreamCommandsMetadataExport is the stream for metadata export commands
	StreamCommandsMetadataExport = "commands:designer:metadata-export"
)

// Redis Streams channels for Designer events (results).
// designer-agent publishes results to these streams, Worker consumes them.
const (
	// StreamEventsCompleted is the stream for successful command completions
	StreamEventsCompleted = "events:designer:completed"

	// StreamEventsFailed is the stream for failed command executions
	StreamEventsFailed = "events:designer:failed"

	// StreamEventsProgress is the stream for progress updates
	StreamEventsProgress = "events:designer:progress"
)

// Consumer group names for designer-agent.
const (
	// ConsumerGroupDesigner is the consumer group name for designer-agent instances.
	// Multiple designer-agent instances in this group will load-balance commands.
	ConsumerGroupDesigner = "designer-agent-group"

	// ConsumerGroupWorker is the consumer group name for Worker instances
	// consuming Designer results.
	ConsumerGroupWorker = "worker-designer-results-group"
)

// commandStreamMap maps command types to their Redis Streams channels.
var commandStreamMap = map[string]string{
	CommandTypeExtensionInstall: StreamCommandsExtensionInstall,
	CommandTypeExtensionRemove:  StreamCommandsExtensionRemove,
	CommandTypeConfigUpdate:     StreamCommandsConfigUpdate,
	CommandTypeConfigLoad:       StreamCommandsConfigLoad,
	CommandTypeConfigDump:       StreamCommandsConfigDump,
	CommandTypeEpfExport:        StreamCommandsEpfExport,
	CommandTypeEpfImport:        StreamCommandsEpfImport,
	CommandTypeMetadataExport:   StreamCommandsMetadataExport,
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
// Useful for subscribing to all Designer commands at once.
func AllCommandStreams() []string {
	return []string{
		StreamCommandsExtensionInstall,
		StreamCommandsExtensionRemove,
		StreamCommandsConfigUpdate,
		StreamCommandsConfigLoad,
		StreamCommandsConfigDump,
		StreamCommandsEpfExport,
		StreamCommandsEpfImport,
		StreamCommandsMetadataExport,
	}
}

// AllEventStreams returns a list of all event stream names.
// Useful for subscribing to all Designer results at once.
func AllEventStreams() []string {
	return []string{
		StreamEventsCompleted,
		StreamEventsFailed,
		StreamEventsProgress,
	}
}
