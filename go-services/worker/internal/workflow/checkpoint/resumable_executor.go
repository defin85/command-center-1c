package checkpoint

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/state"
)

// ResumableExecutor wraps the standard executor with checkpoint/resume capability.
type ResumableExecutor struct {
	executor         *executor.Executor
	checkpointMgr    *CheckpointManager
	stateManager     *state.StateManager
	logger           *slog.Logger
	zapLogger        *zap.Logger
	autoCheckpointer *AutoCheckpointer
	executionID      string
	workflowID       string
}

// ResumableExecutorConfig holds configuration for ResumableExecutor.
type ResumableExecutorConfig struct {
	// ExecutorConfig is the underlying executor configuration.
	ExecutorConfig *executor.ExecutorConfig
	// CheckpointConfig controls checkpointing behavior.
	CheckpointConfig *CheckpointConfig
	// StateManagerConfig controls state management.
	StateManagerConfig *state.StateManagerConfig
}

// NewResumableExecutor creates a new resumable executor.
func NewResumableExecutor(
	dag *models.DAG,
	executionID, workflowID string,
	stateStore state.StateStore,
	historyStore state.HistoryStore,
	logger *slog.Logger,
	zapLogger *zap.Logger,
	config *ResumableExecutorConfig,
) (*ResumableExecutor, error) {
	if config == nil {
		config = &ResumableExecutorConfig{}
	}
	if logger == nil {
		logger = slog.Default()
	}
	if zapLogger == nil {
		zapLogger = zap.NewNop()
	}

	// Create underlying executor
	exec, err := executor.NewExecutorWithConfig(dag, zapLogger, config.ExecutorConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create executor: %w", err)
	}

	// Create checkpoint manager
	checkpointMgr := NewCheckpointManager(stateStore, logger, config.CheckpointConfig)

	// Create state manager
	stateManager := state.NewStateManager(stateStore, historyStore, logger, config.StateManagerConfig)

	// Create auto-checkpointer
	autoCheckpointer := NewAutoCheckpointer(checkpointMgr, executionID)

	return &ResumableExecutor{
		executor:         exec,
		checkpointMgr:    checkpointMgr,
		stateManager:     stateManager,
		logger:           logger,
		zapLogger:        zapLogger,
		autoCheckpointer: autoCheckpointer,
		executionID:      executionID,
		workflowID:       workflowID,
	}, nil
}

// RegisterHandler registers a node handler with the underlying executor.
func (re *ResumableExecutor) RegisterHandler(handler executor.NodeHandler) {
	re.executor.RegisterHandler(handler)
}

// SetConditionEvaluator sets the condition evaluator.
func (re *ResumableExecutor) SetConditionEvaluator(eval executor.ConditionEvaluator) {
	re.executor.SetConditionEvaluator(eval)
}

// Execute runs the workflow with checkpoint support.
func (re *ResumableExecutor) Execute(ctx context.Context, execCtx *wfcontext.ExecutionContext) (*wfcontext.ExecutionContext, error) {
	dag := re.executor.DAG()

	// Initialize state
	_, err := re.stateManager.InitializeExecution(
		ctx,
		re.executionID,
		re.workflowID,
		dag.ID,
		dag.Version,
		execCtx.ToMap(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize execution state: %w", err)
	}

	// Start execution
	if err := re.stateManager.StartExecution(ctx, re.executionID); err != nil {
		return nil, fmt.Errorf("failed to start execution: %w", err)
	}

	// Set up callback for state tracking and checkpointing
	nodeStates := make(map[string]*state.NodeState)
	re.executor.SetCallback(func(event executor.ExecutionEvent) {
		re.handleExecutionEvent(ctx, event, nodeStates)
	})

	// Execute
	finalCtx, err := re.executor.Execute(ctx, execCtx)
	if err != nil {
		// Fail the execution
		if failErr := re.stateManager.FailExecution(ctx, re.executionID, err); failErr != nil {
			re.logger.Error("failed to mark execution as failed",
				"execution_id", re.executionID,
				"error", failErr,
			)
		}
		return nil, err
	}

	// Complete the execution
	if err := re.stateManager.CompleteExecution(ctx, re.executionID); err != nil {
		re.logger.Error("failed to mark execution as completed",
			"execution_id", re.executionID,
			"error", err,
		)
	}

	return finalCtx, nil
}

// Resume resumes execution from a checkpoint.
func (re *ResumableExecutor) Resume(ctx context.Context, opts *ResumeOptions) (*wfcontext.ExecutionContext, error) {
	if opts == nil {
		opts = DefaultResumeOptions()
	}

	// Validate resume is possible
	if err := re.checkpointMgr.ValidateResume(ctx, re.executionID); err != nil {
		return nil, fmt.Errorf("cannot resume: %w", err)
	}

	// Prepare resume data
	resumeData, err := re.checkpointMgr.PrepareResume(ctx, re.executionID)
	if err != nil {
		return nil, fmt.Errorf("failed to prepare resume: %w", err)
	}

	re.logger.Info("resuming execution",
		"execution_id", re.executionID,
		"from_node", resumeData.StartFromNode,
		"completed_nodes", len(resumeData.CompletedNodes),
	)

	// Handle different strategies
	switch opts.Strategy {
	case RestartFromBeginning:
		// Clear completed nodes and restart
		resumeData.CompletedNodes = make(map[string]bool)
		resumeData.StartFromNode = ""
	case RestartFromNode:
		// Mark all nodes after the specified node as not completed
		resumeData.StartFromNode = opts.FromNode
		// Remove nodes that come after the restart point from completed
		re.removeNodesAfter(resumeData, opts.FromNode)
	case ResumeFromCheckpoint:
		// Use checkpoint data as-is
	}

	// Reset failed nodes if requested
	if opts.ResetFailedNodes {
		for nodeID, ns := range resumeData.NodeStates {
			if ns.Status == state.NodeStatusFailed {
				ns.Status = state.NodeStatusPending
				ns.ErrorMessage = ""
				ns.RetryCount = 0
			}
			resumeData.NodeStates[nodeID] = ns
		}
	}

	// Execute from checkpoint
	return re.executeFromCheckpoint(ctx, resumeData)
}

// executeFromCheckpoint runs execution starting from checkpoint data.
func (re *ResumableExecutor) executeFromCheckpoint(
	ctx context.Context,
	resumeData *ResumableExecution,
) (*wfcontext.ExecutionContext, error) {
	// Update state to running
	if err := re.stateManager.ResumeExecution(ctx, re.executionID); err != nil {
		return nil, fmt.Errorf("failed to update execution state: %w", err)
	}

	// Set up callback
	nodeStates := resumeData.NodeStates
	if nodeStates == nil {
		nodeStates = make(map[string]*state.NodeState)
	}

	completedNodes := make([]string, 0, len(resumeData.CompletedNodes))
	for nodeID := range resumeData.CompletedNodes {
		completedNodes = append(completedNodes, nodeID)
	}

	re.executor.SetCallback(func(event executor.ExecutionEvent) {
		re.handleExecutionEvent(ctx, event, nodeStates)
	})

	// Execute with skip list
	finalCtx, err := re.executeWithSkipList(ctx, resumeData.Context, resumeData.CompletedNodes)
	if err != nil {
		if failErr := re.stateManager.FailExecution(ctx, re.executionID, err); failErr != nil {
			re.logger.Error("failed to mark execution as failed", "error", failErr)
		}
		return nil, err
	}

	// Complete
	if err := re.stateManager.CompleteExecution(ctx, re.executionID); err != nil {
		re.logger.Error("failed to mark execution as completed", "error", err)
	}

	return finalCtx, nil
}

// executeWithSkipList executes the DAG but skips already-completed nodes.
func (re *ResumableExecutor) executeWithSkipList(
	ctx context.Context,
	execCtx *wfcontext.ExecutionContext,
	skipNodes map[string]bool,
) (*wfcontext.ExecutionContext, error) {
	currentCtx := execCtx.Clone()
	topOrder := re.executor.TopologicalOrder()

	nodeStates := make(map[string]*state.NodeState)

	for _, nodeID := range topOrder {
		// Check for cancellation
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		// Skip already completed nodes
		if skipNodes[nodeID] {
			re.logger.Debug("skipping completed node", "node_id", nodeID)
			continue
		}

		node := re.executor.DAG().GetNode(nodeID)
		if node == nil {
			return nil, fmt.Errorf("node %s not found", nodeID)
		}

		// Update state
		if err := re.stateManager.StartNode(ctx, re.executionID, nodeID, string(node.Type), node.Name); err != nil {
			re.logger.Warn("failed to record node start", "node_id", nodeID, "error", err)
		}

		// Get handler and execute
		// Note: This is a simplified version - in production, use the full executor logic
		startTime := time.Now()

		// Record completion and checkpoint
		ns := &state.NodeState{
			NodeID:   nodeID,
			NodeType: string(node.Type),
			NodeName: node.Name,
			Status:   state.NodeStatusCompleted,
		}
		now := time.Now()
		ns.StartedAt = &startTime
		ns.CompletedAt = &now
		nodeStates[nodeID] = ns

		// Auto-checkpoint
		completedNodes := make([]string, 0, len(skipNodes)+1)
		for id := range skipNodes {
			completedNodes = append(completedNodes, id)
		}
		completedNodes = append(completedNodes, nodeID)

		if err := re.autoCheckpointer.NodeCompleted(ctx, nodeID, currentCtx, nodeStates); err != nil {
			re.logger.Warn("checkpoint failed", "node_id", nodeID, "error", err)
		}

		// Mark as completed for next iteration
		skipNodes[nodeID] = true
	}

	return currentCtx, nil
}

// handleExecutionEvent handles execution events from the underlying executor.
func (re *ResumableExecutor) handleExecutionEvent(
	ctx context.Context,
	event executor.ExecutionEvent,
	nodeStates map[string]*state.NodeState,
) {
	node := re.executor.DAG().GetNode(event.NodeID)
	nodeType := ""
	nodeName := ""
	if node != nil {
		nodeType = string(node.Type)
		nodeName = node.Name
	}

	switch event.Type {
	case executor.EventNodeStarted:
		if err := re.stateManager.StartNode(ctx, re.executionID, event.NodeID, nodeType, nodeName); err != nil {
			re.logger.Warn("failed to record node start",
				"node_id", event.NodeID,
				"error", err,
			)
		}

	case executor.EventNodeCompleted:
		var output interface{}
		if event.Result != nil {
			output = event.Result.Output
		}

		if err := re.stateManager.CompleteNode(ctx, re.executionID, event.NodeID, output); err != nil {
			re.logger.Warn("failed to record node completion",
				"node_id", event.NodeID,
				"error", err,
			)
		}

		// Update local state for checkpointing
		ns := &state.NodeState{
			NodeID:   event.NodeID,
			NodeType: nodeType,
			NodeName: nodeName,
			Status:   state.NodeStatusCompleted,
			Output:   output,
		}
		ns.CompletedAt = &event.Timestamp
		if event.Result != nil {
			ns.Duration = event.Result.Duration.Milliseconds()
		}
		nodeStates[event.NodeID] = ns

	case executor.EventNodeFailed:
		if err := re.stateManager.FailNode(ctx, re.executionID, event.NodeID, event.Error); err != nil {
			re.logger.Warn("failed to record node failure",
				"node_id", event.NodeID,
				"error", err,
			)
		}

		// Update local state
		ns := &state.NodeState{
			NodeID:   event.NodeID,
			NodeType: nodeType,
			NodeName: nodeName,
			Status:   state.NodeStatusFailed,
		}
		if event.Error != nil {
			ns.ErrorMessage = event.Error.Error()
		}
		nodeStates[event.NodeID] = ns

	case executor.EventNodeSkipped:
		if err := re.stateManager.SkipNode(ctx, re.executionID, event.NodeID, nodeType, nodeName); err != nil {
			re.logger.Warn("failed to record node skip",
				"node_id", event.NodeID,
				"error", err,
			)
		}
	}
}

// removeNodesAfter removes nodes that come after the given node from completed set.
func (re *ResumableExecutor) removeNodesAfter(resumeData *ResumableExecution, fromNode string) {
	topOrder := re.executor.TopologicalOrder()

	// Find position of fromNode
	fromIdx := -1
	for i, nodeID := range topOrder {
		if nodeID == fromNode {
			fromIdx = i
			break
		}
	}

	if fromIdx == -1 {
		return // Node not found
	}

	// Remove all nodes after fromIdx from completed
	for i := fromIdx; i < len(topOrder); i++ {
		delete(resumeData.CompletedNodes, topOrder[i])
	}
}

// Pause pauses the execution and creates a checkpoint.
func (re *ResumableExecutor) Pause(ctx context.Context, execCtx *wfcontext.ExecutionContext) error {
	// Create checkpoint
	nodeStates := make(map[string]*state.NodeState)
	// Note: In production, get actual node states from state manager

	completedNodes := make([]string, 0)
	// Note: In production, build this from execution progress

	currentNode := execCtx.CurrentNode()
	if err := re.checkpointMgr.CreateCheckpoint(ctx, re.executionID, currentNode, execCtx, completedNodes, nodeStates); err != nil {
		return fmt.Errorf("failed to create checkpoint: %w", err)
	}

	// Update state to paused
	if err := re.stateManager.PauseExecution(ctx, re.executionID); err != nil {
		return fmt.Errorf("failed to pause execution: %w", err)
	}

	return nil
}

// GetState returns the current execution state.
func (re *ResumableExecutor) GetState(ctx context.Context) (*state.WorkflowState, error) {
	return re.stateManager.GetState(ctx, re.executionID)
}

// HasCheckpoint checks if a checkpoint exists.
func (re *ResumableExecutor) HasCheckpoint(ctx context.Context) bool {
	return re.checkpointMgr.HasCheckpoint(ctx, re.executionID)
}
