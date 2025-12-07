package checkpoint

import (
	"context"
	"log/slog"
	"os"
	"testing"
	"time"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/state"
)

func TestNewCheckpointManager(t *testing.T) {
	store := state.NewInMemoryStateStore()
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	// Test with nil config
	cm := NewCheckpointManager(store, logger, nil)
	if cm.config == nil {
		t.Error("Config should be initialized to defaults")
	}
	if !cm.config.Enabled {
		t.Error("Enabled should default to true")
	}

	// Test with custom config
	config := &CheckpointConfig{
		Enabled:          false,
		Interval:         1 * time.Minute,
		OnNodeCompletion: false,
		MaxCheckpoints:   5,
	}
	cm = NewCheckpointManager(store, logger, config)
	if cm.config.Enabled {
		t.Error("Config should respect custom values")
	}
}

func TestCheckpointManager_CreateCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	execCtx = execCtx.Set("var1", "value1")
	execCtx = execCtx.Set("var2", 42)

	nodeStates := map[string]*state.NodeState{
		"node-1": state.NewNodeState("node-1", "action", "Node 1"),
		"node-2": state.NewNodeState("node-2", "action", "Node 2"),
	}
	completedNodes := []string{"node-1", "node-2"}

	err := cm.CreateCheckpoint(ctx, "exec-1", "node-3", execCtx, completedNodes, nodeStates)
	if err != nil {
		t.Fatalf("CreateCheckpoint() error = %v", err)
	}

	// Verify checkpoint was saved
	checkpoint, err := cm.LoadCheckpoint(ctx, "exec-1")
	if err != nil {
		t.Fatalf("LoadCheckpoint() error = %v", err)
	}

	if checkpoint.NodeID != "node-3" {
		t.Errorf("NodeID = %v, want node-3", checkpoint.NodeID)
	}
	if len(checkpoint.CompletedNodes) != 2 {
		t.Errorf("CompletedNodes count = %v, want 2", len(checkpoint.CompletedNodes))
	}
	if len(checkpoint.NodeStates) != 2 {
		t.Errorf("NodeStates count = %v, want 2", len(checkpoint.NodeStates))
	}
	if checkpoint.ContextSnapshot["var1"] != "value1" {
		t.Error("Context snapshot not properly saved")
	}
}

func TestCheckpointManager_CreateCheckpoint_Disabled(t *testing.T) {
	store := state.NewInMemoryStateStore()
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	config := &CheckpointConfig{Enabled: false}

	cm := NewCheckpointManager(store, logger, config)
	ctx := context.Background()

	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	// Should not create checkpoint when disabled
	err := cm.CreateCheckpoint(ctx, "exec-1", "node-1", execCtx, nil, nil)
	if err != nil {
		t.Errorf("CreateCheckpoint() should not error when disabled: %v", err)
	}

	// Verify no checkpoint was created
	checkpoint, err := cm.LoadCheckpoint(ctx, "exec-1")
	if checkpoint != nil {
		t.Error("Checkpoint should not be created when disabled")
	}
}

func TestCheckpointManager_LoadCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// Create a checkpoint first
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	execCtx = execCtx.Set("key", "value")

	cm.CreateCheckpoint(ctx, "exec-1", "node-5", execCtx, []string{"node-1"}, nil)

	// Load it
	checkpoint, err := cm.LoadCheckpoint(ctx, "exec-1")
	if err != nil {
		t.Fatalf("LoadCheckpoint() error = %v", err)
	}

	if checkpoint.ExecutionID != "exec-1" {
		t.Errorf("ExecutionID = %v, want exec-1", checkpoint.ExecutionID)
	}
	if checkpoint.NodeID != "node-5" {
		t.Errorf("NodeID = %v, want node-5", checkpoint.NodeID)
	}
}

func TestCheckpointManager_LoadCheckpoint_NotFound(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	checkpoint, err := cm.LoadCheckpoint(ctx, "nonexistent")
	if err != nil {
		t.Errorf("LoadCheckpoint() for nonexistent should return nil error: %v", err)
	}
	if checkpoint != nil {
		t.Error("Checkpoint should be nil when not found")
	}
}

func TestCheckpointManager_HasCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// No checkpoint initially
	if cm.HasCheckpoint(ctx, "exec-1") {
		t.Error("HasCheckpoint() should return false initially")
	}

	// Create checkpoint
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	cm.CreateCheckpoint(ctx, "exec-1", "node-1", execCtx, nil, nil)

	// Should have checkpoint now
	if !cm.HasCheckpoint(ctx, "exec-1") {
		t.Error("HasCheckpoint() should return true after creation")
	}
}

func TestCheckpointManager_ShouldCheckpoint(t *testing.T) {
	tests := []struct {
		name               string
		enabled            bool
		interval           time.Duration
		lastCheckpointTime time.Time
		expected           bool
	}{
		{
			name:               "Disabled checkpoint",
			enabled:            false,
			interval:           30 * time.Second,
			lastCheckpointTime: time.Now(),
			expected:           false,
		},
		{
			name:               "Within interval",
			enabled:            true,
			interval:           30 * time.Second,
			lastCheckpointTime: time.Now().Add(-10 * time.Second),
			expected:           false,
		},
		{
			name:               "Past interval",
			enabled:            true,
			interval:           30 * time.Second,
			lastCheckpointTime: time.Now().Add(-35 * time.Second),
			expected:           true,
		},
		{
			name:               "Exactly at interval",
			enabled:            true,
			interval:           30 * time.Second,
			lastCheckpointTime: time.Now().Add(-30 * time.Second),
			expected:           true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := &CheckpointConfig{
				Enabled:  tt.enabled,
				Interval: tt.interval,
			}
			cm := NewCheckpointManager(state.NewInMemoryStateStore(), nil, config)

			result := cm.ShouldCheckpoint(tt.lastCheckpointTime)
			if result != tt.expected {
				t.Errorf("ShouldCheckpoint() = %v, want %v", result, tt.expected)
			}
		})
	}
}

func TestCheckpointManager_ClearCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// Clear should not error even if checkpoint doesn't exist
	err := cm.ClearCheckpoint(ctx, "exec-1")
	if err != nil {
		t.Errorf("ClearCheckpoint() error = %v", err)
	}
}

func TestCheckpointManager_PrepareResume_NoCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// Create workflow state
	store := cm.stateStore.(*state.InMemoryStateStore)
	workflowState := state.NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	store.SaveState(ctx, workflowState)

	// Prepare resume without checkpoint
	resumable, err := cm.PrepareResume(ctx, "exec-1")
	if err != nil {
		t.Fatalf("PrepareResume() error = %v", err)
	}

	if resumable.ExecutionID != "exec-1" {
		t.Errorf("ExecutionID = %v, want exec-1", resumable.ExecutionID)
	}
	if resumable.StartFromNode != "" {
		t.Errorf("StartFromNode should be empty when no checkpoint")
	}
	if len(resumable.CompletedNodes) != 0 {
		t.Errorf("CompletedNodes should be empty when no checkpoint")
	}
}

func TestCheckpointManager_PrepareResume_WithCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// Create workflow state
	store := cm.stateStore.(*state.InMemoryStateStore)
	workflowState := state.NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	workflowState.Status = state.WorkflowStatusPaused
	store.SaveState(ctx, workflowState)

	// Create checkpoint
	checkpoint := &state.Checkpoint{
		ExecutionID:     "exec-1",
		NodeID:          "node-3",
		Timestamp:       time.Now(),
		ContextSnapshot: map[string]interface{}{"var": "value"},
		CompletedNodes:  []string{"node-1", "node-2"},
		NodeStates: map[string]*state.NodeState{
			"node-1": state.NewNodeState("node-1", "action", "Node 1"),
		},
	}
	store.SaveCheckpoint(ctx, "exec-1", checkpoint)

	// Prepare resume
	resumable, err := cm.PrepareResume(ctx, "exec-1")
	if err != nil {
		t.Fatalf("PrepareResume() error = %v", err)
	}

	if resumable.StartFromNode != "node-3" {
		t.Errorf("StartFromNode = %v, want node-3", resumable.StartFromNode)
	}
	if len(resumable.CompletedNodes) != 2 {
		t.Errorf("CompletedNodes count = %v, want 2", len(resumable.CompletedNodes))
	}
	if !resumable.CompletedNodes["node-1"] {
		t.Error("node-1 should be in completed nodes")
	}
	val, ok := resumable.Context.Get("var")
	if !ok || val != "value" {
		t.Error("Context not properly restored")
	}
}

func TestCheckpointManager_PrepareResume_FinalState(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	// Create completed workflow state
	store := cm.stateStore.(*state.InMemoryStateStore)
	workflowState := state.NewWorkflowState("exec-1", "wf-1", "dag-1", 1)
	workflowState.Status = state.WorkflowStatusCompleted
	store.SaveState(ctx, workflowState)

	// Should error for final state
	_, err := cm.PrepareResume(ctx, "exec-1")
	if err == nil {
		t.Error("Expected error when preparing resume for final state")
	}
}

func TestCheckpointManager_ValidateResume(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()
	store := cm.stateStore.(*state.InMemoryStateStore)

	tests := []struct {
		name        string
		status      state.WorkflowStatus
		expectError bool
	}{
		{"Pending can resume", state.WorkflowStatusPending, false},
		{"Paused can resume", state.WorkflowStatusPaused, false},
		{"Failed can resume", state.WorkflowStatusFailed, false},
		{"Running cannot resume", state.WorkflowStatusRunning, true},
		{"Completed cannot resume", state.WorkflowStatusCompleted, true},
		{"Cancelled cannot resume", state.WorkflowStatusCancelled, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			executionID := "exec-" + tt.name
			workflowState := state.NewWorkflowState(executionID, "wf-1", "dag-1", 1)
			workflowState.Status = tt.status
			store.SaveState(ctx, workflowState)

			err := cm.ValidateResume(ctx, executionID)
			if tt.expectError && err == nil {
				t.Error("Expected error for status", tt.status)
			}
			if !tt.expectError && err != nil {
				t.Errorf("Unexpected error for status %v: %v", tt.status, err)
			}
		})
	}
}

func TestCheckpointManager_ValidateResume_NotFound(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	err := cm.ValidateResume(ctx, "nonexistent")
	if err == nil {
		t.Error("Expected error for nonexistent execution")
	}
}

func TestAutoCheckpointer_NodeCompleted(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	ac := NewAutoCheckpointer(cm, "exec-1")

	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	nodeStates := make(map[string]*state.NodeState)

	// Complete a node
	err := ac.NodeCompleted(ctx, "node-1", execCtx, nodeStates)
	if err != nil {
		t.Fatalf("NodeCompleted() error = %v", err)
	}

	// Verify checkpoint was created (OnNodeCompletion is true by default)
	if !cm.HasCheckpoint(ctx, "exec-1") {
		t.Error("Checkpoint should be created on node completion")
	}

	checkpoint, _ := cm.LoadCheckpoint(ctx, "exec-1")
	if checkpoint.NodeID != "node-1" {
		t.Errorf("Checkpoint NodeID = %v, want node-1", checkpoint.NodeID)
	}
	if len(checkpoint.CompletedNodes) != 1 {
		t.Errorf("CompletedNodes count = %v, want 1", len(checkpoint.CompletedNodes))
	}
}

func TestAutoCheckpointer_NodeCompleted_IntervalBased(t *testing.T) {
	store := state.NewInMemoryStateStore()
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	config := &CheckpointConfig{
		Enabled:          true,
		Interval:         100 * time.Millisecond,
		OnNodeCompletion: false, // Disable automatic checkpointing
	}

	cm := NewCheckpointManager(store, logger, config)
	ctx := context.Background()

	ac := NewAutoCheckpointer(cm, "exec-1")
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	nodeStates := make(map[string]*state.NodeState)

	// Complete first node - should not checkpoint (within interval)
	ac.NodeCompleted(ctx, "node-1", execCtx, nodeStates)
	if cm.HasCheckpoint(ctx, "exec-1") {
		t.Error("Checkpoint should not be created within interval")
	}

	// Wait for interval to pass
	time.Sleep(110 * time.Millisecond)

	// Complete second node - should checkpoint
	ac.NodeCompleted(ctx, "node-2", execCtx, nodeStates)
	if !cm.HasCheckpoint(ctx, "exec-1") {
		t.Error("Checkpoint should be created after interval")
	}
}

func TestAutoCheckpointer_ForceCheckpoint(t *testing.T) {
	cm := setupTestCheckpointManager(t)
	ctx := context.Background()

	ac := NewAutoCheckpointer(cm, "exec-1")

	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")
	nodeStates := make(map[string]*state.NodeState)

	// Force checkpoint
	err := ac.ForceCheckpoint(ctx, "node-critical", execCtx, nodeStates)
	if err != nil {
		t.Fatalf("ForceCheckpoint() error = %v", err)
	}

	// Verify checkpoint was created
	checkpoint, _ := cm.LoadCheckpoint(ctx, "exec-1")
	if checkpoint.NodeID != "node-critical" {
		t.Errorf("Checkpoint NodeID = %v, want node-critical", checkpoint.NodeID)
	}
}

func TestDefaultCheckpointConfig(t *testing.T) {
	config := DefaultCheckpointConfig()

	if !config.Enabled {
		t.Error("Enabled should default to true")
	}
	if config.Interval != 30*time.Second {
		t.Errorf("Interval = %v, want 30s", config.Interval)
	}
	if !config.OnNodeCompletion {
		t.Error("OnNodeCompletion should default to true")
	}
	if config.MaxCheckpoints != 10 {
		t.Errorf("MaxCheckpoints = %v, want 10", config.MaxCheckpoints)
	}
}

func TestDefaultResumeOptions(t *testing.T) {
	opts := DefaultResumeOptions()

	if opts.Strategy != ResumeFromCheckpoint {
		t.Errorf("Strategy = %v, want ResumeFromCheckpoint", opts.Strategy)
	}
	if opts.ClearCheckpoint {
		t.Error("ClearCheckpoint should default to false")
	}
	if !opts.ResetFailedNodes {
		t.Error("ResetFailedNodes should default to true")
	}
}

// Helper function to setup test checkpoint manager
func setupTestCheckpointManager(t *testing.T) *CheckpointManager {
	t.Helper()

	store := state.NewInMemoryStateStore()
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	return NewCheckpointManager(store, logger, nil)
}
