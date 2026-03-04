package queue

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAcquireOrRecoverTaskLock_TakesOverStaleOwnerWithoutHeartbeat(t *testing.T) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	client := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = client.Close() })

	consumer := &Consumer{
		redis:    client,
		workerID: "worker-new",
	}
	ctx := context.Background()
	lockKey := "cc1c:task:op-1:lock"

	require.NoError(t, client.Set(ctx, lockKey, "worker-old", time.Hour).Err())

	acquired, activeOwner, err := consumer.acquireOrRecoverTaskLock(ctx, "op-1")
	require.NoError(t, err)
	assert.True(t, acquired)
	assert.Equal(t, "", activeOwner)

	currentOwner, err := client.Get(ctx, lockKey).Result()
	require.NoError(t, err)
	assert.Equal(t, "worker-new", currentOwner)
}

func TestAcquireOrRecoverTaskLock_ReturnsActiveOwnerWhenHeartbeatExists(t *testing.T) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	client := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = client.Close() })

	consumer := &Consumer{
		redis:    client,
		workerID: "worker-new",
	}
	ctx := context.Background()
	lockKey := "cc1c:task:op-2:lock"
	owner := "worker-old"

	require.NoError(t, client.Set(ctx, lockKey, owner, time.Hour).Err())
	heartbeatKey := fmt.Sprintf("cc1c:worker:%s:heartbeat", owner)
	require.NoError(t, client.Set(ctx, heartbeatKey, "alive", 30*time.Second).Err())

	acquired, activeOwner, err := consumer.acquireOrRecoverTaskLock(ctx, "op-2")
	require.NoError(t, err)
	assert.False(t, acquired)
	assert.Equal(t, owner, activeOwner)

	currentOwner, err := client.Get(ctx, lockKey).Result()
	require.NoError(t, err)
	assert.Equal(t, owner, currentOwner)
}
