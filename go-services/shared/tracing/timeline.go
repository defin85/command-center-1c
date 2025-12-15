package tracing

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/redis/go-redis/v9"
	"github.com/sirupsen/logrus"
)

var (
	// timelineErrorsTotal counts timeline recording errors by service and error type
	timelineErrorsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_timeline_errors_total",
			Help: "Total timeline recording errors",
		},
		[]string{"service", "error_type"},
	)
)

func init() {
	prometheus.MustRegister(timelineErrorsTotal)
}

// TimelineRecorder defines the interface for recording operation timeline events.
type TimelineRecorder interface {
	// Record adds a timeline event for an operation (async, non-blocking)
	// Metadata supports any JSON-serializable values (strings, numbers, bools, etc.)
	Record(ctx context.Context, operationID, event string, metadata map[string]interface{})

	// GetTimeline returns all events for an operation, sorted by timestamp
	GetTimeline(ctx context.Context, operationID string) ([]TimelineEntry, error)
}

// TimelineEntry represents a single event in an operation's timeline.
type TimelineEntry struct {
	Timestamp time.Time              `json:"timestamp"`
	Event     string                 `json:"event"`
	Service   string                 `json:"service"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// timelineEntryStorage is the internal representation stored in Redis.
type timelineEntryStorage struct {
	Event    string                 `json:"event"`
	Service  string                 `json:"service"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// TimelineConfig holds configuration for the timeline recorder.
type TimelineConfig struct {
	Enabled     bool          // Feature flag (default: true)
	TTL         time.Duration // TTL for timeline data (default: 24h)
	ServiceName string        // Service name for events
	MaxEntries  int           // Max events per operation (default: 1000)
}

// DefaultTimelineConfig returns a TimelineConfig with default values.
func DefaultTimelineConfig(serviceName string) TimelineConfig {
	return TimelineConfig{
		Enabled:     true,
		TTL:         24 * time.Hour,
		ServiceName: serviceName,
		MaxEntries:  1000,
	}
}

// RedisTimeline implements TimelineRecorder using Redis ZSET.
type RedisTimeline struct {
	client *redis.Client
	cfg    TimelineConfig
	logger *logrus.Logger
	wg     sync.WaitGroup
}

// NewRedisTimeline creates a new RedisTimeline instance.
// If timeline is disabled in config, returns NoopTimeline instead.
func NewRedisTimeline(client *redis.Client, cfg TimelineConfig) TimelineRecorder {
	if !cfg.Enabled {
		return NewNoopTimeline()
	}

	// Apply defaults
	if cfg.TTL == 0 {
		cfg.TTL = 24 * time.Hour
	}
	if cfg.MaxEntries == 0 {
		cfg.MaxEntries = 1000
	}

	return &RedisTimeline{
		client: client,
		cfg:    cfg,
		logger: logrus.StandardLogger(),
	}
}

// NewRedisTimelineWithLogger creates a RedisTimeline with a custom logger.
func NewRedisTimelineWithLogger(client *redis.Client, cfg TimelineConfig, logger *logrus.Logger) TimelineRecorder {
	if !cfg.Enabled {
		return NewNoopTimeline()
	}

	// Apply defaults
	if cfg.TTL == 0 {
		cfg.TTL = 24 * time.Hour
	}
	if cfg.MaxEntries == 0 {
		cfg.MaxEntries = 1000
	}

	return &RedisTimeline{
		client: client,
		cfg:    cfg,
		logger: logger,
	}
}

// timelineKey generates the Redis key for an operation's timeline.
func timelineKey(operationID string) string {
	return fmt.Sprintf("operation:timeline:%s", operationID)
}

// Record adds a timeline event asynchronously (fire-and-forget).
// Errors are logged but not returned to avoid blocking the caller.
func (rt *RedisTimeline) Record(ctx context.Context, operationID, event string, metadata map[string]interface{}) {
	rt.wg.Add(1)
	go func() {
		defer rt.wg.Done()
		rt.recordSync(ctx, operationID, event, metadata)
	}()
}

// recordSync performs the actual Redis write operation.
func (rt *RedisTimeline) recordSync(ctx context.Context, operationID, event string, metadata map[string]interface{}) {
	if operationID == "" || event == "" {
		return
	}

	entry := timelineEntryStorage{
		Event:    event,
		Service:  rt.cfg.ServiceName,
		Metadata: metadata,
	}

	data, err := json.Marshal(entry)
	if err != nil {
		rt.logger.WithError(err).WithField("operation_id", operationID).
			Warn("timeline: failed to marshal entry")
		return
	}

	key := timelineKey(operationID)
	now := time.Now()
	score := float64(now.UnixNano() / int64(time.Millisecond))

	// Use pipeline for atomic operations
	pipe := rt.client.Pipeline()

	// Add entry to ZSET
	pipe.ZAdd(ctx, key, redis.Z{
		Score:  score,
		Member: string(data),
	})

	// Update TTL
	pipe.Expire(ctx, key, rt.cfg.TTL)

	// Trim to max entries (keep newest)
	if rt.cfg.MaxEntries > 0 {
		// ZREMRANGEBYRANK removes elements from start to stop (inclusive)
		// To keep the newest MaxEntries, remove from 0 to -(MaxEntries+1)
		pipe.ZRemRangeByRank(ctx, key, 0, int64(-rt.cfg.MaxEntries-1))
	}

	_, err = pipe.Exec(ctx)
	if err != nil {
		// Increment Prometheus error counter (FIX #8)
		timelineErrorsTotal.WithLabelValues(rt.cfg.ServiceName, "redis_write").Inc()

		rt.logger.WithError(err).WithFields(logrus.Fields{
			"operation_id": operationID,
			"event":        event,
		}).Warn("timeline: failed to record event")
	}
}

// GetTimeline retrieves all timeline events for an operation, sorted by timestamp.
func (rt *RedisTimeline) GetTimeline(ctx context.Context, operationID string) ([]TimelineEntry, error) {
	if operationID == "" {
		return nil, fmt.Errorf("operation ID is required")
	}

	key := timelineKey(operationID)

	// Get all entries sorted by score (timestamp)
	results, err := rt.client.ZRangeWithScores(ctx, key, 0, -1).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get timeline: %w", err)
	}

	entries := make([]TimelineEntry, 0, len(results))
	for _, z := range results {
		member, ok := z.Member.(string)
		if !ok {
			continue
		}

		var storage timelineEntryStorage
		if err := json.Unmarshal([]byte(member), &storage); err != nil {
			rt.logger.WithError(err).Warn("timeline: failed to unmarshal entry")
			continue
		}

		// Convert score (ms) back to time
		timestamp := time.UnixMilli(int64(z.Score))

		entries = append(entries, TimelineEntry{
			Timestamp: timestamp,
			Event:     storage.Event,
			Service:   storage.Service,
			Metadata:  storage.Metadata,
		})
	}

	return entries, nil
}

// Wait waits for all pending Record operations to complete.
// Useful for graceful shutdown or testing.
func (rt *RedisTimeline) Wait() {
	rt.wg.Wait()
}

// NoopTimeline is a no-op implementation of TimelineRecorder.
// Used when timeline is disabled or Redis is unavailable.
type NoopTimeline struct{}

// NewNoopTimeline creates a new NoopTimeline instance.
func NewNoopTimeline() TimelineRecorder {
	return &NoopTimeline{}
}

// Record is a no-op implementation.
func (nt *NoopTimeline) Record(ctx context.Context, operationID, event string, metadata map[string]interface{}) {
	// No-op: intentionally does nothing
}

// GetTimeline returns an empty list.
func (nt *NoopTimeline) GetTimeline(ctx context.Context, operationID string) ([]TimelineEntry, error) {
	return []TimelineEntry{}, nil
}
