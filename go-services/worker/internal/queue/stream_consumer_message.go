package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

// FallbackIDs contains IDs extracted from message fields for error recovery.
// These fields are duplicated outside the envelope by Django to allow
// error reporting even when envelope parsing fails (Error Feedback Phase 1).
type FallbackIDs struct {
	CorrelationID string
	OperationID   string
	EventType     string
	MessageID     string
}

// extractFallbackIDs extracts fallback IDs from message fields.
// Returns FallbackIDs with MessageID always set, other fields may be empty
// for backward compatibility with old messages without fallback fields.
func extractFallbackIDs(message redis.XMessage) FallbackIDs {
	ids := FallbackIDs{MessageID: message.ID}

	if v, ok := message.Values["correlation_id"].(string); ok && v != "" {
		ids.CorrelationID = v
	}
	if v, ok := message.Values["operation_id"].(string); ok && v != "" {
		ids.OperationID = v
	}
	if v, ok := message.Values["event_type"].(string); ok && v != "" {
		ids.EventType = v
	}

	return ids
}

// processMessage handles a single message from the stream
func (c *Consumer) processMessage(ctx context.Context, message redis.XMessage) {
	log := logger.GetLogger()
	messageID := message.ID

	log.Infof("received message, message_id=%s", messageID)

	// Extract fallback IDs BEFORE parsing envelope (Error Feedback Phase 1)
	// This allows error reporting even if envelope parsing fails
	fallback := extractFallbackIDs(message)

	// Record message received in timeline IMMEDIATELY after getting messageID (FIX #4)
	// Use fallback operation_id which may be empty for old messages (backward compatible)
	c.timeline.Record(ctx, fallback.OperationID, "message.received", map[string]interface{}{
		"message_id": messageID,
		"worker_id":  c.workerID,
	})

	// Extract envelope data from message values
	envelopeData, ok := message.Values["data"].(string)
	if !ok {
		log.Errorf("invalid message format, missing 'data' field, message_id=%s", messageID)
		// ACK only after successful publish or DLQ write (FIX #1)
		if c.publishParseError(ctx, fallback, "INVALID_FORMAT", "missing 'data' field in message") {
			c.ackMessage(ctx, messageID)
		}
		return
	}

	// Parse envelope
	var envelope events.Envelope
	if err := json.Unmarshal([]byte(envelopeData), &envelope); err != nil {
		log.Errorf("failed to parse envelope, message_id=%s, error=%v", messageID, err)
		// ACK only after successful publish or DLQ write (FIX #1)
		if c.publishParseError(ctx, fallback, "ENVELOPE_PARSE_ERROR", fmt.Sprintf("failed to parse envelope: %v", err)) {
			c.ackMessage(ctx, messageID)
		}
		return
	}

	// Validate envelope
	if err := envelope.Validate(); err != nil {
		log.Errorf("invalid envelope, message_id=%s, error=%v", messageID, err)
		// ACK only after successful publish or DLQ write (FIX #1)
		if c.publishParseError(ctx, fallback, "ENVELOPE_VALIDATION_ERROR", fmt.Sprintf("invalid envelope: %v", err)) {
			c.ackMessage(ctx, messageID)
		}
		return
	}

	// Update fallback with envelope data (for better error reporting later)
	if fallback.CorrelationID == "" {
		fallback.CorrelationID = envelope.CorrelationID
	}

	// Parse operation message from payload
	var msg models.OperationMessage
	if err := json.Unmarshal(envelope.Payload, &msg); err != nil {
		log.Errorf("failed to parse operation message, message_id=%s, error=%v", messageID, err)
		// ACK only after successful publish or DLQ write (FIX #1)
		// Use fallback.OperationID which may be set from message fields (FIX #5)
		if c.publishFailedResult(ctx, fallback.OperationID, envelope.CorrelationID, messageID, fmt.Sprintf("invalid payload: %v", err)) {
			c.ackMessage(ctx, messageID)
		}
		return
	}

	// Validate operation message
	if err := msg.Validate(); err != nil {
		log.Errorf("invalid operation message, message_id=%s, error=%v", messageID, err)
		// ACK only after successful publish or DLQ write (FIX #1)
		// Use fallback.OperationID if msg.OperationID is empty (FIX #5)
		opID := msg.OperationID
		if opID == "" {
			opID = fallback.OperationID
		}
		if c.publishFailedResult(ctx, opID, envelope.CorrelationID, messageID, fmt.Sprintf("validation error: %v", err)) {
			c.ackMessage(ctx, messageID)
		}
		return
	}

	releaseSchedulingPoolSlot, schedulingPoolKey, acquired := c.acquireSchedulingPoolSlot(ctx, &msg)
	if !acquired {
		log.Warnf(
			"failed to acquire scheduling pool slot, operation_id=%s, message_id=%s, pool=%s",
			msg.OperationID,
			messageID,
			schedulingPoolKey,
		)
		return
	}
	defer releaseSchedulingPoolSlot()

	fairness := c.buildFairnessProfile(&msg, messageID)
	recordFairnessOldestTaskAgeMetric(fairness)
	releaseFairnessGuards, fairnessAcquired := c.acquireFairnessGuards(ctx, fairness)
	if !fairnessAcquired {
		log.Warnf(
			"failed to acquire fairness guards, operation_id=%s, message_id=%s, role=%s, affinity=%s",
			msg.OperationID,
			messageID,
			fairness.role,
			fairness.affinity,
		)
		return
	}
	defer releaseFairnessGuards()

	log.Infof(
		"processing operation, operation_id=%s, type=%s, databases=%d, role=%s, server_affinity=%s, scheduling_pool=%s, tenant=%s, age_seconds=%.1f, promoted=%t",
		msg.OperationID,
		msg.OperationType,
		len(msg.TargetDatabases),
		msg.Metadata.Role,
		msg.Metadata.ServerAffinity,
		schedulingPoolKey,
		fairness.tenant,
		fairness.age.Seconds(),
		fairness.promoted,
	)

	// Atomic idempotency check with SetNX (FIX #8)
	// SetNX returns true if key was set (new task), false if already exists
	lockKey := fmt.Sprintf("cc1c:task:%s:lock", msg.OperationID)
	acquired, err := c.redis.SetNX(ctx, lockKey, c.workerID, 1*time.Hour).Result()
	if err != nil {
		log.Errorf("idempotency check failed: %v, operation_id=%s", err, msg.OperationID)
		// Don't ACK - will be retried
		return
	}
	if !acquired {
		// Key already exists - check if it's our own lock (after restart)
		lockOwner, err := c.redis.Get(ctx, lockKey).Result()
		if err != nil {
			log.Errorf("failed to get lock owner: %v, operation_id=%s", err, msg.OperationID)
			c.ackMessage(ctx, messageID)
			return
		}
		if lockOwner == c.workerID {
			// Our own lock from previous run (restart recovery)
			log.Infof("recovering own lock after restart, operation_id=%s", msg.OperationID)
			// Refresh TTL since we're taking over
			c.redis.Expire(ctx, lockKey, 1*time.Hour)
		} else {
			// Another worker is processing this task
			log.Warnf("task already being processed by %s, skipping: operation_id=%s", lockOwner, msg.OperationID)
			c.ackMessage(ctx, messageID)
			return
		}
	}

	// Task timeout context
	taskCtx, cancel := context.WithTimeout(ctx,
		time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
	defer cancel()

	// Execute operation
	result := c.processor.Process(taskCtx, &msg)

	// Publish result BEFORE ACK (FIX #1).
	//
	// IMPORTANT: Always publish the full OperationResultV2 to the "completed" stream,
	// even when result.Status is "failed" or "timeout". Otherwise, Orchestrator only
	// receives a summarized error in events:worker:failed and loses per-database
	// results (stdout/stderr/exit_code), making troubleshooting impossible.
	var publishSuccess bool
	if result.Status != "completed" {
		// Record failed status before publishing (failed path is less critical)
		c.timeline.Record(ctx, msg.OperationID, "message.failed", map[string]interface{}{
			"message_id": messageID,
			"status":     result.Status,
			"error":      getErrorSummary(result),
		})
	}

	// Always publish the full result; Orchestrator decides final BatchOperation status from payload.status.
	publishSuccess = c.publishCompletedResult(ctx, result, envelope.CorrelationID)

	// Preserve previous semantics: extend lock only for successful (completed) operations.
	if publishSuccess && result.Status == "completed" {
		// FIX MINOR #2: Extend lock only if we still own it (atomic check-and-extend)
		// Prevents overwriting lock if another worker took over after we crashed/timed out
		extendScript := redis.NewScript(`
			if redis.call("get", KEYS[1]) == ARGV[1] then
				return redis.call("expire", KEYS[1], ARGV[2])
			end
			return 0
		`)
		extendResult, err := extendScript.Run(ctx, c.redis, []string{lockKey}, c.workerID, int(24*time.Hour.Seconds())).Int()
		if err != nil {
			log.Errorf("failed to extend lock for %s: %v", msg.OperationID, err)
		} else if extendResult == 0 {
			log.Warnf("lock for %s was taken by another worker, skipping extend", msg.OperationID)
		}
	}

	// Record message.completed in timeline AFTER successful publish (FIX #5)
	if publishSuccess && result.Status == "completed" {
		c.timeline.Record(ctx, msg.OperationID, "message.completed", map[string]interface{}{
			"message_id": messageID,
			"status":     result.Status,
		})
	}

	// FIX MINOR #2: Verify lock ownership before ACK
	// If lock was taken by another worker, log warning but still ACK to avoid reprocessing
	lockOwner, err := c.redis.Get(ctx, lockKey).Result()
	if err != nil && err != redis.Nil {
		log.Errorf("failed to check lock owner before ACK: %v", err)
	} else if lockOwner != "" && lockOwner != c.workerID {
		log.Warnf("lock owner changed for %s: expected=%s, actual=%s (ACK will proceed)",
			msg.OperationID, c.workerID, lockOwner)
	}

	// ACK message only after successful publish (FIX #1)
	if publishSuccess {
		c.ackMessage(ctx, messageID)
	}

	log.Infof("message processed, message_id=%s, operation_id=%s, status=%s, published=%v",
		messageID, msg.OperationID, result.Status, publishSuccess)
}
