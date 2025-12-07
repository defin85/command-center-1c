package state

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"testing"
	"time"
)

func TestStateManager_InitializeExecution(t *testing.T) {
	store := NewInMemoryStateStore()
	historyStore := &NoOpHistoryStore{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	mgr := NewStateManager(store, historyStore, logger, nil)
	ctx := context.Background()

	initialContext := map[string]interface{}{
		"input": "test",
	}

	state, err := mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, initialContext)
	if err != nil {
		t.Fatalf("InitializeExecution() error = %v", err)
	}

	if state.ExecutionID != "exec-1" {
		t.Errorf("ExecutionID = %v, want exec-1", state.ExecutionID)
	}
	if state.Status != WorkflowStatusPending {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusPending)
	}
	if state.ContextSnapshot["input"] != "test" {
		t.Error("Initial context not properly set")
	}

	// Verify saved to store
	loaded, err := store.LoadState(ctx, "exec-1")
	if err != nil {
		t.Fatalf("LoadState() error = %v", err)
	}
	if loaded.ExecutionID != "exec-1" {
		t.Error("State not properly saved to store")
	}
}

func TestStateManager_StartExecution(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	// Initialize first
	_, err := mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	if err != nil {
		t.Fatalf("InitializeExecution() error = %v", err)
	}

	// Start execution
	err = mgr.StartExecution(ctx, "exec-1")
	if err != nil {
		t.Fatalf("StartExecution() error = %v", err)
	}

	// Verify status
	state, _ := mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusRunning {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusRunning)
	}
	if state.StartedAt == nil {
		t.Error("StartedAt should be set")
	}
}

func TestStateManager_CompleteExecution(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	// Initialize and start
	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartExecution(ctx, "exec-1")

	// Complete
	err := mgr.CompleteExecution(ctx, "exec-1")
	if err != nil {
		t.Fatalf("CompleteExecution() error = %v", err)
	}

	// Verify status
	state, _ := mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusCompleted {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusCompleted)
	}
	if state.CompletedAt == nil {
		t.Error("CompletedAt should be set")
	}
	if !state.Status.IsFinal() {
		t.Error("Status should be final")
	}
}

func TestStateManager_FailExecution(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartExecution(ctx, "exec-1")

	testErr := errors.New("execution failed")
	err := mgr.FailExecution(ctx, "exec-1", testErr)
	if err != nil {
		t.Fatalf("FailExecution() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
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

func TestStateManager_PauseAndResumeExecution(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartExecution(ctx, "exec-1")

	// Pause
	err := mgr.PauseExecution(ctx, "exec-1")
	if err != nil {
		t.Fatalf("PauseExecution() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusPaused {
		t.Errorf("Status after pause = %v, want %v", state.Status, WorkflowStatusPaused)
	}

	// Resume
	err = mgr.ResumeExecution(ctx, "exec-1")
	if err != nil {
		t.Fatalf("ResumeExecution() error = %v", err)
	}

	state, _ = mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusRunning {
		t.Errorf("Status after resume = %v, want %v", state.Status, WorkflowStatusRunning)
	}
}

func TestStateManager_CancelExecution(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartExecution(ctx, "exec-1")

	err := mgr.CancelExecution(ctx, "exec-1")
	if err != nil {
		t.Fatalf("CancelExecution() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusCancelled {
		t.Errorf("Status = %v, want %v", state.Status, WorkflowStatusCancelled)
	}
	if !state.Status.IsFinal() {
		t.Error("Status should be final")
	}
}

func TestStateManager_InvalidStateTransition(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	// Initialize but don't start
	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	// Try to complete without starting
	err := mgr.CompleteExecution(ctx, "exec-1")
	if err == nil {
		t.Error("Expected error when transitioning from Pending to Completed")
	}

	_, ok := err.(*InvalidTransitionError)
	if !ok {
		t.Errorf("Expected InvalidTransitionError, got %T", err)
	}
}

func TestStateManager_StartNode(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	err := mgr.StartNode(ctx, "exec-1", "node-1", "action", "Test Node")
	if err != nil {
		t.Fatalf("StartNode() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	if state.CurrentNode != "node-1" {
		t.Errorf("CurrentNode = %v, want node-1", state.CurrentNode)
	}

	nodeState, exists := state.NodeStates["node-1"]
	if !exists {
		t.Fatal("Node state not found")
	}
	if nodeState.Status != NodeStatusRunning {
		t.Errorf("Node status = %v, want %v", nodeState.Status, NodeStatusRunning)
	}
	if nodeState.StartedAt == nil {
		t.Error("Node StartedAt should be set")
	}
}

func TestStateManager_CompleteNode(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartNode(ctx, "exec-1", "node-1", "action", "Test Node")

	time.Sleep(10 * time.Millisecond)

	output := map[string]string{"result": "success"}
	err := mgr.CompleteNode(ctx, "exec-1", "node-1", output)
	if err != nil {
		t.Fatalf("CompleteNode() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	nodeState := state.NodeStates["node-1"]

	if nodeState.Status != NodeStatusCompleted {
		t.Errorf("Node status = %v, want %v", nodeState.Status, NodeStatusCompleted)
	}
	if nodeState.CompletedAt == nil {
		t.Error("Node CompletedAt should be set")
	}
	if nodeState.Duration <= 0 {
		t.Error("Node Duration should be > 0")
	}

	outputMap, ok := nodeState.Output.(map[string]string)
	if !ok {
		t.Fatal("Output type mismatch")
	}
	if outputMap["result"] != "success" {
		t.Error("Output not properly saved")
	}
}

func TestStateManager_FailNode(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartNode(ctx, "exec-1", "node-1", "action", "Test Node")

	testErr := errors.New("node execution failed")
	err := mgr.FailNode(ctx, "exec-1", "node-1", testErr)
	if err != nil {
		t.Fatalf("FailNode() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	nodeState := state.NodeStates["node-1"]

	if nodeState.Status != NodeStatusFailed {
		t.Errorf("Node status = %v, want %v", nodeState.Status, NodeStatusFailed)
	}
	if nodeState.ErrorMessage != testErr.Error() {
		t.Errorf("ErrorMessage = %v, want %v", nodeState.ErrorMessage, testErr.Error())
	}
}

func TestStateManager_SkipNode(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	err := mgr.SkipNode(ctx, "exec-1", "node-1", "action", "Test Node")
	if err != nil {
		t.Fatalf("SkipNode() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	nodeState := state.NodeStates["node-1"]

	if nodeState.Status != NodeStatusSkipped {
		t.Errorf("Node status = %v, want %v", nodeState.Status, NodeStatusSkipped)
	}
}

func TestStateManager_UpdateNodeProgress_Loop(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartNode(ctx, "exec-1", "loop-1", "loop", "Loop Node")

	err := mgr.UpdateNodeProgress(ctx, "exec-1", "loop-1", 3, 10, true)
	if err != nil {
		t.Fatalf("UpdateNodeProgress() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	nodeState := state.NodeStates["loop-1"]

	if nodeState.LoopIteration != 3 {
		t.Errorf("LoopIteration = %v, want 3", nodeState.LoopIteration)
	}
	if nodeState.LoopTotal != 10 {
		t.Errorf("LoopTotal = %v, want 10", nodeState.LoopTotal)
	}
}

func TestStateManager_UpdateNodeProgress_Parallel(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartNode(ctx, "exec-1", "parallel-1", "parallel", "Parallel Node")

	err := mgr.UpdateNodeProgress(ctx, "exec-1", "parallel-1", 5, 8, false)
	if err != nil {
		t.Fatalf("UpdateNodeProgress() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	nodeState := state.NodeStates["parallel-1"]

	if nodeState.ParallelCompleted != 5 {
		t.Errorf("ParallelCompleted = %v, want 5", nodeState.ParallelCompleted)
	}
	if nodeState.ParallelTotal != 8 {
		t.Errorf("ParallelTotal = %v, want 8", nodeState.ParallelTotal)
	}
}

func TestStateManager_SaveAndLoadCheckpoint(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	mgr.StartExecution(ctx, "exec-1")

	contextSnapshot := map[string]interface{}{
		"var1": "value1",
		"var2": 42,
	}

	err := mgr.SaveCheckpoint(ctx, "exec-1", "node-5", contextSnapshot)
	if err != nil {
		t.Fatalf("SaveCheckpoint() error = %v", err)
	}

	// Load checkpoint
	checkpoint, err := mgr.LoadCheckpoint(ctx, "exec-1")
	if err != nil {
		t.Fatalf("LoadCheckpoint() error = %v", err)
	}

	if checkpoint.NodeID != "node-5" {
		t.Errorf("NodeID = %v, want node-5", checkpoint.NodeID)
	}
	if checkpoint.ContextSnapshot["var1"] != "value1" {
		t.Error("Context snapshot not properly restored")
	}

	// Verify state was updated
	state, _ := mgr.GetState(ctx, "exec-1")
	if state.CheckpointNode != "node-5" {
		t.Errorf("CheckpointNode = %v, want node-5", state.CheckpointNode)
	}
}

func TestStateManager_AcquireAndReleaseLock(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	// Acquire lock
	acquired, err := mgr.AcquireLock(ctx, "exec-1")
	if err != nil {
		t.Fatalf("AcquireLock() error = %v", err)
	}
	if !acquired {
		t.Error("Lock acquisition should succeed")
	}

	// Try to acquire again (should fail)
	acquired, err = mgr.AcquireLock(ctx, "exec-1")
	if err != nil {
		t.Fatalf("AcquireLock() second attempt error = %v", err)
	}
	if acquired {
		t.Error("Second lock acquisition should fail")
	}

	// Release lock
	err = mgr.ReleaseLock(ctx, "exec-1")
	if err != nil {
		t.Fatalf("ReleaseLock() error = %v", err)
	}

	// Should be able to acquire again
	acquired, err = mgr.AcquireLock(ctx, "exec-1")
	if err != nil {
		t.Fatalf("AcquireLock() after release error = %v", err)
	}
	if !acquired {
		t.Error("Lock acquisition after release should succeed")
	}
}

func TestStateManager_Cleanup(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	err := mgr.Cleanup(ctx, "exec-1")
	if err != nil {
		t.Fatalf("Cleanup() error = %v", err)
	}

	// Verify state is deleted
	_, err = mgr.GetState(ctx, "exec-1")
	if !IsNotFound(err) {
		t.Error("State should be deleted after cleanup")
	}
}

func TestStateManager_UpdateCurrentNode(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)

	err := mgr.UpdateCurrentNode(ctx, "exec-1", "node-3")
	if err != nil {
		t.Fatalf("UpdateCurrentNode() error = %v", err)
	}

	state, _ := mgr.GetState(ctx, "exec-1")
	if state.CurrentNode != "node-3" {
		t.Errorf("CurrentNode = %v, want node-3", state.CurrentNode)
	}
}

func TestStateManager_GetState_NotFound(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	_, err := mgr.GetState(ctx, "nonexistent")
	if err == nil {
		t.Error("Expected error for nonexistent state")
	}
	if !IsNotFound(err) {
		t.Errorf("Expected StateNotFoundError, got %T", err)
	}
}

func TestStateManager_FullWorkflowLifecycle(t *testing.T) {
	mgr := setupTestManager(t)
	ctx := context.Background()

	// Initialize
	state, err := mgr.InitializeExecution(ctx, "exec-1", "wf-1", "dag-1", 1, nil)
	if err != nil {
		t.Fatalf("InitializeExecution() error = %v", err)
	}
	if state.Status != WorkflowStatusPending {
		t.Errorf("Initial status = %v, want Pending", state.Status)
	}

	// Start
	mgr.StartExecution(ctx, "exec-1")
	state, _ = mgr.GetState(ctx, "exec-1")
	if state.Status != WorkflowStatusRunning {
		t.Errorf("Status after start = %v, want Running", state.Status)
	}

	// Execute nodes
	mgr.StartNode(ctx, "exec-1", "node-1", "action", "Node 1")
	time.Sleep(5 * time.Millisecond)
	mgr.CompleteNode(ctx, "exec-1", "node-1", map[string]string{"result": "ok"})

	mgr.StartNode(ctx, "exec-1", "node-2", "action", "Node 2")
	time.Sleep(5 * time.Millisecond)
	mgr.CompleteNode(ctx, "exec-1", "node-2", map[string]string{"result": "ok"})

	// Save checkpoint
	mgr.SaveCheckpoint(ctx, "exec-1", "node-2", map[string]interface{}{"progress": "50%"})

	// Complete
	mgr.CompleteExecution(ctx, "exec-1")
	state, _ = mgr.GetState(ctx, "exec-1")

	if state.Status != WorkflowStatusCompleted {
		t.Errorf("Final status = %v, want Completed", state.Status)
	}
	if len(state.NodeStates) != 2 {
		t.Errorf("NodeStates count = %v, want 2", len(state.NodeStates))
	}
	if state.Duration() <= 0 {
		t.Error("Duration should be > 0")
	}
}

func TestStateManager_ConfigDefaults(t *testing.T) {
	store := NewInMemoryStateStore()
	historyStore := &NoOpHistoryStore{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	// Pass nil config to test defaults
	mgr := NewStateManager(store, historyStore, logger, nil)

	if mgr.config == nil {
		t.Error("Config should be set to defaults")
	}
	if !mgr.config.RecordHistory {
		t.Error("RecordHistory should default to true")
	}
	if mgr.config.SyncHistory {
		t.Error("SyncHistory should default to false")
	}
}

// Helper function to setup a test manager
func setupTestManager(t *testing.T) *StateManager {
	t.Helper()

	store := NewInMemoryStateStore()
	historyStore := &NoOpHistoryStore{}
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	return NewStateManager(store, historyStore, logger, nil)
}
