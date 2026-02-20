package events

import (
	"strings"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

// WorkflowMetadataFromMessage extracts workflow correlation fields from a message.
func WorkflowMetadataFromMessage(msg *models.OperationMessage) map[string]interface{} {
	if msg == nil {
		return nil
	}

	metadata := map[string]interface{}{}
	if msg.Metadata.WorkflowExecutionID != "" {
		metadata["workflow_execution_id"] = msg.Metadata.WorkflowExecutionID
	}
	if msg.Metadata.NodeID != "" {
		metadata["node_id"] = msg.Metadata.NodeID
	}
	if msg.Metadata.TraceID != "" {
		metadata["trace_id"] = msg.Metadata.TraceID
	}
	rootOperationID := strings.TrimSpace(msg.Metadata.RootOperationID)
	if rootOperationID == "" {
		rootOperationID = strings.TrimSpace(msg.OperationID)
	}
	if rootOperationID != "" {
		metadata["root_operation_id"] = rootOperationID
	}
	executionConsumer := strings.TrimSpace(msg.Metadata.ExecutionConsumer)
	if executionConsumer == "" {
		executionConsumer = "operations"
	}
	metadata["execution_consumer"] = executionConsumer
	lane := strings.TrimSpace(msg.Metadata.Lane)
	if lane == "" {
		lane = executionConsumer
	}
	metadata["lane"] = lane

	if len(metadata) == 0 {
		return nil
	}
	return metadata
}

// MergeMetadata combines base and extra metadata maps.
func MergeMetadata(base map[string]interface{}, extra map[string]interface{}) map[string]interface{} {
	if len(base) == 0 && len(extra) == 0 {
		return nil
	}
	if len(extra) == 0 {
		return base
	}
	if len(base) == 0 {
		return extra
	}
	merged := make(map[string]interface{}, len(base)+len(extra))
	for key, value := range base {
		merged[key] = value
	}
	for key, value := range extra {
		merged[key] = value
	}
	return merged
}
