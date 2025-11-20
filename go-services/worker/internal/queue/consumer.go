// go-services/worker/internal/queue/consumer.go
package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
)

type Consumer struct {
	redis        *redis.Client
	processor    *processor.TaskProcessor
	workerID     string
	queueName    string
	resultsQueue string
}

// NewConsumer creates a new Redis queue consumer
func NewConsumer(cfg *config.Config, processor *processor.TaskProcessor, redisClient *redis.Client) (*Consumer, error) {
	// Use provided redis client instead of creating new one
	return &Consumer{
		redis:        redisClient,
		processor:    processor,
		workerID:     cfg.WorkerID,
		queueName:    "cc1c:operations:v1",
		resultsQueue: "cc1c:operations:results:v1",
	}, nil
}

// Start starts the consumer main loop
func (c *Consumer) Start(ctx context.Context) error {
	log := logger.GetLogger()
	log.Infof("worker started, worker_id=%s, queue=%s", c.workerID, c.queueName)

	// Start heartbeat goroutine
	go c.heartbeatLoop(ctx)

	// Main processing loop
	for {
		select {
		case <-ctx.Done():
			log.Infof("worker shutting down, worker_id=%s", c.workerID)
			return ctx.Err()

		default:
			// Blocking pop (5 second timeout)
			result, err := c.redis.BRPop(ctx, 5*time.Second, c.queueName).Result()
			if err == redis.Nil {
				// No task available, continue
				continue
			}
			if err != nil {
				log.Errorf("failed to dequeue task: %v", err)
				time.Sleep(1 * time.Second) // Backoff on error
				continue
			}

			if len(result) < 2 {
				log.Error("invalid queue response")
				continue
			}

			// Parse message
			var msg models.OperationMessage
			if err := json.Unmarshal([]byte(result[1]), &msg); err != nil {
				log.Errorf("failed to parse message: %v, raw_message=%s", err, result[1])
				continue
			}

			// Validate message
			if err := msg.Validate(); err != nil {
				log.Errorf("invalid message: %v, operation_id=%s", err, msg.OperationID)
				continue
			}

			// Process task
			c.processTask(ctx, &msg)
		}
	}
}

func (c *Consumer) processTask(ctx context.Context, msg *models.OperationMessage) {
	log := logger.GetLogger()

	log.Infof("processing task, operation_id=%s, worker_id=%s, type=%s, databases=%d",
		msg.OperationID, c.workerID, msg.OperationType, len(msg.TargetDatabases))

	// Idempotency check
	lockKey := fmt.Sprintf("cc1c:task:%s:lock", msg.OperationID)
	exists := c.redis.Exists(ctx, lockKey).Val()
	if exists == 0 {
		log.Warnf("task lock not found, skipping (likely duplicate or cancelled), operation_id=%s", msg.OperationID)
		return
	}

	// Task timeout context
	taskCtx, cancel := context.WithTimeout(ctx,
		time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
	defer cancel()

	// Execute operation
	result := c.processor.Process(taskCtx, msg)

	// Publish result
	if err := c.publishResult(ctx, result); err != nil {
		log.Errorf("failed to publish result: %v", err)
		// TODO: Retry or DLQ
	}

	// Extend lock on success
	if result.Status == "completed" {
		c.redis.Expire(ctx, lockKey, 24*time.Hour)
	}

	log.Infof("task processing completed, status=%s, succeeded=%d, failed=%d",
		result.Status, result.Summary.Succeeded, result.Summary.Failed)
}

func (c *Consumer) publishResult(ctx context.Context, result *models.OperationResultV2) error {
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	return c.redis.LPush(ctx, c.resultsQueue, data).Err()
}

func (c *Consumer) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.sendHeartbeat(ctx)
		}
	}
}

func (c *Consumer) sendHeartbeat(ctx context.Context) {
	key := fmt.Sprintf("cc1c:worker:%s:heartbeat", c.workerID)
	metadata := map[string]interface{}{
		"worker_id":      c.workerID,
		"status":         "alive",
		"last_heartbeat": time.Now().Format(time.RFC3339),
	}

	data, _ := json.Marshal(metadata)
	c.redis.Set(ctx, key, data, 30*time.Second) // TTL 30 seconds
}

// Close closes the Redis connection
func (c *Consumer) Close() error {
	return c.redis.Close()
}
