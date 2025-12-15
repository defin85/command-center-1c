package tracing

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// getTestRedisClient creates a Redis client for testing.
// Uses localhost:6379 by default.
func getTestRedisClient() *redis.Client {
	return redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   15, // Use DB 15 for tests to avoid conflicts
	})
}

// cleanupTestKey removes test keys from Redis.
func cleanupTestKey(client *redis.Client, operationID string) {
	ctx := context.Background()
	client.Del(ctx, timelineKey(operationID))
}

func TestRedisTimeline_Record(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-record-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record an event
	timeline.Record(ctx, operationID, "task.started", map[string]interface{}{
		"task_type": "sync",
	})

	// Wait for async operation to complete
	timeline.Wait()

	// Verify the event was recorded
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)
	require.Len(t, entries, 1)

	assert.Equal(t, "task.started", entries[0].Event)
	assert.Equal(t, "test-service", entries[0].Service)
	assert.Equal(t, "sync", entries[0].Metadata["task_type"])
	assert.WithinDuration(t, time.Now(), entries[0].Timestamp, 5*time.Second)
}

func TestRedisTimeline_GetTimeline(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-timeline-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record multiple events with small delays
	events := []string{"step1", "step2", "step3"}
	for _, event := range events {
		timeline.Record(ctx, operationID, event, nil)
		timeline.Wait()
		time.Sleep(10 * time.Millisecond) // Ensure different timestamps
	}

	// Get timeline and verify order
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)
	require.Len(t, entries, 3)

	// Events should be sorted by timestamp (oldest first)
	assert.Equal(t, "step1", entries[0].Event)
	assert.Equal(t, "step2", entries[1].Event)
	assert.Equal(t, "step3", entries[2].Event)

	// Timestamps should be in ascending order
	assert.True(t, entries[0].Timestamp.Before(entries[1].Timestamp) ||
		entries[0].Timestamp.Equal(entries[1].Timestamp))
	assert.True(t, entries[1].Timestamp.Before(entries[2].Timestamp) ||
		entries[1].Timestamp.Equal(entries[2].Timestamp))
}

func TestRedisTimeline_TTL(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-ttl-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	ttl := 30 * time.Second
	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         ttl,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record an event
	timeline.Record(ctx, operationID, "test.event", nil)
	timeline.Wait()

	// Check TTL was set
	key := timelineKey(operationID)
	actualTTL, err := client.TTL(ctx, key).Result()
	require.NoError(t, err)

	// TTL should be close to configured value (within 5 seconds)
	assert.True(t, actualTTL > 0, "TTL should be positive")
	assert.True(t, actualTTL <= ttl, "TTL should not exceed configured value")
	assert.True(t, actualTTL > ttl-5*time.Second, "TTL should be close to configured value")
}

func TestRedisTimeline_MaxEntries(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-max-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	maxEntries := 5
	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  maxEntries,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record more events than MaxEntries
	for i := 0; i < maxEntries+3; i++ {
		timeline.Record(ctx, operationID, "event", map[string]interface{}{
			"index": string(rune('A' + i)),
		})
		timeline.Wait()
		time.Sleep(5 * time.Millisecond) // Ensure different timestamps
	}

	// Get timeline
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)

	// Should have at most MaxEntries events
	assert.LessOrEqual(t, len(entries), maxEntries)

	// Oldest events should have been trimmed (newest kept)
	// The last entries should have the highest indices
	if len(entries) == maxEntries {
		// Check that we have the newest entries (indices D, E, F, G, H for maxEntries=5, total=8)
		lastEntry := entries[len(entries)-1]
		assert.Equal(t, "H", lastEntry.Metadata["index"]) // Last recorded
	}
}

func TestRedisTimeline_Disabled(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	cfg := TimelineConfig{
		Enabled:     false,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg)

	// Should return NoopTimeline when disabled
	_, isNoop := timeline.(*NoopTimeline)
	assert.True(t, isNoop, "Should return NoopTimeline when disabled")

	// Record should not fail
	timeline.Record(ctx, "op-123", "test.event", nil)

	// GetTimeline should return empty list
	entries, err := timeline.GetTimeline(ctx, "op-123")
	require.NoError(t, err)
	assert.Empty(t, entries)
}

func TestNoopTimeline(t *testing.T) {
	ctx := context.Background()

	timeline := NewNoopTimeline()

	// Record should not panic
	timeline.Record(ctx, "op-123", "test.event", map[string]interface{}{"key": "value"})

	// GetTimeline should return empty list without error
	entries, err := timeline.GetTimeline(ctx, "op-123")
	require.NoError(t, err)
	assert.Empty(t, entries)

	// Multiple Record calls should not panic
	for i := 0; i < 100; i++ {
		timeline.Record(ctx, "op-123", "test.event", nil)
	}

	// GetTimeline for non-existent operation should still work
	entries, err = timeline.GetTimeline(ctx, "non-existent")
	require.NoError(t, err)
	assert.Empty(t, entries)
}

func TestRedisTimeline_EmptyOperationID(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record with empty operation ID should be silently ignored
	timeline.Record(ctx, "", "test.event", nil)
	timeline.Wait()

	// GetTimeline with empty operation ID should return error
	_, err := timeline.GetTimeline(ctx, "")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "operation ID is required")
}

func TestRedisTimeline_EmptyEvent(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-empty-event-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record with empty event should be silently ignored
	timeline.Record(ctx, operationID, "", nil)
	timeline.Wait()

	// Timeline should be empty
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)
	assert.Empty(t, entries)
}

func TestDefaultTimelineConfig(t *testing.T) {
	cfg := DefaultTimelineConfig("my-service")

	assert.True(t, cfg.Enabled)
	assert.Equal(t, 24*time.Hour, cfg.TTL)
	assert.Equal(t, "my-service", cfg.ServiceName)
	assert.Equal(t, 1000, cfg.MaxEntries)
}

func TestRedisTimeline_DefaultValues(t *testing.T) {
	client := getTestRedisClient()

	// Config with zero values
	cfg := TimelineConfig{
		Enabled:     true,
		ServiceName: "test-service",
		// TTL and MaxEntries are zero - should use defaults
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Check defaults were applied
	assert.Equal(t, 24*time.Hour, timeline.cfg.TTL)
	assert.Equal(t, 1000, timeline.cfg.MaxEntries)
}

func TestRedisTimeline_NilMetadata(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-nil-meta-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record with nil metadata
	timeline.Record(ctx, operationID, "test.event", nil)
	timeline.Wait()

	// Get timeline
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)
	require.Len(t, entries, 1)

	assert.Equal(t, "test.event", entries[0].Event)
	assert.Nil(t, entries[0].Metadata)
}

func TestRedisTimeline_ConcurrentRecords(t *testing.T) {
	client := getTestRedisClient()
	ctx := context.Background()

	// Check if Redis is available
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	operationID := "test-op-concurrent-" + time.Now().Format("20060102150405")
	defer cleanupTestKey(client, operationID)

	cfg := TimelineConfig{
		Enabled:     true,
		TTL:         1 * time.Hour,
		ServiceName: "test-service",
		MaxEntries:  100,
	}

	timeline := NewRedisTimeline(client, cfg).(*RedisTimeline)

	// Record multiple events concurrently
	numEvents := 20
	for i := 0; i < numEvents; i++ {
		timeline.Record(ctx, operationID, "concurrent.event", map[string]interface{}{
			"index": string(rune('A' + i)),
		})
	}

	// Wait for all records to complete
	timeline.Wait()

	// All events should be recorded
	entries, err := timeline.GetTimeline(ctx, operationID)
	require.NoError(t, err)
	assert.Len(t, entries, numEvents)
}
