package state

import (
	"fmt"
	"sync"
)

// WorkflowFSM is a finite state machine for workflow state transitions.
// It enforces valid state transitions and prevents invalid state changes.
type WorkflowFSM struct {
	mu           sync.RWMutex
	currentState WorkflowStatus
	transitions  map[WorkflowStatus][]WorkflowStatus
	hooks        []TransitionHook
}

// TransitionHook is called when a state transition occurs.
type TransitionHook func(from, to WorkflowStatus)

// NewWorkflowFSM creates a new workflow FSM with the given initial state.
func NewWorkflowFSM(initialState WorkflowStatus) *WorkflowFSM {
	fsm := &WorkflowFSM{
		currentState: initialState,
		transitions:  buildWorkflowTransitions(),
		hooks:        make([]TransitionHook, 0),
	}
	return fsm
}

// buildWorkflowTransitions defines all valid workflow state transitions.
func buildWorkflowTransitions() map[WorkflowStatus][]WorkflowStatus {
	return map[WorkflowStatus][]WorkflowStatus{
		WorkflowStatusPending: {
			WorkflowStatusRunning,
			WorkflowStatusCancelled,
		},
		WorkflowStatusRunning: {
			WorkflowStatusPaused,
			WorkflowStatusCompleted,
			WorkflowStatusFailed,
			WorkflowStatusCancelled,
			WorkflowStatusCompensating,
		},
		WorkflowStatusPaused: {
			WorkflowStatusRunning,
			WorkflowStatusCancelled,
			WorkflowStatusFailed,
		},
		WorkflowStatusCompensating: {
			WorkflowStatusFailed,
			WorkflowStatusCancelled,
		},
		// Final states have no outgoing transitions
		WorkflowStatusCompleted:  {},
		WorkflowStatusFailed:     {},
		WorkflowStatusCancelled:  {},
	}
}

// CurrentState returns the current state of the FSM.
func (fsm *WorkflowFSM) CurrentState() WorkflowStatus {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.currentState
}

// CanTransition checks if a transition from current state to target is valid.
func (fsm *WorkflowFSM) CanTransition(to WorkflowStatus) bool {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.canTransitionUnsafe(to)
}

// canTransitionUnsafe checks transition without locking (caller must hold lock).
func (fsm *WorkflowFSM) canTransitionUnsafe(to WorkflowStatus) bool {
	validTargets, exists := fsm.transitions[fsm.currentState]
	if !exists {
		return false
	}
	for _, target := range validTargets {
		if target == to {
			return true
		}
	}
	return false
}

// Transition attempts to transition to a new state.
// Returns an error if the transition is invalid.
func (fsm *WorkflowFSM) Transition(to WorkflowStatus) error {
	var from WorkflowStatus
	var hooksToCall []TransitionHook

	fsm.mu.Lock()
	if !fsm.canTransitionUnsafe(to) {
		fsm.mu.Unlock()
		return &InvalidTransitionError{
			From: fsm.currentState,
			To:   to,
		}
	}

	from = fsm.currentState
	fsm.currentState = to

	// Copy hooks to call outside lock
	hooksToCall = make([]TransitionHook, len(fsm.hooks))
	copy(hooksToCall, fsm.hooks)
	fsm.mu.Unlock()

	// Call hooks outside lock to prevent deadlocks
	for _, hook := range hooksToCall {
		hook(from, to)
	}

	return nil
}

// ForceState sets the state without validation (for recovery scenarios).
func (fsm *WorkflowFSM) ForceState(state WorkflowStatus) {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()
	fsm.currentState = state
}

// AddHook adds a transition hook that will be called on state changes.
func (fsm *WorkflowFSM) AddHook(hook TransitionHook) {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()
	fsm.hooks = append(fsm.hooks, hook)
}

// ValidTransitions returns the list of valid target states from current state.
func (fsm *WorkflowFSM) ValidTransitions() []WorkflowStatus {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()

	targets, exists := fsm.transitions[fsm.currentState]
	if !exists {
		return nil
	}
	result := make([]WorkflowStatus, len(targets))
	copy(result, targets)
	return result
}

// IsFinal returns true if current state is a terminal state.
func (fsm *WorkflowFSM) IsFinal() bool {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.currentState.IsFinal()
}

// InvalidTransitionError represents an invalid state transition attempt.
type InvalidTransitionError struct {
	From WorkflowStatus
	To   WorkflowStatus
}

func (e *InvalidTransitionError) Error() string {
	return fmt.Sprintf("invalid transition from %s to %s", e.From, e.To)
}

// NodeFSM is a finite state machine for node state transitions.
type NodeFSM struct {
	mu           sync.RWMutex
	currentState NodeStatus
	transitions  map[NodeStatus][]NodeStatus
}

// NewNodeFSM creates a new node FSM with the given initial state.
func NewNodeFSM(initialState NodeStatus) *NodeFSM {
	return &NodeFSM{
		currentState: initialState,
		transitions:  buildNodeTransitions(),
	}
}

// buildNodeTransitions defines all valid node state transitions.
func buildNodeTransitions() map[NodeStatus][]NodeStatus {
	return map[NodeStatus][]NodeStatus{
		NodeStatusPending: {
			NodeStatusRunning,
			NodeStatusSkipped,
		},
		NodeStatusRunning: {
			NodeStatusCompleted,
			NodeStatusFailed,
			NodeStatusRetrying,
		},
		NodeStatusRetrying: {
			NodeStatusRunning,
			NodeStatusFailed,
		},
		// Final states
		NodeStatusCompleted: {},
		NodeStatusFailed:    {},
		NodeStatusSkipped:   {},
	}
}

// CurrentState returns the current state of the node FSM.
func (fsm *NodeFSM) CurrentState() NodeStatus {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.currentState
}

// CanTransition checks if a transition to target state is valid.
func (fsm *NodeFSM) CanTransition(to NodeStatus) bool {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.canTransitionUnsafe(to)
}

func (fsm *NodeFSM) canTransitionUnsafe(to NodeStatus) bool {
	validTargets, exists := fsm.transitions[fsm.currentState]
	if !exists {
		return false
	}
	for _, target := range validTargets {
		if target == to {
			return true
		}
	}
	return false
}

// Transition attempts to transition to a new state.
func (fsm *NodeFSM) Transition(to NodeStatus) error {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()

	if !fsm.canTransitionUnsafe(to) {
		return &InvalidNodeTransitionError{
			From: fsm.currentState,
			To:   to,
		}
	}

	fsm.currentState = to
	return nil
}

// ForceState sets the state without validation.
func (fsm *NodeFSM) ForceState(state NodeStatus) {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()
	fsm.currentState = state
}

// IsFinal returns true if current state is a terminal state.
func (fsm *NodeFSM) IsFinal() bool {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.currentState.IsFinal()
}

// InvalidNodeTransitionError represents an invalid node state transition.
type InvalidNodeTransitionError struct {
	From NodeStatus
	To   NodeStatus
}

func (e *InvalidNodeTransitionError) Error() string {
	return fmt.Sprintf("invalid node transition from %s to %s", e.From, e.To)
}
