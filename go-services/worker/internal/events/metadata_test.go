package events

import (
	"testing"

	sharedmodels "github.com/commandcenter1c/commandcenter/shared/models"
)

func TestWorkflowMetadataFromMessage_UsesDefaults(t *testing.T) {
	msg := &sharedmodels.OperationMessage{
		OperationID: "op-123",
		Metadata: sharedmodels.MessageMetadata{
			WorkflowExecutionID: "wf-1",
			NodeID:              "node-1",
		},
	}

	metadata := WorkflowMetadataFromMessage(msg)
	if metadata == nil {
		t.Fatalf("expected metadata map, got nil")
	}
	if got := metadata["workflow_execution_id"]; got != "wf-1" {
		t.Fatalf("workflow_execution_id mismatch: got %v", got)
	}
	if got := metadata["node_id"]; got != "node-1" {
		t.Fatalf("node_id mismatch: got %v", got)
	}
	if got := metadata["root_operation_id"]; got != "op-123" {
		t.Fatalf("root_operation_id mismatch: got %v", got)
	}
	if got := metadata["execution_consumer"]; got != "operations" {
		t.Fatalf("execution_consumer mismatch: got %v", got)
	}
	if got := metadata["lane"]; got != "operations" {
		t.Fatalf("lane mismatch: got %v", got)
	}
}

func TestWorkflowMetadataFromMessage_PrefersExplicitValues(t *testing.T) {
	msg := &sharedmodels.OperationMessage{
		OperationID: "op-456",
		Metadata: sharedmodels.MessageMetadata{
			RootOperationID:   "wf-root-456",
			ExecutionConsumer: "pools",
			Lane:              "workflows",
			TraceID:           "trace-1",
		},
	}

	metadata := WorkflowMetadataFromMessage(msg)
	if metadata == nil {
		t.Fatalf("expected metadata map, got nil")
	}
	if got := metadata["root_operation_id"]; got != "wf-root-456" {
		t.Fatalf("root_operation_id mismatch: got %v", got)
	}
	if got := metadata["execution_consumer"]; got != "pools" {
		t.Fatalf("execution_consumer mismatch: got %v", got)
	}
	if got := metadata["lane"]; got != "workflows" {
		t.Fatalf("lane mismatch: got %v", got)
	}
	if got := metadata["trace_id"]; got != "trace-1" {
		t.Fatalf("trace_id mismatch: got %v", got)
	}
}

func TestWorkflowMetadataFromMessage_NilInput(t *testing.T) {
	if metadata := WorkflowMetadataFromMessage(nil); metadata != nil {
		t.Fatalf("expected nil metadata for nil message, got %v", metadata)
	}
}
