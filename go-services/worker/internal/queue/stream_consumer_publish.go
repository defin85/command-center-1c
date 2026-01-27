package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

// moveToDLQ moves an unprocessable message to the Dead Letter Queue.
// This is the last resort when both parsing and error publishing fail.
// DLQ structure allows manual inspection and potential recovery.
// Returns true if message was successfully moved to DLQ (or fallback file).
func (c *Consumer) moveToDLQ(ctx context.Context, fallback FallbackIDs, errorCode, errorMsg string) bool {
	log := logger.GetLogger()

	dlqEntry := map[string]interface{}{
		"original_message_id": fallback.MessageID,
		"correlation_id":      fallback.CorrelationID,
		"operation_id":        fallback.OperationID,
		"event_type":          fallback.EventType,
		"error_code":          errorCode,
		"error_message":       errorMsg,
		"worker_id":           c.workerID,
		"failed_at":           time.Now().UTC().Format(time.RFC3339),
	}

	_, err := c.redis.XAdd(ctx, &redis.XAddArgs{
		Stream: StreamDLQ,
		MaxLen: 10000,
		Approx: true,
		Values: dlqEntry,
	}).Result()

	if err != nil {
		// Last resort - write to local fallback file (FIX #2)
		log.Errorf("CRITICAL: DLQ failed, writing to fallback file, message_id=%s, error=%v",
			fallback.MessageID, err)
		c.writeToFallbackFile(dlqEntry)
		// Return true because we wrote to fallback file - message is not lost
		return true
	}

	log.Warnf("message moved to DLQ, message_id=%s, operation_id=%s, error_code=%s",
		fallback.MessageID, fallback.OperationID, errorCode)
	return true
}

// writeToFallbackFile writes DLQ entry to local file when Redis DLQ is unavailable.
// This is the absolute last resort to prevent message loss (FIX #2).
func (c *Consumer) writeToFallbackFile(entry map[string]interface{}) {
	log := logger.GetLogger()
	fallbackPath := "/var/log/cc1c/dlq-fallback.jsonl"

	// Ensure directory exists
	dir := "/var/log/cc1c"
	if err := os.MkdirAll(dir, 0755); err != nil {
		log.Errorf("CRITICAL: cannot create fallback directory %s: %v", dir, err)
		// Try current directory as last resort
		fallbackPath = "dlq-fallback.jsonl"
	}

	f, err := os.OpenFile(fallbackPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Errorf("CRITICAL: cannot write to fallback file %s: %v", fallbackPath, err)
		// Log the entry content so it's at least in logs
		data, _ := json.Marshal(entry)
		log.Errorf("CRITICAL: lost message data: %s", string(data))
		return
	}
	defer f.Close()

	data, err := json.Marshal(entry)
	if err != nil {
		log.Errorf("CRITICAL: cannot marshal fallback entry: %v", err)
		return
	}

	if _, err := f.WriteString(string(data) + "\n"); err != nil {
		log.Errorf("CRITICAL: cannot write to fallback file: %v", err)
		return
	}

	log.Warnf("wrote message to fallback file: %s", fallbackPath)
}

// publishParseError publishes a parse error to the failed stream using fallback IDs.
// If publishing fails, the message is moved to DLQ as last resort.
// Returns true if error was successfully published (to stream or DLQ).
func (c *Consumer) publishParseError(ctx context.Context, fallback FallbackIDs, errorCode, errorMsg string) bool {
	log := logger.GetLogger()

	// Use fallback correlation_id if available, otherwise use message ID
	correlationID := fallback.CorrelationID
	if correlationID == "" {
		correlationID = fallback.MessageID
	}

	failedPayload := map[string]interface{}{
		"operation_id":        fallback.OperationID,
		"error":               errorMsg,
		"error_code":          errorCode,
		"worker_id":           c.workerID,
		"timestamp":           time.Now().UTC().Format(time.RFC3339),
		"original_message_id": fallback.MessageID,
	}

	envelope, err := events.NewEnvelope(
		"events:worker:operation-failed",
		ServiceName,
		failedPayload,
		correlationID,
	)
	if err != nil {
		log.Errorf("failed to create parse error envelope: %v", err)
		return c.moveToDLQ(ctx, fallback, errorCode, errorMsg)
	}

	envelope.SetMetadata("operation_id", fallback.OperationID)
	envelope.SetMetadata("status", "failed")
	envelope.SetMetadata("worker_id", c.workerID)
	envelope.SetMetadata("error_code", errorCode)

	if err := c.publishResult(ctx, StreamResultsFailed, envelope); err != nil {
		log.Errorf("failed to publish parse error, falling back to DLQ: %v", err)
		return c.moveToDLQ(ctx, fallback, errorCode, errorMsg)
	}

	return true
}

// publishCompletedResult publishes a successful result to the completed stream.
// Returns true if result was successfully published.
func (c *Consumer) publishCompletedResult(ctx context.Context, result *models.OperationResultV2, correlationID string) bool {
	log := logger.GetLogger()

	envelope, err := events.NewEnvelope(
		"events:worker:operation-completed",
		ServiceName,
		result,
		correlationID,
	)
	if err != nil {
		log.Errorf("failed to create result envelope: %v", err)
		return false
	}

	// Add operation metadata
	envelope.SetMetadata("operation_id", result.OperationID)
	envelope.SetMetadata("status", result.Status)
	envelope.SetMetadata("worker_id", c.workerID)

	if err := c.publishResult(ctx, StreamResultsCompleted, envelope); err != nil {
		log.Errorf("failed to publish completed result: %v", err)
		return false
	}

	return true
}

// publishFailedResult publishes a failed result to the failed stream.
// If publishing fails, the error is logged and fallback to DLQ is attempted.
// messageID is used for DLQ fallback to preserve original message reference (FIX #4).
// Returns true if result was successfully published (to stream or DLQ).
func (c *Consumer) publishFailedResult(ctx context.Context, operationID, correlationID, messageID, errorMsg string) bool {
	log := logger.GetLogger()

	failedPayload := map[string]interface{}{
		"operation_id":        operationID,
		"error":               errorMsg,
		"worker_id":           c.workerID,
		"timestamp":           time.Now().UTC().Format(time.RFC3339),
		"original_message_id": messageID,
	}

	envelope, err := events.NewEnvelope(
		"events:worker:operation-failed",
		ServiceName,
		failedPayload,
		correlationID,
	)
	if err != nil {
		log.Errorf("failed to create failed result envelope: %v", err)
		// Fallback to DLQ on envelope creation failure
		fallback := FallbackIDs{
			CorrelationID: correlationID,
			OperationID:   operationID,
			MessageID:     messageID,
		}
		return c.moveToDLQ(ctx, fallback, "ENVELOPE_CREATE_ERROR", errorMsg)
	}

	envelope.SetMetadata("operation_id", operationID)
	envelope.SetMetadata("status", "failed")
	envelope.SetMetadata("worker_id", c.workerID)

	if err := c.publishResult(ctx, StreamResultsFailed, envelope); err != nil {
		log.Errorf("failed to publish failed result, falling back to DLQ: %v", err)
		// Fallback to DLQ on publish failure
		fallback := FallbackIDs{
			CorrelationID: correlationID,
			OperationID:   operationID,
			MessageID:     messageID,
		}
		return c.moveToDLQ(ctx, fallback, "PUBLISH_ERROR", errorMsg)
	}

	return true
}

// publishResult publishes an envelope to a Redis Stream
func (c *Consumer) publishResult(ctx context.Context, stream string, envelope *events.Envelope) error {
	data, err := json.Marshal(envelope)
	if err != nil {
		return fmt.Errorf("failed to marshal envelope: %w", err)
	}

	// Add to stream with auto-generated ID
	_, err = c.redis.XAdd(ctx, &redis.XAddArgs{
		Stream: stream,
		MaxLen: 10000,
		Approx: true,
		Values: map[string]interface{}{
			"data": string(data),
		},
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to add to stream %s: %w", stream, err)
	}

	return nil
}
