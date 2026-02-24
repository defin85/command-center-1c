// go-services/worker/internal/queue/stream_consumer.go
package queue

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
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

	// DefaultConsumerGroupName is the default consumer group name
	// (kept in sync with shared/config default for WORKER_CONSUMER_GROUP)
	DefaultConsumerGroupName = "worker-state-machine"

	// ClaimIdleThreshold is the time after which a pending message can be claimed
	ClaimIdleThreshold = 5 * time.Minute

	// ClaimCheckInterval is how often to check for stalled messages
	ClaimCheckInterval = 30 * time.Second

	// MaxPendingToCheck is the maximum number of pending messages to check
	MaxPendingToCheck = 100

	// ReadBlockTimeout is the Redis STREAMS blocking read duration.
	ReadBlockTimeout = 5 * time.Second

	// ReadCallTimeout bounds the full read call to avoid rare stuck reads.
	ReadCallTimeout = 8 * time.Second

	// RedisOpTimeout bounds auxiliary Redis operations (ACK, heartbeat, pending checks).
	RedisOpTimeout = 3 * time.Second

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
	timeline      tracing.TimelineRecorder
}

// NewConsumer creates a new Redis Streams consumer
func NewConsumer(cfg *config.Config, proc *processor.TaskProcessor, redisClient *redis.Client, timeline tracing.TimelineRecorder) (*Consumer, error) {
	if redisClient == nil {
		return nil, fmt.Errorf("redis client is required")
	}
	if proc == nil {
		return nil, fmt.Errorf("processor is required")
	}

	// Use noop timeline if not provided
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}

	streamName := cfg.WorkerStreamName
	if streamName == "" {
		streamName = StreamCommands
	}

	consumerGroup := cfg.WorkerConsumerGroup
	if consumerGroup == "" {
		consumerGroup = DefaultConsumerGroupName
	}

	consumerName := fmt.Sprintf("worker-%s", cfg.WorkerID)

	return &Consumer{
		redis:         redisClient,
		processor:     proc,
		workerID:      cfg.WorkerID,
		streamName:    streamName,
		consumerGroup: consumerGroup,
		consumerName:  consumerName,
		resultsStream: StreamResultsCompleted,
		timeline:      timeline,
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

	consecutiveReadTimeouts := 0

	// Main processing loop
	for {
		select {
		case <-ctx.Done():
			log.Infof("stream consumer shutting down, worker_id=%s", c.workerID)
			return ctx.Err()

		default:
			readCtx, cancel := context.WithTimeout(ctx, ReadCallTimeout)

			// Read messages from stream with consumer group
			// Using ">" means read only messages that were never delivered to any consumer
			streams, err := c.redis.XReadGroup(readCtx, &redis.XReadGroupArgs{
				Group:    c.consumerGroup,
				Consumer: c.consumerName,
				Streams:  []string{c.streamName, ">"},
				Count:    1,
				Block:    ReadBlockTimeout,
			}).Result()
			cancel()

			if err == redis.Nil {
				// No messages available, continue
				consecutiveReadTimeouts = 0
				continue
			}
			if err != nil {
				if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
					if ctx.Err() != nil {
						return ctx.Err()
					}
					consecutiveReadTimeouts++
					// Keep logs low-noise: once per minute with current defaults.
					if consecutiveReadTimeouts%12 == 0 {
						log.Warnf(
							"stream read timeout watchdog triggered, worker_id=%s, stream=%s, group=%s, consumer=%s, consecutive_timeouts=%d",
							c.workerID,
							c.streamName,
							c.consumerGroup,
							c.consumerName,
							consecutiveReadTimeouts,
						)
					}
					continue
				}

				consecutiveReadTimeouts = 0
				log.Errorf("failed to read from stream: %v", err)
				time.Sleep(1 * time.Second) // Backoff on error
				continue
			}
			consecutiveReadTimeouts = 0

			// Process received messages
			for _, stream := range streams {
				for _, message := range stream.Messages {
					c.processMessage(ctx, message)
				}
			}
		}
	}
}
