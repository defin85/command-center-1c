package statemachine

import (
	"context"
	"fmt"
)

// pushCompensation adds compensation action to stack
func (sm *ExtensionInstallStateMachine) pushCompensation(name string, action func(context.Context) error) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.compensationStack = append(sm.compensationStack, CompensationAction{
		Name:   name,
		Action: action,
	})

	fmt.Printf("[StateMachine] Added compensation: %s\n", name)
}

// executeCompensations executes compensation actions in LIFO order
func (sm *ExtensionInstallStateMachine) executeCompensations(ctx context.Context) error {
	fmt.Printf("[StateMachine] Executing compensations (count=%d)\n", len(sm.compensationStack))

	ctx, cancel := context.WithTimeout(ctx, sm.config.TimeoutCompensation)
	defer cancel()

	// Execute in reverse order (LIFO)
	for i := len(sm.compensationStack) - 1; i >= 0; i-- {
		comp := sm.compensationStack[i]

		fmt.Printf("[StateMachine] Executing compensation: %s\n", comp.Name)

		err := comp.Action(ctx)
		if err != nil {
			fmt.Printf("[StateMachine] Compensation %s failed: %v\n", comp.Name, err)
			// Continue with other compensations даже если одна failed
		} else {
			fmt.Printf("[StateMachine] Compensation %s succeeded\n", comp.Name)
		}
	}

	// All compensations executed, transition to Failed
	return sm.transitionTo(StateFailed)
}
