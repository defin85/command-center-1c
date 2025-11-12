package events_test

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
)

func TestRedisHealthCheck_Healthy(t *testing.T) {
	client := createTestRedisClient(t)
	defer client.Close()

	err := events.RedisHealthCheck(context.Background(), client)
	assert.NoError(t, err)
}

func TestRedisHealthCheck_Unhealthy(t *testing.T) {
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:9999", // Non-existent Redis
	})
	defer client.Close()

	err := events.RedisHealthCheck(context.Background(), client)
	assert.Error(t, err)
}

func TestWaitForRedis_Success(t *testing.T) {
	client := createTestRedisClient(t)
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := events.WaitForRedis(ctx, client, 3, 100*time.Millisecond)
	assert.NoError(t, err)
}

func TestWaitForRedis_MaxRetries(t *testing.T) {
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:9999", // Non-existent Redis
	})
	defer client.Close()

	ctx := context.Background()
	err := events.WaitForRedis(ctx, client, 3, 10*time.Millisecond)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to connect to Redis after 3 retries")
}

func TestWaitForRedis_ContextCanceled(t *testing.T) {
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:9999", // Non-existent Redis
	})
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	err := events.WaitForRedis(ctx, client, 0, 100*time.Millisecond) // Infinite retries
	assert.Error(t, err)
	assert.ErrorIs(t, err, context.DeadlineExceeded)
}
