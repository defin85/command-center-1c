package state

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"
)

// StateManager orchestrates state management across Redis and PostgreSQL.
// It provides a unified interface for state operations with automatic
// persistence to both stores and event recording.
type StateManager struct {
	mu sync.RWMutex

	stateStore   StateStore
	historyStore HistoryStore
	logger       *slog.Logger

	// FSM instances per execution
	fsms map[string]*WorkflowFSM

	// Configuration
	config *StateManagerConfig
}

// StateManagerConfig holds configuration for StateManager.
type StateManagerConfig struct {
	// RecordHistory enables history recording to PostgreSQL.
	RecordHistory bool
	// SyncHistory makes history recording synchronous (blocks until complete).
	SyncHistory bool
	// LockTimeout is the timeout for distributed locks.
	LockTimeout time.Duration
}

// DefaultStateManagerConfig returns default configuration.
func DefaultStateManagerConfig() *StateManagerConfig {
	return &StateManagerConfig{
		RecordHistory: true,
		SyncHistory:   false, // Async by default for performance
		LockTimeout:   5 * time.Minute,
	}
}

// NewStateManager creates a new state manager.
func NewStateManager(
	stateStore StateStore,
	historyStore HistoryStore,
	logger *slog.Logger,
	config *StateManagerConfig,
) *StateManager {
	if config == nil {
		config = DefaultStateManagerConfig()
	}
	if logger == nil {
		logger = slog.Default()
	}

	return &StateManager{
		stateStore:   stateStore,
		historyStore: historyStore,
		logger:       logger,
		fsms:         make(map[string]*WorkflowFSM),
		config:       config,
	}
}

// InitializeExecution creates a new workflow execution state.
func (m *StateManager) InitializeExecution(
	ctx context.Context,
	executionID, workflowID, dagID string,
	dagVersion int,
	initialContext map[string]interface{},
) (*WorkflowState, error) {
	// Create new state
	state := NewWorkflowState(executionID, workflowID, dagID, dagVersion)
	if initialContext != nil {
		state.ContextSnapshot = initialContext
	}

	// Create FSM
	m.mu.Lock()
	m.fsms[executionID] = NewWorkflowFSM(WorkflowStatusPending)
	m.mu.Unlock()

	// Save to Redis
	if err := m.stateStore.SaveState(ctx, state); err != nil {
		return nil, fmt.Errorf("failed to save initial state: %w", err)
	}

	// Record to history (async)
	if m.config.RecordHistory && m.historyStore != nil {
		m.recordHistoryAsync(ctx, func() error {
			return m.historyStore.RecordExecution(ctx, state)
		})
	}

	m.logger.Info("workflow execution initialized",
		"execution_id", executionID,
		"workflow_id", workflowID,
		"dag_id", dagID,
	)

	return state, nil
}

// StartExecution marks the execution as started.
func (m *StateManager) StartExecution(ctx context.Context, executionID string) error {
	return m.transitionState(ctx, executionID, WorkflowStatusRunning, "")
}

// CompleteExecution marks the execution as completed.
func (m *StateManager) CompleteExecution(ctx context.Context, executionID string) error {
	return m.transitionState(ctx, executionID, WorkflowStatusCompleted, "")
}

// FailExecution marks the execution as failed.
func (m *StateManager) FailExecution(ctx context.Context, executionID string, err error) error {
	msg := ""
	if err != nil {
		msg = err.Error()
	}
	return m.transitionState(ctx, executionID, WorkflowStatusFailed, msg)
}

// PauseExecution marks the execution as paused.
func (m *StateManager) PauseExecution(ctx context.Context, executionID string) error {
	return m.transitionState(ctx, executionID, WorkflowStatusPaused, "")
}

// ResumeExecution resumes a paused execution.
func (m *StateManager) ResumeExecution(ctx context.Context, executionID string) error {
	return m.transitionState(ctx, executionID, WorkflowStatusRunning, "")
}

// CancelExecution cancels the execution.
func (m *StateManager) CancelExecution(ctx context.Context, executionID string) error {
	return m.transitionState(ctx, executionID, WorkflowStatusCancelled, "")
}

// transitionState performs a state transition with validation.
func (m *StateManager) transitionState(ctx context.Context, executionID string, newStatus WorkflowStatus, errorMsg string) error {
	// Get or create FSM
	fsm, err := m.getFSM(ctx, executionID)
	if err != nil {
		return err
	}

	// Validate transition
	fromStatus := fsm.CurrentState()
	if err := fsm.Transition(newStatus); err != nil {
		return err
	}

	// Load current state
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return fmt.Errorf("failed to load state: %w", err)
	}

	// Update state
	state.Status = newStatus
	state.LastUpdated = time.Now()
	if errorMsg != "" {
		state.ErrorMessage = errorMsg
	}

	now := time.Now()
	switch newStatus {
	case WorkflowStatusRunning:
		if state.StartedAt == nil {
			state.StartedAt = &now
		}
	case WorkflowStatusCompleted, WorkflowStatusFailed, WorkflowStatusCancelled:
		state.CompletedAt = &now
	}

	// Save to Redis
	if err := m.stateStore.SaveState(ctx, state); err != nil {
		return fmt.Errorf("failed to save state: %w", err)
	}

	// Record transition to history
	if m.config.RecordHistory && m.historyStore != nil {
		event := &StateTransitionEvent{
			ExecutionID: executionID,
			Timestamp:   now,
			FromStatus:  fromStatus,
			ToStatus:    newStatus,
			Message:     errorMsg,
		}
		m.recordHistoryAsync(ctx, func() error {
			if err := m.historyStore.RecordTransition(ctx, event); err != nil {
				return err
			}
			return m.historyStore.UpdateExecution(ctx, state)
		})
	}

	m.logger.Info("workflow state transition",
		"execution_id", executionID,
		"from", fromStatus,
		"to", newStatus,
	)

	return nil
}

// UpdateCurrentNode updates the currently executing node.
func (m *StateManager) UpdateCurrentNode(ctx context.Context, executionID, nodeID string) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	state.SetCurrentNode(nodeID)
	return m.stateStore.SaveState(ctx, state)
}

// StartNode marks a node as started.
func (m *StateManager) StartNode(ctx context.Context, executionID string, nodeID, nodeType, nodeName string) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	nodeState := state.GetNodeState(nodeID, nodeType, nodeName)
	nodeState.SetNodeStarted()
	state.SetCurrentNode(nodeID)

	if err := m.stateStore.SaveState(ctx, state); err != nil {
		return err
	}

	// Record to history
	if m.config.RecordHistory && m.historyStore != nil {
		m.recordHistoryAsync(ctx, func() error {
			return m.historyStore.RecordNodeExecution(ctx, executionID, nodeState)
		})
	}

	return nil
}

// CompleteNode marks a node as completed.
func (m *StateManager) CompleteNode(ctx context.Context, executionID, nodeID string, output interface{}) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	nodeState, exists := state.NodeStates[nodeID]
	if !exists {
		return fmt.Errorf("node %s not found in state", nodeID)
	}

	nodeState.SetNodeCompleted(output)

	if err := m.stateStore.SaveState(ctx, state); err != nil {
		return err
	}

	// Record to history
	if m.config.RecordHistory && m.historyStore != nil {
		m.recordHistoryAsync(ctx, func() error {
			return m.historyStore.RecordNodeExecution(ctx, executionID, nodeState)
		})
	}

	m.logger.Debug("node completed",
		"execution_id", executionID,
		"node_id", nodeID,
		"duration_ms", nodeState.Duration,
	)

	return nil
}

// FailNode marks a node as failed.
func (m *StateManager) FailNode(ctx context.Context, executionID, nodeID string, nodeErr error) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	nodeState, exists := state.NodeStates[nodeID]
	if !exists {
		return fmt.Errorf("node %s not found in state", nodeID)
	}

	nodeState.SetNodeFailed(nodeErr)

	if err := m.stateStore.SaveState(ctx, state); err != nil {
		return err
	}

	// Record to history
	if m.config.RecordHistory && m.historyStore != nil {
		m.recordHistoryAsync(ctx, func() error {
			return m.historyStore.RecordNodeExecution(ctx, executionID, nodeState)
		})
	}

	return nil
}

// SkipNode marks a node as skipped.
func (m *StateManager) SkipNode(ctx context.Context, executionID, nodeID, nodeType, nodeName string) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	nodeState := state.GetNodeState(nodeID, nodeType, nodeName)
	nodeState.SetNodeSkipped()

	return m.stateStore.SaveState(ctx, state)
}

// UpdateNodeProgress updates progress for loop/parallel nodes.
func (m *StateManager) UpdateNodeProgress(ctx context.Context, executionID, nodeID string, current, total int, isLoop bool) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	nodeState, exists := state.NodeStates[nodeID]
	if !exists {
		return fmt.Errorf("node %s not found in state", nodeID)
	}

	if isLoop {
		nodeState.UpdateLoopProgress(current, total)
	} else {
		nodeState.UpdateParallelProgress(current, total)
	}

	return m.stateStore.SaveState(ctx, state)
}

// SaveCheckpoint saves a checkpoint for resume capability.
func (m *StateManager) SaveCheckpoint(ctx context.Context, executionID, nodeID string, contextSnapshot map[string]interface{}) error {
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	// Update state with checkpoint info
	state.SetCheckpoint(nodeID, contextSnapshot)

	// Create checkpoint object
	completedNodes := make([]string, 0)
	for id, ns := range state.NodeStates {
		if ns.Status == NodeStatusCompleted {
			completedNodes = append(completedNodes, id)
		}
	}

	checkpoint := &Checkpoint{
		ExecutionID:     executionID,
		NodeID:          nodeID,
		Timestamp:       time.Now(),
		ContextSnapshot: contextSnapshot,
		NodeStates:      state.NodeStates,
		CompletedNodes:  completedNodes,
	}

	// Save checkpoint
	if err := m.stateStore.SaveCheckpoint(ctx, executionID, checkpoint); err != nil {
		return fmt.Errorf("failed to save checkpoint: %w", err)
	}

	// Save updated state
	return m.stateStore.SaveState(ctx, state)
}

// LoadCheckpoint loads the latest checkpoint.
func (m *StateManager) LoadCheckpoint(ctx context.Context, executionID string) (*Checkpoint, error) {
	return m.stateStore.LoadCheckpoint(ctx, executionID)
}

// GetState returns the current workflow state.
func (m *StateManager) GetState(ctx context.Context, executionID string) (*WorkflowState, error) {
	return m.stateStore.LoadState(ctx, executionID)
}

// AcquireLock acquires a distributed lock for an execution.
func (m *StateManager) AcquireLock(ctx context.Context, executionID string) (bool, error) {
	return m.stateStore.SetLock(ctx, executionID, m.config.LockTimeout)
}

// ReleaseLock releases the distributed lock.
func (m *StateManager) ReleaseLock(ctx context.Context, executionID string) error {
	return m.stateStore.ReleaseLock(ctx, executionID)
}

// Cleanup removes all state for an execution.
func (m *StateManager) Cleanup(ctx context.Context, executionID string) error {
	m.mu.Lock()
	delete(m.fsms, executionID)
	m.mu.Unlock()

	return m.stateStore.DeleteState(ctx, executionID)
}

// getFSM retrieves or creates an FSM for an execution.
func (m *StateManager) getFSM(ctx context.Context, executionID string) (*WorkflowFSM, error) {
	m.mu.RLock()
	fsm, exists := m.fsms[executionID]
	m.mu.RUnlock()

	if exists {
		return fsm, nil
	}

	// Load state to get current status
	state, err := m.stateStore.LoadState(ctx, executionID)
	if err != nil {
		return nil, err
	}

	// Create FSM with current status
	m.mu.Lock()
	defer m.mu.Unlock()

	// Check again after acquiring write lock
	if fsm, exists = m.fsms[executionID]; exists {
		return fsm, nil
	}

	fsm = NewWorkflowFSM(state.Status)
	m.fsms[executionID] = fsm
	return fsm, nil
}

// recordHistoryAsync records to history store asynchronously.
func (m *StateManager) recordHistoryAsync(ctx context.Context, fn func() error) {
	if m.config.SyncHistory {
		if err := fn(); err != nil {
			m.logger.Error("failed to record history", "error", err)
		}
		return
	}

	go func() {
		// Create new context with timeout for background operation
		_, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		// Check if parent context was cancelled
		select {
		case <-ctx.Done():
			return
		default:
		}

		if err := fn(); err != nil {
			m.logger.Error("failed to record history (async)", "error", err)
		}
	}()
}

// Close cleans up resources.
func (m *StateManager) Close() error {
	m.mu.Lock()
	m.fsms = make(map[string]*WorkflowFSM)
	m.mu.Unlock()

	return m.stateStore.Close()
}
