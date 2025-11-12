package statemachine

import (
	"context"
	"fmt"
)

// markEventProcessedInRedis marks event as processed in Redis
func (sm *ExtensionInstallStateMachine) markEventProcessedInRedis(ctx context.Context, messageID string) error {
	key := fmt.Sprintf("workflow:%s:event:%s", sm.CorrelationID, messageID)

	err := sm.redisClient.Set(ctx, key, "1", sm.config.DeduplicationTTL).Err()
	if err != nil {
		return fmt.Errorf("failed to mark event as processed: %w", err)
	}

	return nil
}

// isEventProcessedInRedis checks if event was processed in Redis
func (sm *ExtensionInstallStateMachine) isEventProcessedInRedis(ctx context.Context, messageID string) (bool, error) {
	key := fmt.Sprintf("workflow:%s:event:%s", sm.CorrelationID, messageID)

	exists, err := sm.redisClient.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check event deduplication: %w", err)
	}

	return exists > 0, nil
}
