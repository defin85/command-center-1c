// Package checkpoint provides checkpoint and resume functionality for workflow execution.
// It enables long-running workflows to save progress and resume from failures.
package checkpoint

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/state"
)

// CheckpointManager manages workflow checkpoints for resume capability.
type CheckpointManager struct {
	stateStore state.StateStore
	logger     *slog.Logger
	config     *CheckpointConfig
}

// CheckpointConfig holds configuration for checkpoint behavior.
type CheckpointConfig struct {
	// Enabled controls whether checkpointing is active.
	Enabled bool
	// Interval is the minimum interval between automatic checkpoints.
	Interval time.Duration
	// OnNodeCompletion creates a checkpoint after each node completes.
	OnNodeCompletion bool
	// MaxCheckpoints is the maximum number of checkpoints to keep.
	MaxCheckpoints int
}

// DefaultCheckpointConfig returns sensible defaults.
func DefaultCheckpointConfig() *CheckpointConfig {
	return &CheckpointConfig{
		Enabled:          true,
		Interval:         30 * time.Second,
		OnNodeCompletion: true,
		MaxCheckpoints:   10,
	}
}

// NewCheckpointManager creates a new checkpoint manager.
func NewCheckpointManager(stateStore state.StateStore, logger *slog.Logger, config *CheckpointConfig) *CheckpointManager {
	if config == nil {
		config = DefaultCheckpointConfig()
	}
	if logger == nil {
		logger = slog.Default()
	}

	return &CheckpointManager{
		stateStore: stateStore,
		logger:     logger,
		config:     config,
	}
}

// CreateCheckpoint creates a checkpoint at the current execution state.
func (cm *CheckpointManager) CreateCheckpoint(
	ctx context.Context,
	executionID string,
	nodeID string,
	execCtx *wfcontext.ExecutionContext,
	completedNodes []string,
	nodeStates map[string]*state.NodeState,
) error {
	if !cm.config.Enabled {
		return nil
	}

	checkpoint := &state.Checkpoint{
		ExecutionID:     executionID,
		NodeID:          nodeID,
		Timestamp:       time.Now(),
		ContextSnapshot: execCtx.ToMap(),
		NodeStates:      nodeStates,
		CompletedNodes:  completedNodes,
	}

	if err := cm.stateStore.SaveCheckpoint(ctx, executionID, checkpoint); err != nil {
		cm.logger.Error("failed to save checkpoint",
			"execution_id", executionID,
			"node_id", nodeID,
			"error", err,
		)
		return fmt.Errorf("failed to save checkpoint: %w", err)
	}

	cm.logger.Info("checkpoint created",
		"execution_id", executionID,
		"node_id", nodeID,
		"completed_nodes", len(completedNodes),
	)

	return nil
}

// LoadCheckpoint loads the most recent checkpoint for an execution.
func (cm *CheckpointManager) LoadCheckpoint(ctx context.Context, executionID string) (*state.Checkpoint, error) {
	checkpoint, err := cm.stateStore.LoadCheckpoint(ctx, executionID)
	if err != nil {
		if state.IsCheckpointNotFound(err) {
			return nil, nil // No checkpoint available
		}
		return nil, fmt.Errorf("failed to load checkpoint: %w", err)
	}

	cm.logger.Info("checkpoint loaded",
		"execution_id", executionID,
		"node_id", checkpoint.NodeID,
		"timestamp", checkpoint.Timestamp,
	)

	return checkpoint, nil
}

// HasCheckpoint checks if a checkpoint exists for an execution.
func (cm *CheckpointManager) HasCheckpoint(ctx context.Context, executionID string) bool {
	checkpoint, err := cm.stateStore.LoadCheckpoint(ctx, executionID)
	return err == nil && checkpoint != nil
}

// ClearCheckpoint removes the checkpoint for an execution.
func (cm *CheckpointManager) ClearCheckpoint(ctx context.Context, executionID string) error {
	// The state store doesn't have a specific delete checkpoint method,
	// but the checkpoint will be overwritten on next save or expire with TTL
	cm.logger.Debug("checkpoint cleared", "execution_id", executionID)
	return nil
}

// ShouldCheckpoint determines if a checkpoint should be created based on config.
func (cm *CheckpointManager) ShouldCheckpoint(lastCheckpointTime time.Time) bool {
	if !cm.config.Enabled {
		return false
	}
	return time.Since(lastCheckpointTime) >= cm.config.Interval
}

// ResumableExecution contains data needed to resume an execution.
type ResumableExecution struct {
	// ExecutionID is the execution to resume.
	ExecutionID string
	// WorkflowID is the workflow being executed.
	WorkflowID string
	// DAGID is the DAG being executed.
	DAGID string
	// DAGVersion is the version of the DAG.
	DAGVersion int
	// StartFromNode is the node ID to resume from (inclusive).
	StartFromNode string
	// CompletedNodes are nodes that don't need re-execution.
	CompletedNodes map[string]bool
	// Context is the restored execution context.
	Context *wfcontext.ExecutionContext
	// NodeStates are the restored node states.
	NodeStates map[string]*state.NodeState
}

// PrepareResume prepares execution data for resuming from a checkpoint.
func (cm *CheckpointManager) PrepareResume(
	ctx context.Context,
	executionID string,
) (*ResumableExecution, error) {
	// Load workflow state
	workflowState, err := cm.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return nil, fmt.Errorf("failed to load workflow state: %w", err)
	}

	// Check if execution can be resumed
	if workflowState.Status.IsFinal() {
		return nil, fmt.Errorf("execution %s is in final state %s, cannot resume",
			executionID, workflowState.Status)
	}

	// Load checkpoint
	checkpoint, err := cm.stateStore.LoadCheckpoint(ctx, executionID)
	if err != nil {
		if state.IsCheckpointNotFound(err) {
			// No checkpoint, start from beginning
			return &ResumableExecution{
				ExecutionID:    executionID,
				WorkflowID:     workflowState.WorkflowID,
				DAGID:          workflowState.DAGID,
				DAGVersion:     workflowState.DAGVersion,
				StartFromNode:  "",
				CompletedNodes: make(map[string]bool),
				Context:        wfcontext.NewExecutionContext(executionID, workflowState.WorkflowID),
				NodeStates:     make(map[string]*state.NodeState),
			}, nil
		}
		return nil, fmt.Errorf("failed to load checkpoint: %w", err)
	}

	// Build completed nodes map
	completedNodes := make(map[string]bool)
	for _, nodeID := range checkpoint.CompletedNodes {
		completedNodes[nodeID] = true
	}

	// Restore context
	execCtx := wfcontext.NewExecutionContextWithVars(
		executionID,
		workflowState.WorkflowID,
		checkpoint.ContextSnapshot,
	)

	return &ResumableExecution{
		ExecutionID:    executionID,
		WorkflowID:     workflowState.WorkflowID,
		DAGID:          workflowState.DAGID,
		DAGVersion:     workflowState.DAGVersion,
		StartFromNode:  checkpoint.NodeID,
		CompletedNodes: completedNodes,
		Context:        execCtx,
		NodeStates:     checkpoint.NodeStates,
	}, nil
}

// ResumeStrategy determines how to handle different resume scenarios.
type ResumeStrategy int

const (
	// ResumeFromCheckpoint continues from the last checkpoint.
	ResumeFromCheckpoint ResumeStrategy = iota
	// RestartFromBeginning restarts the entire workflow.
	RestartFromBeginning
	// RestartFromNode restarts from a specific node.
	RestartFromNode
)

// ResumeOptions configures resume behavior.
type ResumeOptions struct {
	// Strategy determines how to resume.
	Strategy ResumeStrategy
	// FromNode is used with RestartFromNode strategy.
	FromNode string
	// ClearCheckpoint removes existing checkpoint before resume.
	ClearCheckpoint bool
	// ResetFailedNodes resets nodes that were in failed state.
	ResetFailedNodes bool
}

// DefaultResumeOptions returns default resume options.
func DefaultResumeOptions() *ResumeOptions {
	return &ResumeOptions{
		Strategy:         ResumeFromCheckpoint,
		ClearCheckpoint:  false,
		ResetFailedNodes: true,
	}
}

// ValidateResume checks if an execution can be resumed.
func (cm *CheckpointManager) ValidateResume(ctx context.Context, executionID string) error {
	workflowState, err := cm.stateStore.LoadState(ctx, executionID)
	if err != nil {
		if state.IsNotFound(err) {
			return fmt.Errorf("execution %s not found", executionID)
		}
		return fmt.Errorf("failed to load state: %w", err)
	}

	// Check status
	switch workflowState.Status {
	case state.WorkflowStatusCompleted:
		return fmt.Errorf("execution already completed")
	case state.WorkflowStatusCancelled:
		return fmt.Errorf("execution was cancelled")
	case state.WorkflowStatusRunning:
		return fmt.Errorf("execution is already running")
	case state.WorkflowStatusPending, state.WorkflowStatusPaused, state.WorkflowStatusFailed:
		// These can be resumed
		return nil
	default:
		return fmt.Errorf("unknown execution status: %s", workflowState.Status)
	}
}

// AutoCheckpointer wraps execution to automatically create checkpoints.
type AutoCheckpointer struct {
	manager         *CheckpointManager
	executionID     string
	lastCheckpoint  time.Time
	completedNodes  []string
}

// NewAutoCheckpointer creates an auto-checkpointer for an execution.
func NewAutoCheckpointer(manager *CheckpointManager, executionID string) *AutoCheckpointer {
	return &AutoCheckpointer{
		manager:        manager,
		executionID:    executionID,
		lastCheckpoint: time.Now(),
		completedNodes: make([]string, 0),
	}
}

// NodeCompleted is called when a node completes execution.
func (ac *AutoCheckpointer) NodeCompleted(
	ctx context.Context,
	nodeID string,
	execCtx *wfcontext.ExecutionContext,
	nodeStates map[string]*state.NodeState,
) error {
	ac.completedNodes = append(ac.completedNodes, nodeID)

	// Check if we should create a checkpoint
	if !ac.manager.config.OnNodeCompletion && !ac.manager.ShouldCheckpoint(ac.lastCheckpoint) {
		return nil
	}

	if err := ac.manager.CreateCheckpoint(ctx, ac.executionID, nodeID, execCtx, ac.completedNodes, nodeStates); err != nil {
		return err
	}

	ac.lastCheckpoint = time.Now()
	return nil
}

// ForceCheckpoint creates a checkpoint regardless of timing.
func (ac *AutoCheckpointer) ForceCheckpoint(
	ctx context.Context,
	nodeID string,
	execCtx *wfcontext.ExecutionContext,
	nodeStates map[string]*state.NodeState,
) error {
	if err := ac.manager.CreateCheckpoint(ctx, ac.executionID, nodeID, execCtx, ac.completedNodes, nodeStates); err != nil {
		return err
	}

	ac.lastCheckpoint = time.Now()
	return nil
}
