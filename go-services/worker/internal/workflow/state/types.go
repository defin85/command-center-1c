// Package state provides state management for workflow execution.
// It includes state types, FSM for transitions, Redis store for current state,
// and history client for PostgreSQL persistence via Internal API.
package state

import (
	"encoding/json"
	"time"
)

// WorkflowStatus represents the current status of a workflow execution.
type WorkflowStatus string

const (
	// WorkflowStatusPending indicates the workflow is queued but not started.
	WorkflowStatusPending WorkflowStatus = "pending"
	// WorkflowStatusRunning indicates the workflow is currently executing.
	WorkflowStatusRunning WorkflowStatus = "running"
	// WorkflowStatusPaused indicates the workflow is paused (manual or checkpoint).
	WorkflowStatusPaused WorkflowStatus = "paused"
	// WorkflowStatusCompleted indicates the workflow finished successfully.
	WorkflowStatusCompleted WorkflowStatus = "completed"
	// WorkflowStatusFailed indicates the workflow failed with an error.
	WorkflowStatusFailed WorkflowStatus = "failed"
	// WorkflowStatusCancelled indicates the workflow was manually cancelled.
	WorkflowStatusCancelled WorkflowStatus = "cancelled"
	// WorkflowStatusCompensating indicates the workflow is rolling back.
	WorkflowStatusCompensating WorkflowStatus = "compensating"
)

// IsFinal returns true if the status is a terminal state.
func (s WorkflowStatus) IsFinal() bool {
	return s == WorkflowStatusCompleted ||
		s == WorkflowStatusFailed ||
		s == WorkflowStatusCancelled
}

// String returns the string representation.
func (s WorkflowStatus) String() string {
	return string(s)
}

// NodeStatus represents the execution status of a single node.
type NodeStatus string

const (
	// NodeStatusPending indicates the node hasn't started yet.
	NodeStatusPending NodeStatus = "pending"
	// NodeStatusRunning indicates the node is currently executing.
	NodeStatusRunning NodeStatus = "running"
	// NodeStatusCompleted indicates the node finished successfully.
	NodeStatusCompleted NodeStatus = "completed"
	// NodeStatusFailed indicates the node failed with an error.
	NodeStatusFailed NodeStatus = "failed"
	// NodeStatusSkipped indicates the node was skipped (condition false).
	NodeStatusSkipped NodeStatus = "skipped"
	// NodeStatusRetrying indicates the node is waiting for retry.
	NodeStatusRetrying NodeStatus = "retrying"
)

// IsFinal returns true if the status is a terminal state for the node.
func (s NodeStatus) IsFinal() bool {
	return s == NodeStatusCompleted ||
		s == NodeStatusFailed ||
		s == NodeStatusSkipped
}

// String returns the string representation.
func (s NodeStatus) String() string {
	return string(s)
}

// WorkflowState represents the complete state of a workflow execution.
type WorkflowState struct {
	// Identity
	ExecutionID string `json:"execution_id"`
	WorkflowID  string `json:"workflow_id"`
	DAGID       string `json:"dag_id"`
	DAGVersion  int    `json:"dag_version"`

	// Status
	Status       WorkflowStatus `json:"status"`
	CurrentNode  string         `json:"current_node,omitempty"`
	ErrorMessage string         `json:"error_message,omitempty"`

	// Node states
	NodeStates map[string]*NodeState `json:"node_states,omitempty"`

	// Context snapshot (for checkpoint/resume)
	ContextSnapshot map[string]interface{} `json:"context_snapshot,omitempty"`

	// Execution metadata
	StartedAt   *time.Time `json:"started_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	LastUpdated time.Time  `json:"last_updated"`

	// Retry tracking
	RetryCount int `json:"retry_count"`
	MaxRetries int `json:"max_retries"`

	// Checkpoint info
	CheckpointNode string     `json:"checkpoint_node,omitempty"`
	CheckpointTime *time.Time `json:"checkpoint_time,omitempty"`

	// Parent workflow (for subworkflows)
	ParentExecutionID string `json:"parent_execution_id,omitempty"`
	ParentNodeID      string `json:"parent_node_id,omitempty"`
}

// NodeState represents the state of a single node execution.
type NodeState struct {
	// Identity
	NodeID   string `json:"node_id"`
	NodeType string `json:"node_type"`
	NodeName string `json:"node_name,omitempty"`

	// Status
	Status       NodeStatus `json:"status"`
	ErrorMessage string     `json:"error_message,omitempty"`

	// Execution data
	StartedAt   *time.Time  `json:"started_at,omitempty"`
	CompletedAt *time.Time  `json:"completed_at,omitempty"`
	Duration    int64       `json:"duration_ms,omitempty"` // milliseconds
	Output      interface{} `json:"output,omitempty"`

	// Retry tracking
	RetryCount  int        `json:"retry_count"`
	LastRetryAt *time.Time `json:"last_retry_at,omitempty"`

	// Loop tracking (for loop nodes)
	LoopIteration int `json:"loop_iteration,omitempty"`
	LoopTotal     int `json:"loop_total,omitempty"`

	// Parallel tracking (for parallel nodes)
	ParallelCompleted int `json:"parallel_completed,omitempty"`
	ParallelTotal     int `json:"parallel_total,omitempty"`
}

// NewWorkflowState creates a new workflow state.
func NewWorkflowState(executionID, workflowID, dagID string, dagVersion int) *WorkflowState {
	now := time.Now()
	return &WorkflowState{
		ExecutionID:     executionID,
		WorkflowID:      workflowID,
		DAGID:           dagID,
		DAGVersion:      dagVersion,
		Status:          WorkflowStatusPending,
		NodeStates:      make(map[string]*NodeState),
		ContextSnapshot: make(map[string]interface{}),
		LastUpdated:     now,
	}
}

// NewNodeState creates a new node state.
func NewNodeState(nodeID, nodeType, nodeName string) *NodeState {
	return &NodeState{
		NodeID:   nodeID,
		NodeType: nodeType,
		NodeName: nodeName,
		Status:   NodeStatusPending,
	}
}

// SetStarted marks the workflow as started.
func (ws *WorkflowState) SetStarted() {
	now := time.Now()
	ws.Status = WorkflowStatusRunning
	ws.StartedAt = &now
	ws.LastUpdated = now
}

// SetCompleted marks the workflow as completed.
func (ws *WorkflowState) SetCompleted() {
	now := time.Now()
	ws.Status = WorkflowStatusCompleted
	ws.CompletedAt = &now
	ws.LastUpdated = now
}

// SetFailed marks the workflow as failed.
func (ws *WorkflowState) SetFailed(err error) {
	now := time.Now()
	ws.Status = WorkflowStatusFailed
	ws.CompletedAt = &now
	ws.LastUpdated = now
	if err != nil {
		ws.ErrorMessage = err.Error()
	}
}

// SetPaused marks the workflow as paused.
func (ws *WorkflowState) SetPaused() {
	ws.Status = WorkflowStatusPaused
	ws.LastUpdated = time.Now()
}

// SetCancelled marks the workflow as cancelled.
func (ws *WorkflowState) SetCancelled() {
	now := time.Now()
	ws.Status = WorkflowStatusCancelled
	ws.CompletedAt = &now
	ws.LastUpdated = now
}

// SetCurrentNode updates the current executing node.
func (ws *WorkflowState) SetCurrentNode(nodeID string) {
	ws.CurrentNode = nodeID
	ws.LastUpdated = time.Now()
}

// SetCheckpoint sets a checkpoint at the given node.
func (ws *WorkflowState) SetCheckpoint(nodeID string, context map[string]interface{}) {
	now := time.Now()
	ws.CheckpointNode = nodeID
	ws.CheckpointTime = &now
	ws.ContextSnapshot = context
	ws.LastUpdated = now
}

// GetNodeState returns the state for a node, creating if needed.
func (ws *WorkflowState) GetNodeState(nodeID, nodeType, nodeName string) *NodeState {
	if ws.NodeStates == nil {
		ws.NodeStates = make(map[string]*NodeState)
	}
	if state, exists := ws.NodeStates[nodeID]; exists {
		return state
	}
	state := NewNodeState(nodeID, nodeType, nodeName)
	ws.NodeStates[nodeID] = state
	return state
}

// SetNodeStarted marks a node as started.
func (ns *NodeState) SetNodeStarted() {
	now := time.Now()
	ns.Status = NodeStatusRunning
	ns.StartedAt = &now
}

// SetNodeCompleted marks a node as completed with output.
func (ns *NodeState) SetNodeCompleted(output interface{}) {
	now := time.Now()
	ns.Status = NodeStatusCompleted
	ns.CompletedAt = &now
	ns.Output = output
	if ns.StartedAt != nil {
		ns.Duration = now.Sub(*ns.StartedAt).Milliseconds()
	}
}

// SetNodeFailed marks a node as failed.
func (ns *NodeState) SetNodeFailed(err error) {
	now := time.Now()
	ns.Status = NodeStatusFailed
	ns.CompletedAt = &now
	if err != nil {
		ns.ErrorMessage = err.Error()
	}
	if ns.StartedAt != nil {
		ns.Duration = now.Sub(*ns.StartedAt).Milliseconds()
	}
}

// SetNodeSkipped marks a node as skipped.
func (ns *NodeState) SetNodeSkipped() {
	ns.Status = NodeStatusSkipped
}

// SetNodeRetrying marks a node as waiting for retry.
func (ns *NodeState) SetNodeRetrying() {
	now := time.Now()
	ns.Status = NodeStatusRetrying
	ns.LastRetryAt = &now
	ns.RetryCount++
}

// UpdateLoopProgress updates loop iteration progress.
func (ns *NodeState) UpdateLoopProgress(current, total int) {
	ns.LoopIteration = current
	ns.LoopTotal = total
}

// UpdateParallelProgress updates parallel execution progress.
func (ns *NodeState) UpdateParallelProgress(completed, total int) {
	ns.ParallelCompleted = completed
	ns.ParallelTotal = total
}

// Duration returns the execution duration.
func (ws *WorkflowState) Duration() time.Duration {
	if ws.StartedAt == nil {
		return 0
	}
	end := ws.CompletedAt
	if end == nil {
		now := time.Now()
		end = &now
	}
	return end.Sub(*ws.StartedAt)
}

// ToJSON serializes the workflow state to JSON.
func (ws *WorkflowState) ToJSON() ([]byte, error) {
	return json.Marshal(ws)
}

// WorkflowStateFromJSON deserializes a workflow state from JSON.
func WorkflowStateFromJSON(data []byte) (*WorkflowState, error) {
	var state WorkflowState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, err
	}
	if state.NodeStates == nil {
		state.NodeStates = make(map[string]*NodeState)
	}
	if state.ContextSnapshot == nil {
		state.ContextSnapshot = make(map[string]interface{})
	}
	return &state, nil
}

// StateTransitionEvent represents a state change event for history.
type StateTransitionEvent struct {
	ExecutionID string         `json:"execution_id"`
	Timestamp   time.Time      `json:"timestamp"`
	FromStatus  WorkflowStatus `json:"from_status,omitempty"`
	ToStatus    WorkflowStatus `json:"to_status"`
	NodeID      string         `json:"node_id,omitempty"`
	NodeStatus  NodeStatus     `json:"node_status,omitempty"`
	Message     string         `json:"message,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}
