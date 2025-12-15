// Package events provides Redis Streams channels for inter-service communication.
package events

// Redis Streams channels for Orchestrator commands.
// Worker publishes commands to these streams, Orchestrator (Django) consumes them.
const (
	// StreamCommandsGetClusterInfo is the stream for requesting cluster info from Orchestrator.
	// Used when Worker needs to resolve database_id to cluster/infobase UUIDs.
	StreamCommandsGetClusterInfo = "commands:orchestrator:get-cluster-info"
)

// Redis Streams channels for Orchestrator events (responses).
// Orchestrator publishes responses to these streams, Worker consumes them.
const (
	// StreamEventsClusterInfoResponse is the stream for cluster info responses from Orchestrator.
	StreamEventsClusterInfoResponse = "events:orchestrator:cluster-info-response"
)

// Consumer group names for Orchestrator communication.
const (
	// ConsumerGroupOrchestrator is the consumer group name for Orchestrator instances
	// consuming commands from Worker.
	ConsumerGroupOrchestrator = "orchestrator-group"

	// ConsumerGroupWorkerClusterInfo is the consumer group name for Worker instances
	// consuming cluster info responses from Orchestrator.
	ConsumerGroupWorkerClusterInfo = "worker-cluster-info-group"
)

// AllOrchestratorCommandStreams returns a list of all Orchestrator command stream names.
func AllOrchestratorCommandStreams() []string {
	return []string{
		StreamCommandsGetClusterInfo,
	}
}

// AllOrchestratorEventStreams returns a list of all Orchestrator event stream names.
func AllOrchestratorEventStreams() []string {
	return []string{
		StreamEventsClusterInfoResponse,
	}
}
