package progress

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

// Event types
const (
	EventTaskStarted   = "task_started"
	EventTaskProgress  = "task_progress"
	EventTaskCompleted = "task_completed"
	EventTaskFailed    = "task_failed"
)

// ProgressEvent represents a progress event structure
type ProgressEvent struct {
	Event           string                 `json:"event"`
	TaskID          string                 `json:"task_id"`
	DatabaseID      int                    `json:"database_id"`
	DatabaseName    string                 `json:"database_name,omitempty"`
	Status          string                 `json:"status"`
	DurationSeconds int                    `json:"duration_seconds,omitempty"`
	Timestamp       string                 `json:"timestamp"`
	ErrorMessage    string                 `json:"error_message,omitempty"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

// Publisher handles publishing installation progress to Redis pub/sub
type Publisher struct {
	client  *redis.Client
	channel string
}

// NewPublisher creates a new progress publisher
func NewPublisher(cfg *config.RedisConfig) *Publisher {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		Password: cfg.Password,
		DB:       cfg.DB,
	})

	return &Publisher{
		client:  client,
		channel: cfg.ProgressChannel,
	}
}

// PublishTaskStarted publishes task_started event
func (p *Publisher) PublishTaskStarted(ctx context.Context, task executor.Task) error {
	event := ProgressEvent{
		Event:        EventTaskStarted,
		TaskID:       task.TaskID,
		DatabaseID:   task.DatabaseID,
		DatabaseName: task.DatabaseName,
		Status:       "in_progress",
		Timestamp:    time.Now().Format(time.RFC3339),
	}

	return p.publish(ctx, event)
}

// PublishTaskProgress publishes task_progress event
func (p *Publisher) PublishTaskProgress(ctx context.Context, task executor.Task, percentage int) error {
	event := ProgressEvent{
		Event:        EventTaskProgress,
		TaskID:       task.TaskID,
		DatabaseID:   task.DatabaseID,
		DatabaseName: task.DatabaseName,
		Status:       "in_progress",
		Timestamp:    time.Now().Format(time.RFC3339),
		Metadata: map[string]interface{}{
			"percentage": percentage,
		},
	}

	return p.publish(ctx, event)
}

// PublishTaskCompleted publishes task_completed event
func (p *Publisher) PublishTaskCompleted(ctx context.Context, result executor.TaskResult) error {
	event := ProgressEvent{
		Event:           EventTaskCompleted,
		TaskID:          result.TaskID,
		DatabaseID:      result.DatabaseID,
		DatabaseName:    result.DatabaseName,
		Status:          "success",
		DurationSeconds: result.DurationSeconds,
		Timestamp:       time.Now().Format(time.RFC3339),
	}

	return p.publish(ctx, event)
}

// PublishTaskFailed publishes task_failed event
func (p *Publisher) PublishTaskFailed(ctx context.Context, result executor.TaskResult) error {
	event := ProgressEvent{
		Event:           EventTaskFailed,
		TaskID:          result.TaskID,
		DatabaseID:      result.DatabaseID,
		DatabaseName:    result.DatabaseName,
		Status:          "failed",
		DurationSeconds: result.DurationSeconds,
		ErrorMessage:    result.ErrorMessage,
		Timestamp:       time.Now().Format(time.RFC3339),
	}

	return p.publish(ctx, event)
}

// publish sends event to Redis pub/sub channel
func (p *Publisher) publish(ctx context.Context, event ProgressEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		log.Error().Err(err).Msg("Failed to marshal progress event")
		return err
	}

	// Publish to channel
	if err := p.client.Publish(ctx, p.channel, data).Err(); err != nil {
		log.Error().
			Err(err).
			Str("channel", p.channel).
			Str("event", event.Event).
			Msg("Failed to publish progress event")
		return err
	}

	log.Debug().
		Str("event", event.Event).
		Str("task_id", event.TaskID).
		Int("database_id", event.DatabaseID).
		Msg("Progress event published")

	return nil
}

// Close closes the Redis connection
func (p *Publisher) Close() error {
	return p.client.Close()
}

// Ping checks Redis connection
func (p *Publisher) Ping(ctx context.Context) error {
	return p.client.Ping(ctx).Err()
}
