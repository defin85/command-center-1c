package state

import (
	"encoding/json"
	"errors"
	"testing"
	"time"
)

func TestWorkflowStatus_IsFinal(t *testing.T) {
	tests := []struct {
		name     string
		status   WorkflowStatus
		expected bool
	}{
		{"Pending is not final", WorkflowStatusPending, false},
		{"Running is not final", WorkflowStatusRunning, false},
		{"Paused is not final", WorkflowStatusPaused, false},
		{"Compensating is not final", WorkflowStatusCompensating, false},
		{"Completed is final", WorkflowStatusCompleted, true},
		{"Failed is final", WorkflowStatusFailed, true},
		{"Cancelled is final", WorkflowStatusCancelled, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.status.IsFinal(); got != tt.expected {
				t.Errorf("IsFinal() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestNodeStatus_IsFinal(t *testing.T) {
	tests := []struct {
		name     string
		status   NodeStatus
		expected bool
	}{
		{"Pending is not final", NodeStatusPending, false},
		{"Running is not final", NodeStatusRunning, false},
		{"Retrying is not final", NodeStatusRetrying, false},
		{"Completed is final", NodeStatusCompleted, true},
		{"Failed is final", NodeStatusFailed, true},
		{"Skipped is final", NodeStatusSkipped, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.status.IsFinal(); got != tt.expected {
				t.Errorf("IsFinal() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestNewWorkflowState(t *testing.T) {
	executionID := "exec-123"
	workflowID := "wf-456"
	dagID := "dag-789"
	dagVersion := 1

	state := NewWorkflowState(executionID, workflowID, dagID, dagVersion)

	if state.ExecutionID != executionID {
		t.Errorf("ExecutionID = %v, want %v", state.ExecutionID, executionID)
	}
	if state.WorkflowID != workflowID {
		t.Errorf("WorkflowID = %v, want %v", state.WorkflowID, workflowID)
	}
	if state.DAGID != dagID {
		t.Errorf("DAGID = %v, want %v", state.DAGID, dagID)
	}
	if state.DAGVersion != dagVersion {
		t.Errorf("DAGVersion = %v, want %v", state.DAGVersion, dagVersion)
	}
	if state.Status != WorkflowStatusPending {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusPending)
	}
	if state.NodeStates == nil {
		t.Error("NodeStates should be initialized")
	}
	if state.ContextSnapshot == nil {
		t.Error("ContextSnapshot should be initialized")
	}
}

func TestWorkflowState_SetStarted(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)

	state.SetStarted()

	if state.Status != WorkflowStatusRunning {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusRunning)
	}
	if state.StartedAt == nil {
		t.Error("StartedAt should be set")
	}
	if state.StartedAt.After(time.Now()) {
		t.Error("StartedAt should not be in the future")
	}
}

func TestWorkflowState_SetCompleted(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	state.SetStarted()
	time.Sleep(10 * time.Millisecond)

	state.SetCompleted()

	if state.Status != WorkflowStatusCompleted {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusCompleted)
	}
	if state.CompletedAt == nil {
		t.Error("CompletedAt should be set")
	}
	if state.CompletedAt.Before(*state.StartedAt) {
		t.Error("CompletedAt should be after StartedAt")
	}
}

func TestWorkflowState_SetFailed(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	testErr := errors.New("test error")

	state.SetFailed(testErr)

	if state.Status != WorkflowStatusFailed {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusFailed)
	}
	if state.ErrorMessage != testErr.Error() {
		t.Errorf("ErrorMessage = %v, want %v", state.ErrorMessage, testErr.Error())
	}
	if state.CompletedAt == nil {
		t.Error("CompletedAt should be set")
	}
}

func TestWorkflowState_GetNodeState(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	nodeID := "node-1"
	nodeType := "action"
	nodeName := "Test Node"

	// First call should create new node state
	ns := state.GetNodeState(nodeID, nodeType, nodeName)

	if ns.NodeID != nodeID {
		t.Errorf("NodeID = %v, want %v", ns.NodeID, nodeID)
	}
	if ns.NodeType != nodeType {
		t.Errorf("NodeType = %v, want %v", ns.NodeType, nodeType)
	}
	if ns.Status != NodeStatusPending {
		t.Errorf("Status = %v, want %v", ns.Status, NodeStatusPending)
	}

	// Second call should return same instance
	ns2 := state.GetNodeState(nodeID, nodeType, nodeName)
	if ns2 != ns {
		t.Error("GetNodeState should return the same instance on subsequent calls")
	}
}

func TestWorkflowState_Duration(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)

	// Before started
	if duration := state.Duration(); duration != 0 {
		t.Errorf("Duration before start = %v, want 0", duration)
	}

	// After started
	state.SetStarted()
	time.Sleep(50 * time.Millisecond)

	duration := state.Duration()
	if duration < 50*time.Millisecond {
		t.Errorf("Duration = %v, want >= 50ms", duration)
	}

	// After completed
	time.Sleep(50 * time.Millisecond)
	state.SetCompleted()

	finalDuration := state.Duration()
	if finalDuration < duration {
		t.Error("Final duration should be >= duration before completion")
	}
}

func TestWorkflowState_JSON_Serialization(t *testing.T) {
	original := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	original.SetStarted()
	original.ContextSnapshot["key"] = "value"

	ns := original.GetNodeState("node-1", "action", "Test")
	ns.SetNodeStarted()
	ns.SetNodeCompleted(map[string]string{"result": "success"})

	// Serialize
	data, err := original.ToJSON()
	if err != nil {
		t.Fatalf("ToJSON() error = %v", err)
	}

	// Deserialize
	restored, err := WorkflowStateFromJSON(data)
	if err != nil {
		t.Fatalf("WorkflowStateFromJSON() error = %v", err)
	}

	// Verify
	if restored.ExecutionID != original.ExecutionID {
		t.Errorf("ExecutionID = %v, want %v", restored.ExecutionID, original.ExecutionID)
	}
	if restored.Status != original.Status {
		t.Errorf("Status = %v, want %v", restored.Status, original.Status)
	}
	if len(restored.NodeStates) != len(original.NodeStates) {
		t.Errorf("NodeStates count = %v, want %v", len(restored.NodeStates), len(original.NodeStates))
	}
	if restored.ContextSnapshot["key"] != "value" {
		t.Errorf("ContextSnapshot key = %v, want 'value'", restored.ContextSnapshot["key"])
	}
}

func TestNodeState_SetNodeCompleted(t *testing.T) {
	ns := NewNodeState("node-1", "action", "Test Node")
	ns.SetNodeStarted()
	time.Sleep(10 * time.Millisecond)

	output := map[string]interface{}{"result": "success"}
	ns.SetNodeCompleted(output)

	if ns.Status != NodeStatusCompleted {
		t.Errorf("Status = %v, want %v", ns.Status, NodeStatusCompleted)
	}
	if ns.CompletedAt == nil {
		t.Error("CompletedAt should be set")
	}
	if ns.Duration <= 0 {
		t.Errorf("Duration = %v, want > 0", ns.Duration)
	}

	// Verify output
	outputMap, ok := ns.Output.(map[string]interface{})
	if !ok {
		t.Fatal("Output type mismatch")
	}
	if outputMap["result"] != "success" {
		t.Errorf("Output result = %v, want 'success'", outputMap["result"])
	}
}

func TestNodeState_SetNodeRetrying(t *testing.T) {
	ns := NewNodeState("node-1", "action", "Test Node")
	ns.SetNodeStarted()

	initialRetryCount := ns.RetryCount

	ns.SetNodeRetrying()

	if ns.Status != NodeStatusRetrying {
		t.Errorf("Status = %v, want %v", ns.Status, NodeStatusRetrying)
	}
	if ns.RetryCount != initialRetryCount+1 {
		t.Errorf("RetryCount = %v, want %v", ns.RetryCount, initialRetryCount+1)
	}
	if ns.LastRetryAt == nil {
		t.Error("LastRetryAt should be set")
	}
}

func TestNodeState_UpdateLoopProgress(t *testing.T) {
	ns := NewNodeState("loop-1", "loop", "Loop Node")

	ns.UpdateLoopProgress(3, 10)

	if ns.LoopIteration != 3 {
		t.Errorf("LoopIteration = %v, want 3", ns.LoopIteration)
	}
	if ns.LoopTotal != 10 {
		t.Errorf("LoopTotal = %v, want 10", ns.LoopTotal)
	}
}

func TestNodeState_UpdateParallelProgress(t *testing.T) {
	ns := NewNodeState("parallel-1", "parallel", "Parallel Node")

	ns.UpdateParallelProgress(5, 8)

	if ns.ParallelCompleted != 5 {
		t.Errorf("ParallelCompleted = %v, want 5", ns.ParallelCompleted)
	}
	if ns.ParallelTotal != 8 {
		t.Errorf("ParallelTotal = %v, want 8", ns.ParallelTotal)
	}
}

func TestWorkflowState_SetCheckpoint(t *testing.T) {
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	nodeID := "checkpoint-node"
	context := map[string]interface{}{
		"var1": "value1",
		"var2": 42,
	}

	state.SetCheckpoint(nodeID, context)

	if state.CheckpointNode != nodeID {
		t.Errorf("CheckpointNode = %v, want %v", state.CheckpointNode, nodeID)
	}
	if state.CheckpointTime == nil {
		t.Error("CheckpointTime should be set")
	}
	if len(state.ContextSnapshot) != 2 {
		t.Errorf("ContextSnapshot length = %v, want 2", len(state.ContextSnapshot))
	}
	if state.ContextSnapshot["var1"] != "value1" {
		t.Error("Context snapshot not properly set")
	}
}

func TestStateTransitionEvent_JSON(t *testing.T) {
	event := &StateTransitionEvent{
		ExecutionID: "exec-1",
		Timestamp:   time.Now(),
		FromStatus:  WorkflowStatusPending,
		ToStatus:    WorkflowStatusRunning,
		NodeID:      "node-1",
		NodeStatus:  NodeStatusRunning,
		Message:     "Starting execution",
		Metadata: map[string]interface{}{
			"key": "value",
		},
	}

	// Serialize and deserialize
	data, err := json.Marshal(event)
	if err != nil {
		t.Fatalf("JSON marshal error: %v", err)
	}

	var restored StateTransitionEvent
	if err := json.Unmarshal(data, &restored); err != nil {
		t.Fatalf("JSON unmarshal error: %v", err)
	}

	if restored.ExecutionID != event.ExecutionID {
		t.Errorf("ExecutionID mismatch")
	}
	if restored.FromStatus != event.FromStatus {
		t.Errorf("FromStatus mismatch")
	}
	if restored.ToStatus != event.ToStatus {
		t.Errorf("ToStatus mismatch")
	}
}
