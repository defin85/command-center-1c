package eventhandlers

import (
	"context"
	"fmt"
	"time"

	"go.uber.org/zap"
)

const (
	// IdempotencyTTL is the TTL for idempotency keys in Redis
	IdempotencyTTL = 10 * time.Minute
)

// CheckIdempotency checks if an operation has already been processed using Redis SetNX
// Returns (isFirst, error) where isFirst=true means this is the first time processing
func CheckIdempotency(ctx context.Context, redisClient RedisClient, correlationID, operation string, logger *zap.Logger) (bool, error) {
	// Skip idempotency check if no correlationID
	if correlationID == "" {
		logger.Warn("empty correlation ID, skipping idempotency check")
		return true, nil
	}

	// Skip if Redis client not configured
	if redisClient == nil {
		logger.Debug("Redis client not configured, skipping idempotency check",
			zap.String("correlation_id", correlationID))
		return true, nil
	}

	key := fmt.Sprintf("idempotency:%s:%s", operation, correlationID)

	result := redisClient.SetNX(ctx, key, "processed", IdempotencyTTL)
	if result.Err() != nil {
		logger.Warn("idempotency check failed (Redis error), allowing operation to proceed (fail-open)",
			zap.String("correlation_id", correlationID),
			zap.String("operation", operation),
			zap.Error(result.Err()))
		return true, nil // Fail-open: allow operation
	}

	isFirst, err := result.Result()
	if err != nil {
		logger.Warn("failed to get SetNX result, allowing operation (fail-open)",
			zap.String("correlation_id", correlationID),
			zap.Error(err))
		return true, nil
	}

	return isFirst, nil
}
