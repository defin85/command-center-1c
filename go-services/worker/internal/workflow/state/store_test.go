package state

import (
	"context"
	"testing"
	"time"
)

func TestInMemoryStateStore_SaveAndLoadState(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	state.SetStarted()

	// Save state
	err := store.SaveState(ctx, state)
	if err != nil {
		t.Fatalf("SaveState() error = %v", err)
	}

	// Load state
	loaded, err := store.LoadState(ctx, state.ExecutionID)
	if err != nil {
		t.Fatalf("LoadState() error = %v", err)
	}

	// Verify
	if loaded.ExecutionID != state.ExecutionID {
		t.Errorf("ExecutionID = %v, want %v", loaded.ExecutionID, state.ExecutionID)
	}
	if loaded.Status != state.Status {
		t.Errorf("Status = %v, want %v", loaded.Status, state.Status)
	}
}

func TestInMemoryStateStore_LoadState_NotFound(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	_, err := store.LoadState(ctx, "nonexistent")

	if err == nil {
		t.Fatal("Expected error for nonexistent state")
	}

	if !IsNotFound(err) {
		t.Errorf("Expected StateNotFoundError, got %T", err)
	}
}

func TestInMemoryStateStore_SaveState_Nil(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	err := store.SaveState(ctx, nil)
	if err == nil {
		t.Error("Expected error when saving nil state")
	}
}

func TestInMemoryStateStore_UpdateNodeState(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	// Create and save initial state
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	if err := store.SaveState(ctx, state); err != nil {
		t.Fatalf("SaveState() error = %v", err)
	}

	// Update node state
	nodeState := NewNodeState("node-1", "action", "Test Node")
	nodeState.SetNodeStarted()
	nodeState.SetNodeCompleted(map[string]string{"result": "success"})

	err := store.UpdateNodeState(ctx, state.ExecutionID, nodeState)
	if err != nil {
		t.Fatalf("UpdateNodeState() error = %v", err)
	}

	// Load and verify
	loaded, err := store.LoadState(ctx, state.ExecutionID)
	if err != nil {
		t.Fatalf("LoadState() error = %v", err)
	}

	ns, exists := loaded.NodeStates[nodeState.NodeID]
	if !exists {
		t.Fatal("Node state not found after update")
	}
	if ns.Status != NodeStatusCompleted {
		t.Errorf("Node status = %v, want %v", ns.Status, NodeStatusCompleted)
	}
}

func TestInMemoryStateStore_UpdateNodeState_StateNotFound(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	nodeState := NewNodeState("node-1", "action", "Test")
	err := store.UpdateNodeState(ctx, "nonexistent", nodeState)

	if err == nil {
		t.Error("Expected error when updating node state for nonexistent execution")
	}
	if !IsNotFound(err) {
		t.Errorf("Expected StateNotFoundError, got %T", err)
	}
}

func TestInMemoryStateStore_DeleteState(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	if err := store.SaveState(ctx, state); err != nil {
		t.Fatalf("SaveState() error = %v", err)
	}

	// Delete
	err := store.DeleteState(ctx, state.ExecutionID)
	if err != nil {
		t.Fatalf("DeleteState() error = %v", err)
	}

	// Verify deleted
	_, err = store.LoadState(ctx, state.ExecutionID)
	if err == nil {
		t.Error("State should not exist after deletion")
	}
	if !IsNotFound(err) {
		t.Errorf("Expected StateNotFoundError after deletion, got %T", err)
	}
}

func TestInMemoryStateStore_SaveAndLoadCheckpoint(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	checkpoint := &Checkpoint{
		ExecutionID: "exec-1",
		NodeID:      "node-5",
		Timestamp:   time.Now(),
		ContextSnapshot: map[string]interface{}{
			"var1": "value1",
			"var2": 42,
		},
		NodeStates: map[string]*NodeState{
			"node-1": NewNodeState("node-1", "action", "Node 1"),
		},
		CompletedNodes: []string{"node-1", "node-2", "node-3"},
	}

	// Save checkpoint
	err := store.SaveCheckpoint(ctx, checkpoint.ExecutionID, checkpoint)
	if err != nil {
		t.Fatalf("SaveCheckpoint() error = %v", err)
	}

	// Load checkpoint
	loaded, err := store.LoadCheckpoint(ctx, checkpoint.ExecutionID)
	if err != nil {
		t.Fatalf("LoadCheckpoint() error = %v", err)
	}

	// Verify
	if loaded.ExecutionID != checkpoint.ExecutionID {
		t.Errorf("ExecutionID = %v, want %v", loaded.ExecutionID, checkpoint.ExecutionID)
	}
	if loaded.NodeID != checkpoint.NodeID {
		t.Errorf("NodeID = %v, want %v", loaded.NodeID, checkpoint.NodeID)
	}
	if len(loaded.CompletedNodes) != 3 {
		t.Errorf("CompletedNodes count = %v, want 3", len(loaded.CompletedNodes))
	}
	if loaded.ContextSnapshot["var1"] != "value1" {
		t.Error("Context snapshot not properly restored")
	}
}

func TestInMemoryStateStore_LoadCheckpoint_NotFound(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	_, err := store.LoadCheckpoint(ctx, "nonexistent")

	if err == nil {
		t.Fatal("Expected error for nonexistent checkpoint")
	}
	if !IsCheckpointNotFound(err) {
		t.Errorf("Expected CheckpointNotFoundError, got %T", err)
	}
}

func TestInMemoryStateStore_SaveCheckpoint_Nil(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	err := store.SaveCheckpoint(ctx, "exec-1", nil)
	if err == nil {
		t.Error("Expected error when saving nil checkpoint")
	}
}

func TestInMemoryStateStore_SetLock(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()
	executionID := "exec-1"
	ttl := 5 * time.Second

	// First lock should succeed
	acquired, err := store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() error = %v", err)
	}
	if !acquired {
		t.Error("First lock acquisition should succeed")
	}

	// Second lock should fail (already locked)
	acquired, err = store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() error = %v", err)
	}
	if acquired {
		t.Error("Second lock acquisition should fail")
	}
}

func TestInMemoryStateStore_SetLock_Expiration(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()
	executionID := "exec-1"
	ttl := 50 * time.Millisecond

	// Acquire lock
	acquired, err := store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() error = %v", err)
	}
	if !acquired {
		t.Error("Lock acquisition should succeed")
	}

	// Wait for expiration
	time.Sleep(60 * time.Millisecond)

	// Should be able to acquire again
	acquired, err = store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() after expiration error = %v", err)
	}
	if !acquired {
		t.Error("Lock acquisition after expiration should succeed")
	}
}

func TestInMemoryStateStore_ReleaseLock(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()
	executionID := "exec-1"
	ttl := 5 * time.Second

	// Acquire lock
	acquired, err := store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() error = %v", err)
	}
	if !acquired {
		t.Fatal("Lock acquisition should succeed")
	}

	// Release lock
	err = store.ReleaseLock(ctx, executionID)
	if err != nil {
		t.Fatalf("ReleaseLock() error = %v", err)
	}

	// Should be able to acquire again immediately
	acquired, err = store.SetLock(ctx, executionID, ttl)
	if err != nil {
		t.Fatalf("SetLock() after release error = %v", err)
	}
	if !acquired {
		t.Error("Lock acquisition after release should succeed")
	}
}

func TestInMemoryStateStore_DeleteState_CleansUpAll(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()
	executionID := "exec-1"

	// Setup state, checkpoint, and lock
	state := NewWorkflowState(executionID, "wf-1", "dag-1", 1)
	store.SaveState(ctx, state)

	checkpoint := &Checkpoint{
		ExecutionID:    executionID,
		NodeID:         "node-1",
		Timestamp:      time.Now(),
		CompletedNodes: []string{"node-1"},
	}
	store.SaveCheckpoint(ctx, executionID, checkpoint)

	store.SetLock(ctx, executionID, 5*time.Second)

	// Delete
	err := store.DeleteState(ctx, executionID)
	if err != nil {
		t.Fatalf("DeleteState() error = %v", err)
	}

	// Verify all cleaned up
	if _, err := store.LoadState(ctx, executionID); !IsNotFound(err) {
		t.Error("State should be deleted")
	}
	if _, err := store.LoadCheckpoint(ctx, executionID); !IsCheckpointNotFound(err) {
		t.Error("Checkpoint should be deleted")
	}

	// Lock should be released
	acquired, _ := store.SetLock(ctx, executionID, 5*time.Second)
	if !acquired {
		t.Error("Lock should be released after DeleteState")
	}
}

func TestInMemoryStateStore_Close(t *testing.T) {
	store := NewInMemoryStateStore()

	err := store.Close()
	if err != nil {
		t.Fatalf("Close() error = %v", err)
	}
}

func TestStateNotFoundError_Message(t *testing.T) {
	err := &StateNotFoundError{ExecutionID: "exec-123"}
	expectedMsg := "state not found for execution: exec-123"

	if err.Error() != expectedMsg {
		t.Errorf("Error() = %v, want %v", err.Error(), expectedMsg)
	}
}

func TestCheckpointNotFoundError_Message(t *testing.T) {
	err := &CheckpointNotFoundError{ExecutionID: "exec-123"}
	expectedMsg := "checkpoint not found for execution: exec-123"

	if err.Error() != expectedMsg {
		t.Errorf("Error() = %v, want %v", err.Error(), expectedMsg)
	}
}

func TestIsNotFound(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected bool
	}{
		{"StateNotFoundError", &StateNotFoundError{ExecutionID: "test"}, true},
		{"Other error", &CheckpointNotFoundError{ExecutionID: "test"}, false},
		{"Nil error", nil, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsNotFound(tt.err); got != tt.expected {
				t.Errorf("IsNotFound() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestIsCheckpointNotFound(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected bool
	}{
		{"CheckpointNotFoundError", &CheckpointNotFoundError{ExecutionID: "test"}, true},
		{"Other error", &StateNotFoundError{ExecutionID: "test"}, false},
		{"Nil error", nil, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := IsCheckpointNotFound(tt.err); got != tt.expected {
				t.Errorf("IsCheckpointNotFound() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestInMemoryStateStore_ConcurrentAccess(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()

	// Create initial state
	state := NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	store.SaveState(ctx, state)

	// Concurrent updates
	done := make(chan bool)
	for i := 0; i < 10; i++ {
		go func(id int) {
			defer func() { done <- true }()

			nodeState := NewNodeState("node-1", "action", "Test")
			store.UpdateNodeState(ctx, "exec-1", nodeState)
			store.LoadState(ctx, "exec-1")
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	// Should not panic and state should still be valid
	loaded, err := store.LoadState(ctx, "exec-1")
	if err != nil {
		t.Errorf("LoadState() after concurrent access error = %v", err)
	}
	if loaded == nil {
		t.Error("State should exist after concurrent access")
	}
}

func TestInMemoryStateStore_OverwriteCheckpoint(t *testing.T) {
	store := NewInMemoryStateStore()
	ctx := context.Background()
	executionID := "exec-1"

	// Save first checkpoint
	checkpoint1 := &Checkpoint{
		ExecutionID:    executionID,
		NodeID:         "node-1",
		Timestamp:      time.Now(),
		CompletedNodes: []string{"node-1"},
	}
	store.SaveCheckpoint(ctx, executionID, checkpoint1)

	// Save second checkpoint (should overwrite)
	time.Sleep(10 * time.Millisecond)
	checkpoint2 := &Checkpoint{
		ExecutionID:    executionID,
		NodeID:         "node-5",
		Timestamp:      time.Now(),
		CompletedNodes: []string{"node-1", "node-2", "node-3", "node-4", "node-5"},
	}
	store.SaveCheckpoint(ctx, executionID, checkpoint2)

	// Load and verify it's the second checkpoint
	loaded, err := store.LoadCheckpoint(ctx, executionID)
	if err != nil {
		t.Fatalf("LoadCheckpoint() error = %v", err)
	}

	if loaded.NodeID != "node-5" {
		t.Errorf("NodeID = %v, want node-5", loaded.NodeID)
	}
	if len(loaded.CompletedNodes) != 5 {
		t.Errorf("CompletedNodes count = %v, want 5", len(loaded.CompletedNodes))
	}
}
