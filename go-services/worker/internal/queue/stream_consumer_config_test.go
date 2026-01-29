package queue

import (
	"testing"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/processor"
)

func TestNewConsumer_UsesConfigStreamAndGroup(t *testing.T) {
	cfg := &config.Config{
		WorkerID:            "test-worker",
		WorkerStreamName:    "commands:worker:workflows",
		WorkerConsumerGroup: "worker-workflows",
		OrchestratorURL:     "http://example.invalid",
		WorkerAPIKey:        "test",
	}
	redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	proc := processor.NewTaskProcessorWithOptions(cfg, nil, redisClient, processor.ProcessorOptions{})

	consumer, err := NewConsumer(cfg, proc, redisClient, nil)
	assert.NoError(t, err)
	assert.Equal(t, "commands:worker:workflows", consumer.streamName)
	assert.Equal(t, "worker-workflows", consumer.consumerGroup)
}

func TestNewConsumer_DefaultsWhenConfigEmpty(t *testing.T) {
	cfg := &config.Config{
		WorkerID:        "test-worker",
		OrchestratorURL: "http://example.invalid",
		WorkerAPIKey:    "test",
	}
	redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	proc := processor.NewTaskProcessorWithOptions(cfg, nil, redisClient, processor.ProcessorOptions{})

	consumer, err := NewConsumer(cfg, proc, redisClient, nil)
	assert.NoError(t, err)
	assert.Equal(t, StreamCommands, consumer.streamName)
	assert.Equal(t, DefaultConsumerGroupName, consumer.consumerGroup)
}

