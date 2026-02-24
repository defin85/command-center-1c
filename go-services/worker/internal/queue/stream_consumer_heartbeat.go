package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

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
	log := logger.GetLogger()
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
	opCtx, cancel := context.WithTimeout(ctx, RedisOpTimeout)
	defer cancel()
	if err := c.redis.Set(opCtx, key, data, 30*time.Second).Err(); err != nil {
		if opCtx.Err() != nil {
			log.Warnf("failed to write heartbeat (timeout), worker_id=%s, error=%v", c.workerID, err)
		} else {
			log.Warnf("failed to write heartbeat, worker_id=%s, error=%v", c.workerID, err)
		}
	}
}

// GetStreamDepth returns the current length of the stream
func (c *Consumer) GetStreamDepth(ctx context.Context) int64 {
	log := logger.GetLogger()

	opCtx, cancel := context.WithTimeout(ctx, RedisOpTimeout)
	defer cancel()
	length, err := c.redis.XLen(opCtx, c.streamName).Result()
	if err != nil {
		log.Errorf("failed to get stream length: %v", err)
		return 0
	}
	return length
}

// GetPendingCount returns the number of pending messages for this consumer group
func (c *Consumer) GetPendingCount(ctx context.Context) int64 {
	log := logger.GetLogger()

	opCtx, cancel := context.WithTimeout(ctx, RedisOpTimeout)
	defer cancel()
	pending, err := c.redis.XPending(opCtx, c.streamName, c.consumerGroup).Result()
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
