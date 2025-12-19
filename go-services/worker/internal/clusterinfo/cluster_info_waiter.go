// Package clusterinfo provides cluster info resolution via Orchestrator (HTTP) or Redis Streams.
package clusterinfo

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// ClusterInfoWaiter errors
var (
	// ErrClusterInfoTimeout indicates that the response was not received within the timeout period
	ErrClusterInfoTimeout = errors.New("cluster info response timeout")

	// ErrClusterInfoWaiterClosed indicates that the waiter has been closed
	ErrClusterInfoWaiterClosed = errors.New("cluster info waiter is closed")

	// ErrClusterInfoDuplicateCorrelationID indicates that a wait is already registered
	ErrClusterInfoDuplicateCorrelationID = errors.New("duplicate correlation_id for cluster info")

	// ErrClusterInfoNotFound indicates that the database was not found in Orchestrator
	ErrClusterInfoNotFound = errors.New("database not found in Orchestrator")
)

// ClusterInfoRequest represents a request for cluster info via Streams.
type ClusterInfoRequest struct {
	// CorrelationID for matching request-response
	CorrelationID string `json:"correlation_id"`
	// DatabaseID is the Django database ID
	DatabaseID string `json:"database_id"`
	// OperationID is optional, for tracing purposes
	OperationID string `json:"operation_id,omitempty"`
	// Timestamp is when the request was created
	Timestamp string `json:"timestamp"`
}

// ClusterInfoResponse represents a response from Orchestrator via Streams.
type ClusterInfoResponse struct {
	// CorrelationID for matching request-response
	CorrelationID string `json:"correlation_id"`
	// DatabaseID is the Django database ID
	DatabaseID string `json:"database_id"`
	// ClusterID is the UUID of the 1C cluster in RAS (ras_cluster_uuid)
	ClusterID string `json:"cluster_id"`
	// RASServer is the RAS server address (host:port)
	RASServer string `json:"ras_server"`
	// RASClusterUUID is the UUID of the cluster in RAS
	RASClusterUUID string `json:"ras_cluster_uuid"`
	// InfobaseID is the UUID of the infobase in RAS
	InfobaseID string `json:"infobase_id"`
	// Success indicates if the request was successful
	Success bool `json:"success"`
	// Error contains error message if Success is false
	Error string `json:"error,omitempty"`
}

// ClusterInfoWaiter subscribes to cluster info response stream and matches responses by correlation_id.
// It implements the Request-Response pattern over Redis Streams for getting cluster info from Orchestrator.
type ClusterInfoWaiter struct {
	redisClient   *redis.Client
	consumerGroup string
	pending       map[string]chan *ClusterInfoResponse // correlation_id -> response channel
	mu            sync.RWMutex
	closed        bool
	wg            sync.WaitGroup
	cancelFunc    context.CancelFunc
}

// NewClusterInfoWaiter creates a new ClusterInfoWaiter.
func NewClusterInfoWaiter(redisClient *redis.Client, consumerGroup string) *ClusterInfoWaiter {
	if consumerGroup == "" {
		consumerGroup = events.ConsumerGroupWorkerClusterInfo
	}

	return &ClusterInfoWaiter{
		redisClient:   redisClient,
		consumerGroup: consumerGroup,
		pending:       make(map[string]chan *ClusterInfoResponse),
	}
}

// Start begins listening for cluster info responses on events:orchestrator:cluster-info-response.
// It runs until the context is cancelled.
func (w *ClusterInfoWaiter) Start(ctx context.Context) error {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return ErrClusterInfoWaiterClosed
	}

	// Create cancellable context
	ctx, w.cancelFunc = context.WithCancel(ctx)
	w.mu.Unlock()

	// Ensure consumer group exists
	stream := events.StreamEventsClusterInfoResponse
	err := w.redisClient.XGroupCreateMkStream(ctx, stream, w.consumerGroup, "0").Err()
	if err != nil && !isConsumerGroupExistsErr(err) {
		w.cancelFunc()
		return fmt.Errorf("failed to create consumer group: %w", err)
	}

	logger.Infof("ClusterInfoWaiter started, listening on stream: %s", stream)

	// Start consuming
	w.wg.Add(1)
	go w.consumeLoop(ctx, stream)

	return nil
}

// consumeLoop continuously reads from Redis Stream and dispatches responses.
func (w *ClusterInfoWaiter) consumeLoop(ctx context.Context, stream string) {
	defer w.wg.Done()

	consumerID := fmt.Sprintf("worker-cluster-info-%d", time.Now().UnixNano())

	for {
		select {
		case <-ctx.Done():
			logger.Info("ClusterInfoWaiter: context cancelled, stopping consumer loop")
			return
		default:
		}

		// Read from stream with blocking timeout
		result, err := w.redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    w.consumerGroup,
			Consumer: consumerID,
			Streams:  []string{stream, ">"},
			Count:    10,
			Block:    1 * time.Second,
		}).Result()

		if err != nil {
			if errors.Is(err, redis.Nil) {
				// No messages available, continue
				continue
			}
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return
			}
			logger.Warnf("ClusterInfoWaiter: error reading from stream: %v", err)
			time.Sleep(100 * time.Millisecond)
			continue
		}

		// Process messages
		for _, streamData := range result {
			for _, msg := range streamData.Messages {
				w.handleMessage(ctx, stream, msg)
			}
		}
	}
}

// handleMessage processes a single message from Redis Stream.
func (w *ClusterInfoWaiter) handleMessage(ctx context.Context, streamName string, msg redis.XMessage) {
	log := logger.GetLogger()

	// Parse response from message fields
	var response ClusterInfoResponse

	// Try to get correlation_id directly from message fields
	if corrID, ok := msg.Values["correlation_id"].(string); ok {
		response.CorrelationID = corrID
	}
	if dbID, ok := msg.Values["database_id"].(string); ok {
		response.DatabaseID = dbID
	}
	if clusterID, ok := msg.Values["cluster_id"].(string); ok {
		response.ClusterID = clusterID
	}
	if rasServer, ok := msg.Values["ras_server"].(string); ok {
		response.RASServer = rasServer
	}
	if rasClusterUUID, ok := msg.Values["ras_cluster_uuid"].(string); ok {
		response.RASClusterUUID = rasClusterUUID
	}
	if infobaseID, ok := msg.Values["infobase_id"].(string); ok {
		response.InfobaseID = infobaseID
	}
	if success, ok := msg.Values["success"].(string); ok {
		response.Success = success == "true" || success == "True" || success == "1"
	}
	if errMsg, ok := msg.Values["error"].(string); ok {
		response.Error = errMsg
	}

	// Fallback: try to parse from 'payload' or 'data' field (envelope format)
	if response.CorrelationID == "" {
		if payload, ok := msg.Values["payload"].(string); ok {
			if err := json.Unmarshal([]byte(payload), &response); err != nil {
				log.Warnf("ClusterInfoWaiter: failed to parse payload from %s: %v", msg.ID, err)
			}
		} else if data, ok := msg.Values["data"].(string); ok {
			if err := json.Unmarshal([]byte(data), &response); err != nil {
				log.Warnf("ClusterInfoWaiter: failed to parse data from %s: %v", msg.ID, err)
			}
		}
	}

	if response.CorrelationID == "" {
		log.Warnf("ClusterInfoWaiter: message %s has no correlation_id", msg.ID)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	// Find waiting channel
	w.mu.RLock()
	ch, exists := w.pending[response.CorrelationID]
	w.mu.RUnlock()

	if exists {
		// Send result to waiting channel (non-blocking)
		select {
		case ch <- &response:
			log.Debugf("ClusterInfoWaiter: dispatched response for correlation_id=%s", response.CorrelationID)
		default:
			log.Warnf("ClusterInfoWaiter: channel full for correlation_id=%s", response.CorrelationID)
		}
	} else {
		log.Debugf("ClusterInfoWaiter: no waiter for correlation_id=%s (may have timed out)", response.CorrelationID)
	}

	// ACK message
	w.ackMessage(ctx, streamName, msg.ID)
}

// ackMessage acknowledges a message in the consumer group.
func (w *ClusterInfoWaiter) ackMessage(ctx context.Context, stream, messageID string) {
	if err := w.redisClient.XAck(ctx, stream, w.consumerGroup, messageID).Err(); err != nil {
		logger.Warnf("ClusterInfoWaiter: failed to ACK message %s: %v", messageID, err)
	}
}

// RequestClusterInfo sends a request to Orchestrator and waits for response.
// It returns the ClusterInfo or an error if timeout is reached or request fails.
func (w *ClusterInfoWaiter) RequestClusterInfo(ctx context.Context, databaseID string, timeout time.Duration) (*ClusterInfo, error) {
	log := logger.GetLogger()

	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return nil, ErrClusterInfoWaiterClosed
	}

	// Generate correlation ID
	correlationID := uuid.New().String()

	// Check for duplicate (very unlikely with UUID)
	if _, exists := w.pending[correlationID]; exists {
		w.mu.Unlock()
		return nil, fmt.Errorf("%w: %s", ErrClusterInfoDuplicateCorrelationID, correlationID)
	}

	// Create response channel (buffered to avoid blocking sender)
	ch := make(chan *ClusterInfoResponse, 1)
	w.pending[correlationID] = ch
	w.mu.Unlock()

	// Cleanup on exit
	defer func() {
		w.mu.Lock()
		delete(w.pending, correlationID)
		close(ch)
		w.mu.Unlock()
	}()

	// Create request
	request := ClusterInfoRequest{
		CorrelationID: correlationID,
		DatabaseID:    databaseID,
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
	}

	// Publish request to command stream
	requestFields := map[string]interface{}{
		"correlation_id": request.CorrelationID,
		"database_id":    request.DatabaseID,
		"timestamp":      request.Timestamp,
	}

	err := w.redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: events.StreamCommandsGetClusterInfo,
		Values: requestFields,
	}).Err()
	if err != nil {
		return nil, fmt.Errorf("failed to publish cluster info request: %w", err)
	}

	log.Debugf("ClusterInfoWaiter: published request for database_id=%s, correlation_id=%s", databaseID, correlationID)

	// Wait with timeout
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	select {
	case response := <-ch:
		if !response.Success {
			if response.Error != "" {
				return nil, fmt.Errorf("%w: %s", ErrClusterInfoNotFound, response.Error)
			}
			return nil, ErrClusterInfoNotFound
		}

		// Convert response to ClusterInfo
		// Use RASClusterUUID as ClusterID (this is what RAS needs)
		clusterID := response.RASClusterUUID
		if clusterID == "" {
			clusterID = response.ClusterID
		}

		return &ClusterInfo{
			DatabaseID: response.DatabaseID,
			ClusterID:  clusterID,
			InfobaseID: response.InfobaseID,
			RASServer:  response.RASServer,
		}, nil

	case <-ctx.Done():
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("%w: correlation_id=%s, timeout=%v", ErrClusterInfoTimeout, correlationID, timeout)
		}
		return nil, ctx.Err()
	}
}

// PendingCount returns the number of pending waits.
func (w *ClusterInfoWaiter) PendingCount() int {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return len(w.pending)
}

// Close gracefully shuts down the waiter.
func (w *ClusterInfoWaiter) Close() error {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return nil
	}
	w.closed = true

	// 1. Copy pending channels for safe closing
	pendingToClose := make(map[string]chan *ClusterInfoResponse)
	for id, ch := range w.pending {
		pendingToClose[id] = ch
	}
	// 2. Clear pending BEFORE cancelling context
	w.pending = make(map[string]chan *ClusterInfoResponse)

	if w.cancelFunc != nil {
		w.cancelFunc()
	}
	w.mu.Unlock()

	// 3. Wait for consumer loop to finish
	w.wg.Wait()

	// 4. Close channels WITHOUT lock (safe, consumeLoop already finished)
	for _, ch := range pendingToClose {
		close(ch)
	}

	logger.Info("ClusterInfoWaiter closed successfully")
	return nil
}

// isConsumerGroupExistsErr checks if error indicates consumer group already exists.
func isConsumerGroupExistsErr(err error) bool {
	return err != nil && err.Error() == "BUSYGROUP Consumer Group name already exists"
}
