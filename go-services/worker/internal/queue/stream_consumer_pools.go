package queue

import (
	"context"
	"fmt"
	"strings"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/models"
)

const (
	defaultSchedulingPoolKey       = "shared|default|default"
	defaultSchedulingPoolSize      = 1
	defaultMaxSchedulingPoolGroups = 128
)

// dispatchMessage schedules message processing in bounded concurrent mode.
func (c *Consumer) dispatchMessage(ctx context.Context, message redis.XMessage) bool {
	if c == nil {
		return false
	}
	if c.dispatchSlots == nil {
		c.processMessage(ctx, message)
		return true
	}

	select {
	case c.dispatchSlots <- struct{}{}:
	case <-ctx.Done():
		return false
	}

	c.inflightWG.Add(1)
	go func(msg redis.XMessage) {
		defer c.inflightWG.Done()
		defer func() {
			<-c.dispatchSlots
		}()
		c.processMessage(ctx, msg)
	}(message)

	return true
}

func (c *Consumer) acquireSchedulingPoolSlot(
	ctx context.Context,
	msg *models.OperationMessage,
) (release func(), poolKey string, ok bool) {
	key := resolveSchedulingPoolKey(msg)
	pool := c.ensureSchedulingPool(key)

	select {
	case pool <- struct{}{}:
		return func() {
			<-pool
		}, key, true
	case <-ctx.Done():
		return nil, key, false
	}
}

func (c *Consumer) ensureSchedulingPool(poolKey string) chan struct{} {
	key := strings.TrimSpace(poolKey)
	if key == "" {
		key = defaultSchedulingPoolKey
	}

	c.schedulingPoolsMu.Lock()
	defer c.schedulingPoolsMu.Unlock()

	if c.schedulingPools == nil {
		c.schedulingPools = map[string]chan struct{}{}
	}

	defaultPool := c.schedulingPools[defaultSchedulingPoolKey]
	if defaultPool == nil {
		defaultPool = make(chan struct{}, defaultSchedulingPoolSize)
		c.schedulingPools[defaultSchedulingPoolKey] = defaultPool
	}

	if pool, exists := c.schedulingPools[key]; exists {
		return pool
	}

	maxPools := c.maxSchedulingPoolGroups
	if maxPools <= 0 {
		maxPools = defaultMaxSchedulingPoolGroups
	}
	if len(c.schedulingPools) >= maxPools {
		return defaultPool
	}

	poolSize := c.perSchedulingPoolSize
	if poolSize <= 0 {
		poolSize = defaultSchedulingPoolSize
	}

	pool := make(chan struct{}, poolSize)
	c.schedulingPools[key] = pool
	return pool
}

func resolveSchedulingPoolKey(msg *models.OperationMessage) string {
	if msg == nil {
		return defaultSchedulingPoolKey
	}

	affinity := normalizeSchedulingToken(msg.Metadata.ServerAffinity)
	if affinity == "" {
		affinity = normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "server_affinity"))
	}

	role := normalizeSchedulingToken(msg.Metadata.Role)
	if role == "" {
		role = normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "role"))
	}

	priority := normalizeSchedulingToken(msg.Metadata.Priority)
	if priority == "" {
		priority = normalizeSchedulingToken(msg.ExecConfig.Priority)
	}
	if priority == "" {
		priority = normalizeSchedulingToken(readMessagePayloadToken(msg.Payload.Data, "priority"))
	}

	if affinity == "" && role == "" && priority == "" {
		return defaultSchedulingPoolKey
	}
	if affinity == "" {
		affinity = "shared"
	}
	if role == "" {
		role = "default"
	}
	if priority == "" {
		priority = "default"
	}

	return fmt.Sprintf("%s|%s|%s", affinity, role, priority)
}

func readMessagePayloadToken(data map[string]interface{}, key string) string {
	if len(data) == 0 {
		return ""
	}
	raw, exists := data[key]
	if !exists {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(raw))
}

func normalizeSchedulingToken(value string) string {
	token := strings.TrimSpace(strings.ToLower(value))
	if token == "" {
		return ""
	}
	return token
}

func (c *Consumer) readBatchSize() int64 {
	if c == nil || cap(c.dispatchSlots) <= 0 {
		return 1
	}
	size := cap(c.dispatchSlots)
	if size > 100 {
		size = 100
	}
	return int64(size)
}
