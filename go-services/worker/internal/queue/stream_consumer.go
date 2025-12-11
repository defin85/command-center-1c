// go-services/worker/internal/queue/stream_consumer.go
package queue

import (
	"context"
	"encoding/json"
	"fmt"
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

	// Extract envelope data from message values
	envelopeData, ok := message.Values["data"].(string)
	if !ok {
		log.Errorf("invalid message format, missing 'data' field, message_id=%s", messageID)
		// ACK to prevent redelivery of malformed messages
		c.ackMessage(ctx, messageID)
		return
	}

	// Parse envelope
	var envelope events.Envelope
	if err := json.Unmarshal([]byte(envelopeData), &envelope); err != nil {
		log.Errorf("failed to parse envelope, message_id=%s, error=%v", messageID, err)
		c.ackMessage(ctx, messageID)
		return
	}

	// Validate envelope
	if err := envelope.Validate(); err != nil {
		log.Errorf("invalid envelope, message_id=%s, error=%v", messageID, err)
		c.ackMessage(ctx, messageID)
		return
	}

	// Parse operation message from payload
	var msg models.OperationMessage
	if err := json.Unmarshal(envelope.Payload, &msg); err != nil {
		log.Errorf("failed to parse operation message, message_id=%s, error=%v", messageID, err)
		c.ackMessage(ctx, messageID)
		c.publishFailedResult(ctx, "", envelope.CorrelationID, fmt.Sprintf("invalid payload: %v", err))
		return
	}

	// Validate operation message
	if err := msg.Validate(); err != nil {
		log.Errorf("invalid operation message, message_id=%s, error=%v", messageID, err)
		c.ackMessage(ctx, messageID)
		c.publishFailedResult(ctx, msg.OperationID, envelope.CorrelationID, fmt.Sprintf("validation error: %v", err))
		return
	}

	log.Infof("processing operation, operation_id=%s, type=%s, databases=%d",
		msg.OperationID, msg.OperationType, len(msg.TargetDatabases))

	// Idempotency check
	lockKey := fmt.Sprintf("cc1c:task:%s:lock", msg.OperationID)
	exists := c.redis.Exists(ctx, lockKey).Val()
	if exists == 0 {
		log.Warnf("task lock not found, skipping (likely duplicate or cancelled), operation_id=%s", msg.OperationID)
		c.ackMessage(ctx, messageID)
		return
	}

	// Task timeout context
	taskCtx, cancel := context.WithTimeout(ctx,
		time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
	defer cancel()

	// Execute operation
	result := c.processor.Process(taskCtx, &msg)

	// ACK message after successful processing
	c.ackMessage(ctx, messageID)

	// Publish result to appropriate stream
	if result.Status == "completed" {
		// Extend lock on success
		c.redis.Expire(ctx, lockKey, 24*time.Hour)
		c.publishCompletedResult(ctx, result, envelope.CorrelationID)
	} else {
		c.publishFailedResult(ctx, result.OperationID, envelope.CorrelationID, getErrorSummary(result))
	}

	log.Infof("message processed, message_id=%s, operation_id=%s, status=%s",
		messageID, msg.OperationID, result.Status)
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

// publishCompletedResult publishes a successful result to the completed stream
func (c *Consumer) publishCompletedResult(ctx context.Context, result *models.OperationResultV2, correlationID string) {
	log := logger.GetLogger()

	envelope, err := events.NewEnvelope(
		"events:worker:operation-completed",
		ServiceName,
		result,
		correlationID,
	)
	if err != nil {
		log.Errorf("failed to create result envelope: %v", err)
		return
	}

	// Add operation metadata
	envelope.SetMetadata("operation_id", result.OperationID)
	envelope.SetMetadata("status", result.Status)
	envelope.SetMetadata("worker_id", c.workerID)

	if err := c.publishResult(ctx, StreamResultsCompleted, envelope); err != nil {
		log.Errorf("failed to publish completed result: %v", err)
	}
}

// publishFailedResult publishes a failed result to the failed stream
func (c *Consumer) publishFailedResult(ctx context.Context, operationID, correlationID, errorMsg string) {
	log := logger.GetLogger()

	failedPayload := map[string]interface{}{
		"operation_id": operationID,
		"error":        errorMsg,
		"worker_id":    c.workerID,
		"timestamp":    time.Now().UTC().Format(time.RFC3339),
	}

	envelope, err := events.NewEnvelope(
		"events:worker:operation-failed",
		ServiceName,
		failedPayload,
		correlationID,
	)
	if err != nil {
		log.Errorf("failed to create failed result envelope: %v", err)
		return
	}

	envelope.SetMetadata("operation_id", operationID)
	envelope.SetMetadata("status", "failed")
	envelope.SetMetadata("worker_id", c.workerID)

	if err := c.publishResult(ctx, StreamResultsFailed, envelope); err != nil {
		log.Errorf("failed to publish failed result: %v", err)
	}
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
