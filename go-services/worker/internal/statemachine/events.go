package statemachine

import (
	"context"
	"fmt"
)

// publishCommand publishes a command event
func (sm *ExtensionInstallStateMachine) publishCommand(
	ctx context.Context,
	channel string,
	eventType string,
	payload interface{},
) error {

	err := sm.publisher.Publish(ctx, channel, eventType, payload, sm.CorrelationID)
	if err != nil {
		return fmt.Errorf("failed to publish command %s: %w", eventType, err)
	}

	fmt.Printf("[StateMachine] Published command: %s (correlation_id=%s)\n",
		eventType, sm.CorrelationID)

	return nil
}
