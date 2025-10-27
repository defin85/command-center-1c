package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/rs/zerolog/log"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/executor"
)

// Consumer handles Redis queue consumption
type Consumer struct {
	client *redis.Client
	config *config.RedisConfig
}

// NewConsumer creates a new Redis queue consumer
func NewConsumer(cfg *config.RedisConfig) *Consumer {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		Password: cfg.Password,
		DB:       cfg.DB,
	})

	return &Consumer{
		client: client,
		config: cfg,
	}
}

// Start begins consuming messages from Redis queue
func (c *Consumer) Start(ctx context.Context, taskChan chan<- executor.Task) error {
	log.Info().
		Str("queue", c.config.Queue).
		Str("redis_host", c.config.Host).
		Int("redis_port", c.config.Port).
		Msg("Starting Redis queue consumer")

	// Test connection first
	if err := c.client.Ping(ctx).Err(); err != nil {
		log.Error().Err(err).Msg("Failed to connect to Redis")
		return fmt.Errorf("redis connection failed: %w", err)
	}

	log.Info().Msg("Successfully connected to Redis")

	for {
		select {
		case <-ctx.Done():
			log.Info().Msg("Stopping queue consumer")
			return ctx.Err()
		default:
			// BRPOP (blocking right pop) - waits for new tasks
			// Timeout of 5 seconds to allow periodic context checks
			result, err := c.client.BRPop(ctx, 5*time.Second, c.config.Queue).Result()
			if err == redis.Nil {
				// Timeout, continue loop to check context
				continue
			}
			if err != nil {
				log.Error().Err(err).Msg("Error reading from queue")
				time.Sleep(time.Duration(c.config.RetryDelay) * time.Second)
				continue
			}

			// result[0] - queue name, result[1] - data
			var task executor.Task
			if err := json.Unmarshal([]byte(result[1]), &task); err != nil {
				log.Error().
					Err(err).
					Str("data", result[1]).
					Msg("Error parsing task JSON")
				continue
			}

			log.Info().
				Str("task_id", task.TaskID).
				Int("database_id", task.DatabaseID).
				Str("database_name", task.DatabaseName).
				Msg("Received task from queue")

			// Send to worker pool for processing
			select {
			case taskChan <- task:
				log.Debug().
					Str("task_id", task.TaskID).
					Msg("Task sent to worker pool")
			case <-ctx.Done():
				return ctx.Err()
			}
		}
	}
}

// Close closes the Redis client connection
func (c *Consumer) Close() error {
	log.Info().Msg("Closing Redis connection")
	return c.client.Close()
}

// HealthCheck performs a health check on the Redis connection
func (c *Consumer) HealthCheck(ctx context.Context) error {
	return c.client.Ping(ctx).Err()
}
