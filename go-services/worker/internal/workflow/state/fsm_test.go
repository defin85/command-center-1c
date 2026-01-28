package state

import (
	"sync"
	"testing"
)

func TestWorkflowFSM_ValidTransitions(t *testing.T) {
	tests := []struct {
		name     string
		from     WorkflowStatus
		to       WorkflowStatus
		expected bool
	}{
		// Valid transitions from Pending
		{"Pending to Running", WorkflowStatusPending, WorkflowStatusRunning, true},
		{"Pending to Cancelled", WorkflowStatusPending, WorkflowStatusCancelled, true},
		{"Pending to Completed", WorkflowStatusPending, WorkflowStatusCompleted, false},

		// Valid transitions from Running
		{"Running to Paused", WorkflowStatusRunning, WorkflowStatusPaused, true},
		{"Running to Completed", WorkflowStatusRunning, WorkflowStatusCompleted, true},
		{"Running to Failed", WorkflowStatusRunning, WorkflowStatusFailed, true},
		{"Running to Cancelled", WorkflowStatusRunning, WorkflowStatusCancelled, true},
		{"Running to Compensating", WorkflowStatusRunning, WorkflowStatusCompensating, true},
		{"Running to Pending", WorkflowStatusRunning, WorkflowStatusPending, false},

		// Valid transitions from Paused
		{"Paused to Running", WorkflowStatusPaused, WorkflowStatusRunning, true},
		{"Paused to Cancelled", WorkflowStatusPaused, WorkflowStatusCancelled, true},
		{"Paused to Failed", WorkflowStatusPaused, WorkflowStatusFailed, true},
		{"Paused to Completed", WorkflowStatusPaused, WorkflowStatusCompleted, false},

		// Valid transitions from Compensating
		{"Compensating to Failed", WorkflowStatusCompensating, WorkflowStatusFailed, true},
		{"Compensating to Cancelled", WorkflowStatusCompensating, WorkflowStatusCancelled, true},
		{"Compensating to Running", WorkflowStatusCompensating, WorkflowStatusRunning, false},

		// Final states have no outgoing transitions
		{"Completed to Running", WorkflowStatusCompleted, WorkflowStatusRunning, false},
		{"Failed to Running", WorkflowStatusFailed, WorkflowStatusRunning, false},
		{"Cancelled to Running", WorkflowStatusCancelled, WorkflowStatusRunning, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fsm := NewWorkflowFSM(tt.from)

			canTransition := fsm.CanTransition(tt.to)
			if canTransition != tt.expected {
				t.Errorf("CanTransition(%v -> %v) = %v, want %v",
					tt.from, tt.to, canTransition, tt.expected)
			}

			// Try to transition
			err := fsm.Transition(tt.to)
			if tt.expected {
				if err != nil {
					t.Errorf("Transition(%v -> %v) unexpected error: %v", tt.from, tt.to, err)
				}
				if fsm.CurrentState() != tt.to {
					t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), tt.to)
				}
			} else {
				if err == nil {
					t.Errorf("Transition(%v -> %v) expected error, got nil", tt.from, tt.to)
				}
				if _, ok := err.(*InvalidTransitionError); !ok {
					t.Errorf("Expected InvalidTransitionError, got %T", err)
				}
			}
		})
	}
}

func TestWorkflowFSM_TransitionHooks(t *testing.T) {
	fsm := NewWorkflowFSM(WorkflowStatusPending)

	var hookCalled bool
	var hookFrom, hookTo WorkflowStatus

	fsm.AddHook(func(from, to WorkflowStatus) {
		hookCalled = true
		hookFrom = from
		hookTo = to
	})

	err := fsm.Transition(WorkflowStatusRunning)
	if err != nil {
		t.Fatalf("Transition error: %v", err)
	}

	if !hookCalled {
		t.Error("Hook was not called")
	}
	if hookFrom != WorkflowStatusPending {
		t.Errorf("Hook from = %v, want %v", hookFrom, WorkflowStatusPending)
	}
	if hookTo != WorkflowStatusRunning {
		t.Errorf("Hook to = %v, want %v", hookTo, WorkflowStatusRunning)
	}
}

func TestWorkflowFSM_MultipleHooks(t *testing.T) {
	fsm := NewWorkflowFSM(WorkflowStatusPending)

	callCount := 0
	hook := func(from, to WorkflowStatus) {
		callCount++
	}

	fsm.AddHook(hook)
	fsm.AddHook(hook)
	fsm.AddHook(hook)

	if err := fsm.Transition(WorkflowStatusRunning); err != nil {
		t.Fatalf("Transition error: %v", err)
	}

	if callCount != 3 {
		t.Errorf("Hook call count = %v, want 3", callCount)
	}
}

func TestWorkflowFSM_ForceState(t *testing.T) {
	fsm := NewWorkflowFSM(WorkflowStatusPending)

	// Force invalid transition
	fsm.ForceState(WorkflowStatusCompleted)

	if fsm.CurrentState() != WorkflowStatusCompleted {
		t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), WorkflowStatusCompleted)
	}

	// Should still allow force even from final state
	fsm.ForceState(WorkflowStatusRunning)

	if fsm.CurrentState() != WorkflowStatusRunning {
		t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), WorkflowStatusRunning)
	}
}

func TestWorkflowFSM_ValidTransitions_List(t *testing.T) {
	tests := []struct {
		name          string
		currentState  WorkflowStatus
		expectedCount int
	}{
		{"Pending has 2 valid transitions", WorkflowStatusPending, 2},
		{"Running has 5 valid transitions", WorkflowStatusRunning, 5},
		{"Paused has 3 valid transitions", WorkflowStatusPaused, 3},
		{"Compensating has 2 valid transitions", WorkflowStatusCompensating, 2},
		{"Completed has 0 valid transitions", WorkflowStatusCompleted, 0},
		{"Failed has 0 valid transitions", WorkflowStatusFailed, 0},
		{"Cancelled has 0 valid transitions", WorkflowStatusCancelled, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fsm := NewWorkflowFSM(tt.currentState)
			valid := fsm.ValidTransitions()

			if len(valid) != tt.expectedCount {
				t.Errorf("ValidTransitions() count = %v, want %v", len(valid), tt.expectedCount)
			}
		})
	}
}

func TestWorkflowFSM_IsFinal(t *testing.T) {
	tests := []struct {
		name     string
		state    WorkflowStatus
		expected bool
	}{
		{"Completed is final", WorkflowStatusCompleted, true},
		{"Failed is final", WorkflowStatusFailed, true},
		{"Cancelled is final", WorkflowStatusCancelled, true},
		{"Running is not final", WorkflowStatusRunning, false},
		{"Paused is not final", WorkflowStatusPaused, false},
		{"Pending is not final", WorkflowStatusPending, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fsm := NewWorkflowFSM(tt.state)
			if got := fsm.IsFinal(); got != tt.expected {
				t.Errorf("IsFinal() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestWorkflowFSM_ConcurrentAccess(t *testing.T) {
	fsm := NewWorkflowFSM(WorkflowStatusPending)

	var wg sync.WaitGroup
	iterations := 100

	// Multiple goroutines trying to transition
	wg.Add(iterations)
	for i := 0; i < iterations; i++ {
		go func() {
			defer wg.Done()
			fsm.CanTransition(WorkflowStatusRunning)
			fsm.CurrentState()
			fsm.ValidTransitions()
		}()
	}

	wg.Wait()
	// Should not panic
}

func TestNodeFSM_ValidTransitions(t *testing.T) {
	tests := []struct {
		name     string
		from     NodeStatus
		to       NodeStatus
		expected bool
	}{
		// Valid transitions from Pending
		{"Pending to Running", NodeStatusPending, NodeStatusRunning, true},
		{"Pending to Skipped", NodeStatusPending, NodeStatusSkipped, true},
		{"Pending to Completed", NodeStatusPending, NodeStatusCompleted, false},

		// Valid transitions from Running
		{"Running to Completed", NodeStatusRunning, NodeStatusCompleted, true},
		{"Running to Failed", NodeStatusRunning, NodeStatusFailed, true},
		{"Running to Retrying", NodeStatusRunning, NodeStatusRetrying, true},
		{"Running to Pending", NodeStatusRunning, NodeStatusPending, false},

		// Valid transitions from Retrying
		{"Retrying to Running", NodeStatusRetrying, NodeStatusRunning, true},
		{"Retrying to Failed", NodeStatusRetrying, NodeStatusFailed, true},
		{"Retrying to Completed", NodeStatusRetrying, NodeStatusCompleted, false},

		// Final states
		{"Completed to Running", NodeStatusCompleted, NodeStatusRunning, false},
		{"Failed to Running", NodeStatusFailed, NodeStatusRunning, false},
		{"Skipped to Running", NodeStatusSkipped, NodeStatusRunning, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fsm := NewNodeFSM(tt.from)

			canTransition := fsm.CanTransition(tt.to)
			if canTransition != tt.expected {
				t.Errorf("CanTransition(%v -> %v) = %v, want %v",
					tt.from, tt.to, canTransition, tt.expected)
			}

			err := fsm.Transition(tt.to)
			if tt.expected {
				if err != nil {
					t.Errorf("Transition(%v -> %v) unexpected error: %v", tt.from, tt.to, err)
				}
				if fsm.CurrentState() != tt.to {
					t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), tt.to)
				}
			} else {
				if err == nil {
					t.Errorf("Transition(%v -> %v) expected error, got nil", tt.from, tt.to)
				}
			}
		})
	}
}

func TestNodeFSM_ForceState(t *testing.T) {
	fsm := NewNodeFSM(NodeStatusPending)

	// Force to final state
	fsm.ForceState(NodeStatusCompleted)

	if fsm.CurrentState() != NodeStatusCompleted {
		t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), NodeStatusCompleted)
	}

	// Force back to running (invalid normally)
	fsm.ForceState(NodeStatusRunning)

	if fsm.CurrentState() != NodeStatusRunning {
		t.Errorf("CurrentState() = %v, want %v", fsm.CurrentState(), NodeStatusRunning)
	}
}

func TestNodeFSM_IsFinal(t *testing.T) {
	tests := []struct {
		name     string
		state    NodeStatus
		expected bool
	}{
		{"Completed is final", NodeStatusCompleted, true},
		{"Failed is final", NodeStatusFailed, true},
		{"Skipped is final", NodeStatusSkipped, true},
		{"Running is not final", NodeStatusRunning, false},
		{"Pending is not final", NodeStatusPending, false},
		{"Retrying is not final", NodeStatusRetrying, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fsm := NewNodeFSM(tt.state)
			if got := fsm.IsFinal(); got != tt.expected {
				t.Errorf("IsFinal() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestInvalidTransitionError_Message(t *testing.T) {
	err := &InvalidTransitionError{
		From: WorkflowStatusPending,
		To:   WorkflowStatusCompleted,
	}

	expectedMsg := "invalid transition from pending to completed"
	if err.Error() != expectedMsg {
		t.Errorf("Error() = %v, want %v", err.Error(), expectedMsg)
	}
}

func TestInvalidNodeTransitionError_Message(t *testing.T) {
	err := &InvalidNodeTransitionError{
		From: NodeStatusCompleted,
		To:   NodeStatusRunning,
	}

	expectedMsg := "invalid node transition from completed to running"
	if err.Error() != expectedMsg {
		t.Errorf("Error() = %v, want %v", err.Error(), expectedMsg)
	}
}

func TestWorkflowFSM_SequentialTransitions(t *testing.T) {
	fsm := NewWorkflowFSM(WorkflowStatusPending)

	// Simulate typical workflow lifecycle
	transitions := []WorkflowStatus{
		WorkflowStatusRunning,
		WorkflowStatusPaused,
		WorkflowStatusRunning,
		WorkflowStatusCompleted,
	}

	for i, target := range transitions {
		if err := fsm.Transition(target); err != nil {
			t.Fatalf("Step %d: Transition to %v failed: %v", i, target, err)
		}
		if fsm.CurrentState() != target {
			t.Errorf("Step %d: CurrentState() = %v, want %v", i, fsm.CurrentState(), target)
		}
	}

	// Should not allow further transitions from final state
	err := fsm.Transition(WorkflowStatusRunning)
	if err == nil {
		t.Error("Expected error when transitioning from final state")
	}
}

func TestNodeFSM_RetryWorkflow(t *testing.T) {
	fsm := NewNodeFSM(NodeStatusPending)

	// Normal flow
	if err := fsm.Transition(NodeStatusRunning); err != nil {
		t.Fatalf("Transition to Running failed: %v", err)
	}

	// Failed, then retry
	if err := fsm.Transition(NodeStatusRetrying); err != nil {
		t.Fatalf("Transition to Retrying failed: %v", err)
	}

	// Run again
	if err := fsm.Transition(NodeStatusRunning); err != nil {
		t.Fatalf("Transition to Running after retry failed: %v", err)
	}

	// Finally succeed
	if err := fsm.Transition(NodeStatusCompleted); err != nil {
		t.Fatalf("Transition to Completed failed: %v", err)
	}

	if !fsm.IsFinal() {
		t.Error("Expected final state after completion")
	}
}
