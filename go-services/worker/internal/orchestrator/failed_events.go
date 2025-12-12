package orchestrator

import (
	"context"
	"fmt"
	"time"
)

const (
	// API paths for failed events endpoints
	pathFailedEventsPending = "/api/v2/internal/list-pending-failed-events"
	pathFailedEventReplayed = "/api/v2/internal/mark-event-replayed"
	pathFailedEventFailed   = "/api/v2/internal/mark-event-failed"
	pathFailedEventsCleanup = "/api/v2/internal/cleanup-failed-events"

	// Default values
	defaultBatchSize     = 100
	defaultRetentionDays = 7
)

// GetPendingFailedEvents returns failed events that are ready for replay.
// batchSize limits the number of returned events (1-1000, default 100).
func (c *Client) GetPendingFailedEvents(ctx context.Context, batchSize int) ([]FailedEvent, error) {
	if batchSize <= 0 {
		batchSize = defaultBatchSize
	}
	if batchSize > 1000 {
		batchSize = 1000
	}

	path := fmt.Sprintf("%s?batch_size=%d", pathFailedEventsPending, batchSize)

	var resp FailedEventsPendingResponse
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, fmt.Errorf("failed to get pending failed events: %w", err)
	}
	return resp.Events, nil
}

// MarkEventReplayed marks a failed event as successfully replayed.
func (c *Client) MarkEventReplayed(ctx context.Context, eventID int) error {
	return c.MarkEventReplayedAt(ctx, eventID, nil)
}

// MarkEventReplayedAt marks a failed event as replayed with optional timestamp.
func (c *Client) MarkEventReplayedAt(ctx context.Context, eventID int, replayedAt *time.Time) error {
	if eventID <= 0 {
		return fmt.Errorf("event ID must be positive")
	}

	path := fmt.Sprintf("%s?event_id=%d", pathFailedEventReplayed, eventID)

	req := &FailedEventReplayedRequest{
		ReplayedAt: replayedAt,
	}

	var resp FailedEventReplayedResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return fmt.Errorf("failed to mark event as replayed: %w", err)
	}

	return nil
}

// MarkEventFailed marks a failed event with an error and increments retry count.
// If retry_count >= max_retries after increment, status changes to "failed" (permanently).
func (c *Client) MarkEventFailed(ctx context.Context, eventID int, errorMessage string) (*FailedEventFailedResponse, error) {
	return c.MarkEventFailedWithOptions(ctx, eventID, errorMessage, true)
}

// MarkEventFailedWithOptions marks a failed event with error and optional retry increment.
func (c *Client) MarkEventFailedWithOptions(ctx context.Context, eventID int, errorMessage string, incrementRetry bool) (*FailedEventFailedResponse, error) {
	if eventID <= 0 {
		return nil, fmt.Errorf("event ID must be positive")
	}
	if errorMessage == "" {
		return nil, fmt.Errorf("error message is required")
	}

	path := fmt.Sprintf("%s?event_id=%d", pathFailedEventFailed, eventID)

	req := &FailedEventFailedRequest{
		ErrorMessage:   errorMessage,
		IncrementRetry: &incrementRetry,
	}

	var resp FailedEventFailedResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return nil, fmt.Errorf("failed to mark event as failed: %w", err)
	}

	return &resp, nil
}

// CleanupOldEvents removes old replayed/failed events.
// retentionDays specifies how old events should be to be deleted (1-365, default 7).
// Returns the number of deleted events.
func (c *Client) CleanupOldEvents(ctx context.Context, retentionDays int) (int, error) {
	if retentionDays <= 0 {
		retentionDays = defaultRetentionDays
	}
	if retentionDays > 365 {
		retentionDays = 365
	}

	req := &FailedEventsCleanupRequest{
		RetentionDays: retentionDays,
	}

	var resp FailedEventsCleanupResponse
	if err := c.post(ctx, pathFailedEventsCleanup, req, &resp); err != nil {
		return 0, fmt.Errorf("failed to cleanup old events: %w", err)
	}
	return resp.DeletedCount, nil
}

// ============================================================================
// EventReplayClient Interface
// ============================================================================

// EventReplayClient defines the interface for event replay operations.
// This interface allows for easier testing and potential future implementations.
type EventReplayClient interface {
	// GetPendingFailedEvents returns events that are ready for replay.
	GetPendingFailedEvents(ctx context.Context, batchSize int) ([]FailedEvent, error)

	// MarkEventReplayed marks an event as successfully replayed.
	MarkEventReplayed(ctx context.Context, eventID int) error

	// MarkEventReplayedAt marks an event as replayed with specific timestamp.
	MarkEventReplayedAt(ctx context.Context, eventID int, replayedAt *time.Time) error

	// MarkEventFailed marks an event as failed and increments retry count.
	MarkEventFailed(ctx context.Context, eventID int, errorMessage string) (*FailedEventFailedResponse, error)

	// MarkEventFailedWithOptions marks an event as failed with retry control.
	MarkEventFailedWithOptions(ctx context.Context, eventID int, errorMessage string, incrementRetry bool) (*FailedEventFailedResponse, error)

	// CleanupOldEvents removes old replayed/failed events.
	CleanupOldEvents(ctx context.Context, retentionDays int) (int, error)
}

// Verify Client implements EventReplayClient
var _ EventReplayClient = (*Client)(nil)
