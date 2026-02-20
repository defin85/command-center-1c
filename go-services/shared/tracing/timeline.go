package tracing

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
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
	timelineDroppedTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_timeline_dropped_total",
			Help: "Total timeline events dropped before enqueue",
		},
		[]string{"service", "reason"},
	)
)

func init() {
	prometheus.MustRegister(timelineErrorsTotal)
	prometheus.MustRegister(timelineDroppedTotal)
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
	// StreamEnabled publishes timeline events to Redis Streams for live updates.
	StreamEnabled bool
	// StreamMaxLen caps stream length when StreamEnabled is true.
	StreamMaxLen int
	// QueueSize bounds the number of pending timeline events.
	QueueSize int
	// WorkerCount controls concurrent Redis writers.
	WorkerCount int
	// DropOnFull drops events when queue is full to keep Record non-blocking.
	DropOnFull bool
}

// DefaultTimelineConfig returns a TimelineConfig with default values.
func DefaultTimelineConfig(serviceName string) TimelineConfig {
	return TimelineConfig{
		Enabled:       true,
		TTL:           24 * time.Hour,
		ServiceName:   serviceName,
		MaxEntries:    1000,
		StreamEnabled: false,
		StreamMaxLen:  1000,
		QueueSize:     10000,
		WorkerCount:   4,
		DropOnFull:    true,
	}
}

type timelineRecord struct {
	ctx         context.Context
	operationID string
	event       string
	metadata    map[string]interface{}
}

// RedisTimeline implements TimelineRecorder using Redis ZSET.
type RedisTimeline struct {
	client      *redis.Client
	cfg         TimelineConfig
	logger      *logrus.Logger
	recordWG    sync.WaitGroup
	queue       chan timelineRecord
	workerCount int
	mu          sync.RWMutex
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
	if cfg.StreamMaxLen == 0 {
		cfg.StreamMaxLen = cfg.MaxEntries
	}
	if cfg.QueueSize == 0 {
		cfg.QueueSize = 10000
	}
	if cfg.WorkerCount == 0 {
		cfg.WorkerCount = 4
	}

	timeline := &RedisTimeline{
		client: client,
		cfg:    cfg,
		logger: logrus.StandardLogger(),
	}
	timeline.startWorkers()
	return timeline
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
	if cfg.StreamMaxLen == 0 {
		cfg.StreamMaxLen = cfg.MaxEntries
	}
	if cfg.QueueSize == 0 {
		cfg.QueueSize = 10000
	}
	if cfg.WorkerCount == 0 {
		cfg.WorkerCount = 4
	}

	timeline := &RedisTimeline{
		client: client,
		cfg:    cfg,
		logger: logger,
	}
	timeline.startWorkers()
	return timeline
}

// timelineKey generates the Redis key for an operation's timeline.
func timelineKey(operationID string) string {
	return fmt.Sprintf("operation:timeline:%s", operationID)
}

// Record adds a timeline event asynchronously (fire-and-forget).
// Errors are logged but not returned to avoid blocking the caller.
func (rt *RedisTimeline) Record(ctx context.Context, operationID, event string, metadata map[string]interface{}) {
	record := timelineRecord{
		ctx:         ctx,
		operationID: operationID,
		event:       event,
		metadata:    metadata,
	}
	rt.mu.RLock()
	queue := rt.queue
	dropOnFull := rt.cfg.DropOnFull
	if queue != nil {
		rt.recordWG.Add(1)
		select {
		case queue <- record:
			rt.mu.RUnlock()
			return
		default:
			rt.recordWG.Done()
			rt.mu.RUnlock()
			if dropOnFull {
				timelineDroppedTotal.WithLabelValues(rt.cfg.ServiceName, "queue_full").Inc()
				return
			}
		}
	} else {
		rt.mu.RUnlock()
	}
	rt.recordWG.Add(1)
	go func() {
		defer rt.recordWG.Done()
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

	if rt.cfg.StreamEnabled {
		rt.publishToStream(ctx, operationID, entry, score)
	}
}

func (rt *RedisTimeline) publishToStream(
	ctx context.Context,
	operationID string,
	entry timelineEntryStorage,
	timestampMs float64,
) {
	normalizedMetadata := map[string]interface{}{}
	for key, value := range entry.Metadata {
		normalizedMetadata[key] = value
	}
	rootOperationID := operationID
	if value, ok := normalizedMetadata["root_operation_id"]; ok {
		candidate := strings.TrimSpace(fmt.Sprint(value))
		if candidate != "" {
			rootOperationID = candidate
		}
	}
	executionConsumer := "operations"
	if value, ok := normalizedMetadata["execution_consumer"]; ok {
		candidate := strings.TrimSpace(fmt.Sprint(value))
		if candidate != "" {
			executionConsumer = candidate
		}
	}
	lane := executionConsumer
	if value, ok := normalizedMetadata["lane"]; ok {
		candidate := strings.TrimSpace(fmt.Sprint(value))
		if candidate != "" {
			lane = candidate
		}
	}
	normalizedMetadata["root_operation_id"] = rootOperationID
	normalizedMetadata["execution_consumer"] = executionConsumer
	normalizedMetadata["lane"] = lane

	payload := map[string]interface{}{
		"operation_id":       operationID,
		"timestamp":          int64(timestampMs),
		"event":              entry.Event,
		"service":            entry.Service,
		"metadata":           normalizedMetadata,
		"root_operation_id":  rootOperationID,
		"execution_consumer": executionConsumer,
		"lane":               lane,
	}
	if traceID, ok := normalizedMetadata["trace_id"]; ok {
		payload["trace_id"] = traceID
	}
	if workflowID, ok := normalizedMetadata["workflow_execution_id"]; ok {
		payload["workflow_execution_id"] = workflowID
	}
	if nodeID, ok := normalizedMetadata["node_id"]; ok {
		payload["node_id"] = nodeID
	}

	data, err := json.Marshal(payload)
	if err != nil {
		rt.logger.WithError(err).WithField("operation_id", operationID).
			Warn("timeline: failed to marshal stream event")
		return
	}

	stream := fmt.Sprintf("events:operation:%s", operationID)
	if err := rt.client.XAdd(ctx, &redis.XAddArgs{
		Stream: stream,
		MaxLen: int64(rt.cfg.StreamMaxLen),
		Approx: true,
		Values: map[string]interface{}{
			"event_type":   entry.Event,
			"data":         string(data),
			"operation_id": operationID,
		},
	}).Err(); err != nil {
		timelineErrorsTotal.WithLabelValues(rt.cfg.ServiceName, "stream_write").Inc()
		rt.logger.WithError(err).WithFields(logrus.Fields{
			"operation_id": operationID,
			"event":        entry.Event,
		}).Warn("timeline: failed to publish stream event")
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
	rt.recordWG.Wait()
}

func (rt *RedisTimeline) startWorkers() {
	if rt.cfg.QueueSize <= 0 || rt.cfg.WorkerCount <= 0 {
		return
	}
	rt.queue = make(chan timelineRecord, rt.cfg.QueueSize)
	rt.workerCount = rt.cfg.WorkerCount
	for i := 0; i < rt.cfg.WorkerCount; i++ {
		rt.startWorker(rt.queue)
	}
}

func (rt *RedisTimeline) startWorker(queue chan timelineRecord) {
	if queue == nil {
		return
	}
	go func() {
		for record := range queue {
			rt.recordSync(record.ctx, record.operationID, record.event, record.metadata)
			rt.recordWG.Done()
		}
	}()
}

func (rt *RedisTimeline) UpdateWorkerCount(count int) {
	if count <= 0 {
		return
	}
	rt.mu.Lock()
	defer rt.mu.Unlock()
	rt.cfg.WorkerCount = count
	if rt.queue == nil {
		rt.workerCount = count
		return
	}
	if count <= rt.workerCount {
		return
	}
	for i := rt.workerCount; i < count; i++ {
		rt.startWorker(rt.queue)
	}
	rt.workerCount = count
}

func (rt *RedisTimeline) UpdateDropOnFull(dropOnFull bool) {
	rt.mu.Lock()
	rt.cfg.DropOnFull = dropOnFull
	rt.mu.Unlock()
}

func (rt *RedisTimeline) ResetQueue(queueSize int, workerCount int) {
	if queueSize <= 0 || workerCount <= 0 {
		return
	}
	rt.mu.Lock()
	oldQueue := rt.queue
	rt.cfg.QueueSize = queueSize
	rt.cfg.WorkerCount = workerCount
	rt.queue = make(chan timelineRecord, queueSize)
	rt.workerCount = workerCount
	for i := 0; i < workerCount; i++ {
		rt.startWorker(rt.queue)
	}
	rt.mu.Unlock()

	if oldQueue != nil {
		close(oldQueue)
	}
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
