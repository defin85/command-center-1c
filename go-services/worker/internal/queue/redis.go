package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/redis/go-redis/v9"
)

const (
	TaskQueueKey    = "commandcenter:tasks:pending"
	ResultQueueKey  = "commandcenter:tasks:results"
	TaskKeyPrefix   = "commandcenter:task:"
)

// RedisQueue handles task queue operations
type RedisQueue struct {
	client *redis.Client
	ctx    context.Context
}

// NewRedisQueue creates a new Redis queue client
func NewRedisQueue(ctx context.Context, cfg *config.Config) (*RedisQueue, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	// Test connection
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &RedisQueue{
		client: client,
		ctx:    ctx,
	}, nil
}

// DequeueTask retrieves a task from the queue (blocking)
func (q *RedisQueue) DequeueTask(ctx context.Context, timeout time.Duration) (*models.Operation, error) {
	// BRPOP blocks until a task is available or timeout
	result, err := q.client.BRPop(ctx, timeout, TaskQueueKey).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil // No task available
		}
		return nil, fmt.Errorf("failed to dequeue task: %w", err)
	}

	if len(result) < 2 {
		return nil, fmt.Errorf("invalid queue response")
	}

	// Parse task data
	var operation models.Operation
	if err := json.Unmarshal([]byte(result[1]), &operation); err != nil {
		return nil, fmt.Errorf("failed to parse task: %w", err)
	}

	return &operation, nil
}

// PublishResult publishes task result
func (q *RedisQueue) PublishResult(ctx context.Context, result *models.OperationResult) error {
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	if err := q.client.LPush(ctx, ResultQueueKey, data).Err(); err != nil {
		return fmt.Errorf("failed to publish result: %w", err)
	}

	return nil
}

// UpdateTaskStatus updates task status in Redis
func (q *RedisQueue) UpdateTaskStatus(ctx context.Context, taskID string, status models.OperationStatus) error {
	key := fmt.Sprintf("%s%s:status", TaskKeyPrefix, taskID)
	if err := q.client.Set(ctx, key, string(status), 24*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to update task status: %w", err)
	}
	return nil
}

// GetQueueDepth returns the number of pending tasks
func (q *RedisQueue) GetQueueDepth(ctx context.Context) (int64, error) {
	return q.client.LLen(ctx, TaskQueueKey).Result()
}

// Close closes the Redis connection
func (q *RedisQueue) Close() error {
	return q.client.Close()
}
