package queue

import (
	"testing"
	"time"

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
	assert.Equal(t, defaultOldestAgeThreshold, consumer.oldestAgeThreshold)
	assert.Equal(t, defaultTenantBudgetShare, consumer.tenantBudgetShare)
	assert.Equal(t, defaultTenantBudgetBackoff, consumer.tenantBudgetBackoff)
}

func TestNewConsumer_AppliesFairnessSettingsFromConfig(t *testing.T) {
	cfg := &config.Config{
		WorkerID:                          "test-worker",
		WorkerPoolSize:                    6,
		WorkerFairnessOldestAgeThreshold:  45 * time.Second,
		WorkerFairnessManualReserveSlots:  3,
		WorkerFairnessTenantBudgetShare:   0.25,
		WorkerFairnessTenantBudgetBackoff: 75 * time.Millisecond,
		OrchestratorURL:                   "http://example.invalid",
		WorkerAPIKey:                      "test",
	}
	redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	proc := processor.NewTaskProcessorWithOptions(cfg, nil, redisClient, processor.ProcessorOptions{})

	consumer, err := NewConsumer(cfg, proc, redisClient, nil)
	assert.NoError(t, err)
	assert.Equal(t, 45*time.Second, consumer.oldestAgeThreshold)
	assert.Equal(t, 0.25, consumer.tenantBudgetShare)
	assert.Equal(t, 75*time.Millisecond, consumer.tenantBudgetBackoff)
	if assert.NotNil(t, consumer.manualReserveSlots) {
		assert.Equal(t, 3, cap(consumer.manualReserveSlots))
	}
	assert.Equal(t, 3, cap(consumer.generalWorkerSlots))
}

func TestNewConsumer_ClampsManualReserveSlotsToLeaveGeneralCapacity(t *testing.T) {
	cfg := &config.Config{
		WorkerID:                         "test-worker",
		WorkerPoolSize:                   2,
		WorkerFairnessManualReserveSlots: 10,
		OrchestratorURL:                  "http://example.invalid",
		WorkerAPIKey:                     "test",
	}
	redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	proc := processor.NewTaskProcessorWithOptions(cfg, nil, redisClient, processor.ProcessorOptions{})

	consumer, err := NewConsumer(cfg, proc, redisClient, nil)
	assert.NoError(t, err)
	if assert.NotNil(t, consumer.manualReserveSlots) {
		assert.Equal(t, 1, cap(consumer.manualReserveSlots))
	}
	assert.Equal(t, 1, cap(consumer.generalWorkerSlots))
}
