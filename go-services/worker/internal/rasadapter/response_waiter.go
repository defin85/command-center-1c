// Package rasadapter provides HTTP and Redis Streams clients for communicating with RAS Adapter.
package rasadapter

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/ras"
	"github.com/redis/go-redis/v9"
)

// ResponseWaiter errors
var (
	// ErrResponseTimeout indicates that the response was not received within the timeout period
	ErrResponseTimeout = errors.New("response timeout")

	// ErrWaiterClosed indicates that the waiter has been closed
	ErrWaiterClosed = errors.New("response waiter is closed")

	// ErrDuplicateCorrelationID indicates that a wait is already registered for this correlation ID
	ErrDuplicateCorrelationID = errors.New("duplicate correlation_id")
)

// ResponseWaiter subscribes to RAS result streams and matches responses by correlation_id.
// It implements the Request-Response pattern over Redis Streams.
type ResponseWaiter struct {
	redisClient   *redis.Client
	consumerGroup string
	pending       map[string]chan *ras.RASResult // correlation_id -> response channel
	mu            sync.RWMutex
	closed        bool
	wg            sync.WaitGroup
	cancelFunc    context.CancelFunc
}

// NewResponseWaiter creates a new ResponseWaiter.
func NewResponseWaiter(redisClient *redis.Client, consumerGroup string) *ResponseWaiter {
	if consumerGroup == "" {
		consumerGroup = ras.ConsumerGroupWorker
	}

	return &ResponseWaiter{
		redisClient:   redisClient,
		consumerGroup: consumerGroup,
		pending:       make(map[string]chan *ras.RASResult),
	}
}

// Start begins listening for RAS responses on events:ras:completed and events:ras:failed.
// It runs until the context is cancelled.
func (w *ResponseWaiter) Start(ctx context.Context) error {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return ErrWaiterClosed
	}

	// Create cancellable context
	ctx, w.cancelFunc = context.WithCancel(ctx)
	w.mu.Unlock()

	// Ensure consumer group exists for both streams
	streams := ras.AllEventStreams()
	for _, stream := range streams {
		// Create consumer group if it doesn't exist
		err := w.redisClient.XGroupCreateMkStream(ctx, stream, w.consumerGroup, "0").Err()
		if err != nil && !isConsumerGroupExistsError(err) {
			logger.Warnf("Failed to create consumer group for %s: %v", stream, err)
		}
	}

	logger.Infof("ResponseWaiter started, listening on streams: %v", streams)

	// Start consuming from both streams
	w.wg.Add(1)
	go w.consumeLoop(ctx, streams)

	return nil
}

// consumeLoop continuously reads from Redis Streams and dispatches responses.
func (w *ResponseWaiter) consumeLoop(ctx context.Context, streams []string) {
	defer w.wg.Done()

	// Build stream args: stream1, stream2, ">", ">"
	streamArgs := make([]string, 0, len(streams)*2)
	for _, s := range streams {
		streamArgs = append(streamArgs, s)
	}
	for range streams {
		streamArgs = append(streamArgs, ">")
	}

	consumerID := fmt.Sprintf("worker-waiter-%d", time.Now().UnixNano())

	for {
		select {
		case <-ctx.Done():
			logger.Info("ResponseWaiter: context cancelled, stopping consumer loop")
			return
		default:
		}

		// Read from streams with blocking timeout
		result, err := w.redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    w.consumerGroup,
			Consumer: consumerID,
			Streams:  streamArgs,
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
			logger.Warnf("ResponseWaiter: error reading from streams: %v", err)
			time.Sleep(100 * time.Millisecond)
			continue
		}

		// Process messages
		for _, stream := range result {
			for _, msg := range stream.Messages {
				w.handleMessage(ctx, stream.Stream, msg)
			}
		}
	}
}

// handleMessage processes a single message from Redis Streams.
func (w *ResponseWaiter) handleMessage(ctx context.Context, streamName string, msg redis.XMessage) {
	// Extract envelope from message
	payload, ok := msg.Values["payload"]
	if !ok {
		// Try to get from Watermill format
		payload, ok = msg.Values["_watermill_message_payload"]
	}
	if !ok {
		logger.Warnf("ResponseWaiter: message %s has no payload", msg.ID)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	payloadStr, ok := payload.(string)
	if !ok {
		logger.Warnf("ResponseWaiter: message %s payload is not a string", msg.ID)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	// Parse envelope
	var envelope events.Envelope
	if err := json.Unmarshal([]byte(payloadStr), &envelope); err != nil {
		logger.Warnf("ResponseWaiter: failed to unmarshal envelope from %s: %v", msg.ID, err)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	// Extract RAS result from envelope payload
	var result ras.RASResult
	if err := json.Unmarshal(envelope.Payload, &result); err != nil {
		logger.Warnf("ResponseWaiter: failed to unmarshal RASResult from %s: %v", msg.ID, err)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	// Determine success based on stream
	if streamName == ras.StreamEventsFailed {
		result.Success = false
	}

	correlationID := envelope.CorrelationID
	if correlationID == "" {
		logger.Warnf("ResponseWaiter: message %s has no correlation_id", msg.ID)
		w.ackMessage(ctx, streamName, msg.ID)
		return
	}

	// Find waiting channel
	w.mu.RLock()
	ch, exists := w.pending[correlationID]
	w.mu.RUnlock()

	if exists {
		// Send result to waiting channel (non-blocking)
		select {
		case ch <- &result:
			logger.Debugf("ResponseWaiter: dispatched response for correlation_id=%s", correlationID)
		default:
			logger.Warnf("ResponseWaiter: channel full for correlation_id=%s", correlationID)
		}
	} else {
		logger.Debugf("ResponseWaiter: no waiter for correlation_id=%s (may have timed out)", correlationID)
	}

	// ACK message
	w.ackMessage(ctx, streamName, msg.ID)
}

// ackMessage acknowledges a message in the consumer group.
func (w *ResponseWaiter) ackMessage(ctx context.Context, stream, messageID string) {
	if err := w.redisClient.XAck(ctx, stream, w.consumerGroup, messageID).Err(); err != nil {
		logger.Warnf("ResponseWaiter: failed to ACK message %s: %v", messageID, err)
	}
}

// WaitForResponse waits for a response with the given correlation ID.
// It returns the result or an error if timeout is reached.
func (w *ResponseWaiter) WaitForResponse(ctx context.Context, correlationID string, timeout time.Duration) (*ras.RASResult, error) {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return nil, ErrWaiterClosed
	}

	// Check for duplicate
	if _, exists := w.pending[correlationID]; exists {
		w.mu.Unlock()
		return nil, fmt.Errorf("%w: %s", ErrDuplicateCorrelationID, correlationID)
	}

	// Create response channel (buffered to avoid blocking sender)
	ch := make(chan *ras.RASResult, 1)
	w.pending[correlationID] = ch
	w.mu.Unlock()

	// Cleanup on exit
	defer func() {
		w.mu.Lock()
		delete(w.pending, correlationID)
		close(ch)
		w.mu.Unlock()
	}()

	// Wait with timeout
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	select {
	case result := <-ch:
		return result, nil
	case <-ctx.Done():
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("%w: correlation_id=%s, timeout=%v", ErrResponseTimeout, correlationID, timeout)
		}
		return nil, ctx.Err()
	}
}

// RegisterWait registers a wait for a correlation ID and returns the channel.
// This is useful when you need to publish first and then wait.
func (w *ResponseWaiter) RegisterWait(correlationID string) (chan *ras.RASResult, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.closed {
		return nil, ErrWaiterClosed
	}

	if _, exists := w.pending[correlationID]; exists {
		return nil, fmt.Errorf("%w: %s", ErrDuplicateCorrelationID, correlationID)
	}

	ch := make(chan *ras.RASResult, 1)
	w.pending[correlationID] = ch
	return ch, nil
}

// UnregisterWait removes a wait registration.
func (w *ResponseWaiter) UnregisterWait(correlationID string) {
	w.mu.Lock()
	defer w.mu.Unlock()

	if ch, exists := w.pending[correlationID]; exists {
		delete(w.pending, correlationID)
		close(ch)
	}
}

// PendingCount returns the number of pending waits.
func (w *ResponseWaiter) PendingCount() int {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return len(w.pending)
}

// Close gracefully shuts down the waiter.
func (w *ResponseWaiter) Close() error {
	w.mu.Lock()
	if w.closed {
		w.mu.Unlock()
		return nil
	}

	w.closed = true

	// Cancel context to stop consumer loop
	if w.cancelFunc != nil {
		w.cancelFunc()
	}
	w.mu.Unlock()

	// Wait for consumer loop to finish
	w.wg.Wait()

	// Close all pending channels with timeout error
	w.mu.Lock()
	for id, ch := range w.pending {
		delete(w.pending, id)
		close(ch)
	}
	w.mu.Unlock()

	logger.Info("ResponseWaiter closed successfully")
	return nil
}

// isConsumerGroupExistsError checks if error indicates consumer group already exists.
func isConsumerGroupExistsError(err error) bool {
	return err != nil && err.Error() == "BUSYGROUP Consumer Group name already exists"
}

// WatermillLoggerAdapter adapts our logger to Watermill's interface.
type WatermillLoggerAdapter struct{}

// NewWatermillLoggerAdapter creates a new adapter.
func NewWatermillLoggerAdapter() watermill.LoggerAdapter {
	return &WatermillLoggerAdapter{}
}

// Error logs an error message.
func (a *WatermillLoggerAdapter) Error(msg string, err error, fields watermill.LogFields) {
	logger.WithFields(fieldsToLogrus(fields)).Errorf("%s: %v", msg, err)
}

// Info logs an info message.
func (a *WatermillLoggerAdapter) Info(msg string, fields watermill.LogFields) {
	logger.WithFields(fieldsToLogrus(fields)).Info(msg)
}

// Debug logs a debug message.
func (a *WatermillLoggerAdapter) Debug(msg string, fields watermill.LogFields) {
	logger.WithFields(fieldsToLogrus(fields)).Debug(msg)
}

// Trace logs a trace message.
func (a *WatermillLoggerAdapter) Trace(msg string, fields watermill.LogFields) {
	logger.WithFields(fieldsToLogrus(fields)).Debug(msg)
}

// With returns a new logger with additional fields.
func (a *WatermillLoggerAdapter) With(fields watermill.LogFields) watermill.LoggerAdapter {
	return a // Simplified: just return same adapter
}

// fieldsToLogrus converts Watermill fields to logrus fields.
func fieldsToLogrus(fields watermill.LogFields) map[string]interface{} {
	result := make(map[string]interface{}, len(fields))
	for k, v := range fields {
		result[k] = v
	}
	return result
}
