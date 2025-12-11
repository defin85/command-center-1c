package rasadapter

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/ras"
	"github.com/google/uuid"
)

const (
	// DefaultTimeout is the default timeout for RAS operations
	DefaultTimeout = 30 * time.Second

	// ServiceNameWorker is the service name used for publishing events
	ServiceNameWorker = "worker"
)

// StreamClient errors
var (
	// ErrStreamClientClosed indicates that the client has been closed
	ErrStreamClientClosed = errors.New("stream client is closed")

	// ErrPublishFailed indicates that publishing the command failed
	ErrPublishFailed = errors.New("failed to publish command")

	// ErrCommandFailed indicates that the RAS command execution failed
	ErrCommandFailed = errors.New("RAS command failed")
)

// StreamClient publishes RAS commands to Redis Streams and waits for responses.
// It implements the Request-Response pattern over Redis Streams.
type StreamClient struct {
	publisher      *events.Publisher
	waiter         *ResponseWaiter
	defaultTimeout time.Duration
	mu             sync.RWMutex
	closed         bool
}

// NewStreamClient creates a new StreamClient.
func NewStreamClient(publisher *events.Publisher, waiter *ResponseWaiter) *StreamClient {
	return &StreamClient{
		publisher:      publisher,
		waiter:         waiter,
		defaultTimeout: DefaultTimeout,
	}
}

// NewStreamClientWithTimeout creates a new StreamClient with custom timeout.
func NewStreamClientWithTimeout(publisher *events.Publisher, waiter *ResponseWaiter, timeout time.Duration) *StreamClient {
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	return &StreamClient{
		publisher:      publisher,
		waiter:         waiter,
		defaultTimeout: timeout,
	}
}

// SetDefaultTimeout sets the default timeout for operations.
func (c *StreamClient) SetDefaultTimeout(timeout time.Duration) {
	if timeout > 0 {
		c.defaultTimeout = timeout
	}
}

// executeCommand is the internal method that publishes a command and waits for response.
func (c *StreamClient) executeCommand(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	c.mu.RLock()
	if c.closed {
		c.mu.RUnlock()
		return nil, ErrStreamClientClosed
	}
	c.mu.RUnlock()

	if timeout <= 0 {
		timeout = c.defaultTimeout
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		return nil, fmt.Errorf("invalid command: %w", err)
	}

	// Get stream for command type
	stream, err := ras.GetCommandStream(cmd.CommandType)
	if err != nil {
		return nil, fmt.Errorf("unknown command type %s: %w", cmd.CommandType, err)
	}

	// Generate correlation ID
	correlationID := uuid.New().String()

	// Register wait BEFORE publishing (to avoid race condition)
	responseCh, err := c.waiter.RegisterWait(correlationID)
	if err != nil {
		return nil, fmt.Errorf("failed to register wait: %w", err)
	}
	defer c.waiter.UnregisterWait(correlationID)

	// Create event type based on command
	eventType := fmt.Sprintf("commands:ras:%s", cmd.CommandType)

	// Publish command
	logger.WithFields(map[string]interface{}{
		"correlation_id": correlationID,
		"operation_id":   cmd.OperationID,
		"database_id":    cmd.DatabaseID,
		"command_type":   cmd.CommandType,
		"stream":         stream,
	}).Debug("Publishing RAS command")

	if err := c.publisher.Publish(ctx, stream, eventType, cmd, correlationID); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrPublishFailed, err)
	}

	// Wait for response with timeout
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	select {
	case result := <-responseCh:
		if result == nil {
			return nil, fmt.Errorf("received nil result for correlation_id=%s", correlationID)
		}

		logger.WithFields(map[string]interface{}{
			"correlation_id": correlationID,
			"operation_id":   cmd.OperationID,
			"database_id":    cmd.DatabaseID,
			"command_type":   cmd.CommandType,
			"success":        result.Success,
			"duration":       result.Duration,
		}).Debug("Received RAS response")

		// Check for command failure
		if !result.Success {
			return result, fmt.Errorf("%w: %s", ErrCommandFailed, result.Error)
		}

		return result, nil

	case <-ctx.Done():
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("%w: correlation_id=%s, timeout=%v", ErrResponseTimeout, correlationID, timeout)
		}
		return nil, ctx.Err()
	}
}

// LockScheduledJobs sends a lock command and waits for the result.
// It locks scheduled jobs for an infobase (sets ScheduledJobsDeny = true).
func (c *StreamClient) LockScheduledJobs(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	// Ensure command type is correct
	cmd.CommandType = ras.CommandTypeLock
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// LockScheduledJobsWithTimeout sends a lock command with custom timeout.
func (c *StreamClient) LockScheduledJobsWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeLock
	return c.executeCommand(ctx, cmd, timeout)
}

// UnlockScheduledJobs sends an unlock command and waits for the result.
// It unlocks scheduled jobs for an infobase (sets ScheduledJobsDeny = false).
func (c *StreamClient) UnlockScheduledJobs(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeUnlock
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// UnlockScheduledJobsWithTimeout sends an unlock command with custom timeout.
func (c *StreamClient) UnlockScheduledJobsWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeUnlock
	return c.executeCommand(ctx, cmd, timeout)
}

// BlockSessions sends a block command and waits for the result.
// It blocks new user sessions for an infobase (sets SessionsDeny = true).
func (c *StreamClient) BlockSessions(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeBlock
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// BlockSessionsWithTimeout sends a block command with custom timeout.
func (c *StreamClient) BlockSessionsWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeBlock
	return c.executeCommand(ctx, cmd, timeout)
}

// UnblockSessions sends an unblock command and waits for the result.
// It unblocks user sessions for an infobase (sets SessionsDeny = false).
func (c *StreamClient) UnblockSessions(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeUnblock
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// UnblockSessionsWithTimeout sends an unblock command with custom timeout.
func (c *StreamClient) UnblockSessionsWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeUnblock
	return c.executeCommand(ctx, cmd, timeout)
}

// TerminateSessions sends a terminate command and waits for the result.
// It terminates active sessions for an infobase.
func (c *StreamClient) TerminateSessions(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeTerminate
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// TerminateSessionsWithTimeout sends a terminate command with custom timeout.
func (c *StreamClient) TerminateSessionsWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	cmd.CommandType = ras.CommandTypeTerminate
	return c.executeCommand(ctx, cmd, timeout)
}

// Execute sends any RAS command and waits for the result.
// The command type is determined by cmd.CommandType.
func (c *StreamClient) Execute(ctx context.Context, cmd *ras.RASCommand) (*ras.RASResult, error) {
	return c.executeCommand(ctx, cmd, c.defaultTimeout)
}

// ExecuteWithTimeout sends any RAS command with custom timeout.
func (c *StreamClient) ExecuteWithTimeout(ctx context.Context, cmd *ras.RASCommand, timeout time.Duration) (*ras.RASResult, error) {
	return c.executeCommand(ctx, cmd, timeout)
}

// ExecuteAsync publishes a command without waiting for response.
// Returns the correlation ID for manual tracking.
func (c *StreamClient) ExecuteAsync(ctx context.Context, cmd *ras.RASCommand) (string, error) {
	c.mu.RLock()
	if c.closed {
		c.mu.RUnlock()
		return "", ErrStreamClientClosed
	}
	c.mu.RUnlock()

	if err := cmd.Validate(); err != nil {
		return "", fmt.Errorf("invalid command: %w", err)
	}

	stream, err := ras.GetCommandStream(cmd.CommandType)
	if err != nil {
		return "", fmt.Errorf("unknown command type %s: %w", cmd.CommandType, err)
	}

	correlationID := uuid.New().String()
	eventType := fmt.Sprintf("commands:ras:%s", cmd.CommandType)

	if err := c.publisher.Publish(ctx, stream, eventType, cmd, correlationID); err != nil {
		return "", fmt.Errorf("%w: %v", ErrPublishFailed, err)
	}

	logger.WithFields(map[string]interface{}{
		"correlation_id": correlationID,
		"operation_id":   cmd.OperationID,
		"database_id":    cmd.DatabaseID,
		"command_type":   cmd.CommandType,
	}).Debug("Published async RAS command")

	return correlationID, nil
}

// Close marks the client as closed.
// Note: This does not close the publisher or waiter - those should be closed separately.
func (c *StreamClient) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.closed {
		return nil
	}
	c.closed = true
	logger.Info("StreamClient closed")
	return nil
}

// IsClosed returns true if the client has been closed.
func (c *StreamClient) IsClosed() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.closed
}

// DefaultTimeout returns the current default timeout.
func (c *StreamClient) DefaultTimeout() time.Duration {
	return c.defaultTimeout
}
