// go-services/worker/internal/queue/stream_consumer.go
package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
)

// Stream constants
const (
	// StreamCommands is the Redis Stream for incoming commands
	StreamCommands = "commands:worker:operations"

	// StreamResultsCompleted is the Redis Stream for successful results
	StreamResultsCompleted = "events:worker:completed"

	// StreamResultsFailed is the Redis Stream for failed results
	StreamResultsFailed = "events:worker:failed"

	// StreamDLQ is the Dead Letter Queue for unprocessable messages
	StreamDLQ = "commands:worker:dlq"

	// ConsumerGroupName is the default consumer group name
	ConsumerGroupName = "worker-group"

	// ClaimIdleThreshold is the time after which a pending message can be claimed
	ClaimIdleThreshold = 5 * time.Minute

	// ClaimCheckInterval is how often to check for stalled messages
	ClaimCheckInterval = 30 * time.Second

	// MaxPendingToCheck is the maximum number of pending messages to check
	MaxPendingToCheck = 100

	// ServiceName for event envelopes
	ServiceName = "go-worker"
)

// Consumer consumes messages from Redis Streams using XREADGROUP
type Consumer struct {
	redis         *redis.Client
	processor     *processor.TaskProcessor
	workerID      string
	streamName    string
	consumerGroup string
	consumerName  string
	resultsStream string
}

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

// NewConsumer creates a new Redis Streams consumer
func NewConsumer(cfg *config.Config, proc *processor.TaskProcessor, redisClient *redis.Client) (*Consumer, error) {
	if redisClient == nil {
		return nil, fmt.Errorf("redis client is required")
	}
	if proc == nil {
		return nil, fmt.Errorf("processor is required")
	}

	consumerName := fmt.Sprintf("worker-%s", cfg.WorkerID)

	return &Consumer{
		redis:         redisClient,
		processor:     proc,
		workerID:      cfg.WorkerID,
		streamName:    StreamCommands,
		consumerGroup: ConsumerGroupName,
		consumerName:  consumerName,
		resultsStream: StreamResultsCompleted,
	}, nil
}

// EnsureConsumerGroup creates the consumer group if it doesn't exist
func (c *Consumer) EnsureConsumerGroup(ctx context.Context) error {
	log := logger.GetLogger()

	// Create consumer group starting from the end of the stream ("$")
	// This means we only process new messages, not historical ones
	err := c.redis.XGroupCreateMkStream(ctx, c.streamName, c.consumerGroup, "$").Err()
	if err != nil {
		// BUSYGROUP means the group already exists - this is fine
		if err.Error() == "BUSYGROUP Consumer Group name already exists" {
			log.Infof("consumer group already exists, stream=%s, group=%s", c.streamName, c.consumerGroup)
			return nil
		}
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	log.Infof("created consumer group, stream=%s, group=%s", c.streamName, c.consumerGroup)
	return nil
}

// Start begins consuming messages from the stream
func (c *Consumer) Start(ctx context.Context) error {
	log := logger.GetLogger()

	// Ensure consumer group exists
	if err := c.EnsureConsumerGroup(ctx); err != nil {
		return err
	}

	log.Infof("stream consumer started, worker_id=%s, stream=%s, group=%s, consumer=%s",
		c.workerID, c.streamName, c.consumerGroup, c.consumerName)

	// Start heartbeat goroutine
	go c.heartbeatLoop(ctx)

	// Start stalled message claimer goroutine
	go c.claimStalledMessages(ctx)

	// Main processing loop
	for {
		select {
		case <-ctx.Done():
			log.Infof("stream consumer shutting down, worker_id=%s", c.workerID)
			return ctx.Err()

		default:
			// Read messages from stream with consumer group
			// Using ">" means read only messages that were never delivered to any consumer
			streams, err := c.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    c.consumerGroup,
				Consumer: c.consumerName,
				Streams:  []string{c.streamName, ">"},
				Count:    1,
				Block:    5 * time.Second,
			}).Result()

			if err == redis.Nil {
				// No messages available, continue
				continue
			}
			if err != nil {
				log.Errorf("failed to read from stream: %v", err)
				time.Sleep(1 * time.Second) // Backoff on error
				continue
			}

			// Process received messages
			for _, stream := range streams {
				for _, message := range stream.Messages {
					c.processMessage(ctx, message)
				}
			}
		}
	}
}

// processMessage handles a single message from the stream
func (c *Consumer) processMessage(ctx context.Context, message redis.XMessage) {
	log := logger.GetLogger()
	messageID := message.ID

	log.Infof("received message, message_id=%s", messageID)

	// Extract fallback IDs BEFORE parsing envelope (Error Feedback Phase 1)
	// This allows error reporting even if envelope parsing fails
	fallback := extractFallbackIDs(message)

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

	log.Infof("processing operation, operation_id=%s, type=%s, databases=%d",
		msg.OperationID, msg.OperationType, len(msg.TargetDatabases))

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
		// Key already exists - task is being processed or was processed
		log.Warnf("task already being processed, skipping: operation_id=%s", msg.OperationID)
		c.ackMessage(ctx, messageID)
		return
	}

	// Task timeout context
	taskCtx, cancel := context.WithTimeout(ctx,
		time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
	defer cancel()

	// Execute operation
	result := c.processor.Process(taskCtx, &msg)

	// Publish result to appropriate stream BEFORE ACK (FIX #1)
	var publishSuccess bool
	if result.Status == "completed" {
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
		publishSuccess = c.publishCompletedResult(ctx, result, envelope.CorrelationID)
	} else {
		publishSuccess = c.publishFailedResult(ctx, result.OperationID, envelope.CorrelationID, messageID, getErrorSummary(result))
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

// ackMessage acknowledges a message in the stream
func (c *Consumer) ackMessage(ctx context.Context, messageID string) {
	log := logger.GetLogger()

	err := c.redis.XAck(ctx, c.streamName, c.consumerGroup, messageID).Err()
	if err != nil {
		log.Errorf("failed to ACK message, message_id=%s, error=%v", messageID, err)
	}
}

// claimStalledMessages periodically checks for and claims stalled messages
func (c *Consumer) claimStalledMessages(ctx context.Context) {
	log := logger.GetLogger()
	ticker := time.NewTicker(ClaimCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Infof("stalled message claimer stopped, worker_id=%s", c.workerID)
			return
		case <-ticker.C:
			c.checkAndClaimPending(ctx)
		}
	}
}

// checkAndClaimPending checks for pending messages and claims stalled ones
func (c *Consumer) checkAndClaimPending(ctx context.Context) {
	log := logger.GetLogger()

	// Get pending messages summary
	pending, err := c.redis.XPending(ctx, c.streamName, c.consumerGroup).Result()
	if err != nil {
		log.Errorf("failed to get pending summary: %v", err)
		return
	}

	if pending.Count == 0 {
		return
	}

	log.Debugf("checking pending messages, count=%d, stream=%s", pending.Count, c.streamName)

	// Get detailed pending messages
	pendingExt, err := c.redis.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: c.streamName,
		Group:  c.consumerGroup,
		Start:  "-",
		End:    "+",
		Count:  MaxPendingToCheck,
	}).Result()
	if err != nil {
		log.Errorf("failed to get pending messages detail: %v", err)
		return
	}

	// Claim stalled messages
	for _, pendingMsg := range pendingExt {
		// Skip messages that haven't been idle long enough
		if pendingMsg.Idle < ClaimIdleThreshold {
			continue
		}

		// Skip messages owned by this consumer (we're already processing them)
		if pendingMsg.Consumer == c.consumerName {
			continue
		}

		log.Infof("claiming stalled message, message_id=%s, idle=%v, owner=%s",
			pendingMsg.ID, pendingMsg.Idle, pendingMsg.Consumer)

		// Claim the message
		messages, err := c.redis.XClaim(ctx, &redis.XClaimArgs{
			Stream:   c.streamName,
			Group:    c.consumerGroup,
			Consumer: c.consumerName,
			MinIdle:  ClaimIdleThreshold,
			Messages: []string{pendingMsg.ID},
		}).Result()
		if err != nil {
			log.Errorf("failed to claim message %s: %v", pendingMsg.ID, err)
			continue
		}

		// Process claimed messages
		for _, msg := range messages {
			log.Infof("processing claimed message, message_id=%s", msg.ID)
			c.processMessage(ctx, msg)
		}
	}
}

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

// heartbeatLoop sends periodic heartbeats
func (c *Consumer) heartbeatLoop(ctx context.Context) {
	log := logger.GetLogger()
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Infof("heartbeat loop stopped, worker_id=%s", c.workerID)
			return
		case <-ticker.C:
			c.sendHeartbeat(ctx)
		}
	}
}

// sendHeartbeat sends a heartbeat to Redis
func (c *Consumer) sendHeartbeat(ctx context.Context) {
	key := fmt.Sprintf("cc1c:worker:%s:heartbeat", c.workerID)
	metadata := map[string]interface{}{
		"worker_id":      c.workerID,
		"status":         "alive",
		"consumer":       c.consumerName,
		"stream":         c.streamName,
		"consumer_group": c.consumerGroup,
		"last_heartbeat": time.Now().Format(time.RFC3339),
	}

	data, _ := json.Marshal(metadata)
	c.redis.Set(ctx, key, data, 30*time.Second)
}

// GetStreamDepth returns the current length of the stream
func (c *Consumer) GetStreamDepth(ctx context.Context) int64 {
	log := logger.GetLogger()

	length, err := c.redis.XLen(ctx, c.streamName).Result()
	if err != nil {
		log.Errorf("failed to get stream length: %v", err)
		return 0
	}
	return length
}

// GetPendingCount returns the number of pending messages for this consumer group
func (c *Consumer) GetPendingCount(ctx context.Context) int64 {
	log := logger.GetLogger()

	pending, err := c.redis.XPending(ctx, c.streamName, c.consumerGroup).Result()
	if err != nil {
		log.Errorf("failed to get pending count: %v", err)
		return 0
	}
	return pending.Count
}

// Close gracefully closes the consumer
func (c *Consumer) Close() error {
	// Redis client is shared, don't close it here
	return nil
}

// getErrorSummary extracts error summary from OperationResultV2
func getErrorSummary(result *models.OperationResultV2) string {
	if result.Status == "completed" {
		return ""
	}

	// Collect errors from failed results
	var errorMsgs []string
	for _, dbResult := range result.Results {
		if !dbResult.Success && dbResult.Error != "" {
			errorMsgs = append(errorMsgs, fmt.Sprintf("%s: %s", dbResult.DatabaseID, dbResult.Error))
		}
	}

	if len(errorMsgs) == 0 {
		return fmt.Sprintf("operation %s failed", result.OperationID)
	}

	if len(errorMsgs) == 1 {
		return errorMsgs[0]
	}

	return fmt.Sprintf("%d errors: %s", len(errorMsgs), errorMsgs[0])
}
