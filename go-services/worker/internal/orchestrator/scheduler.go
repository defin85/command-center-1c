package orchestrator

import (
	"context"
	"fmt"
)

const (
	// API paths for scheduler endpoints
	pathSchedulerRunStart    = "/api/internal/scheduler/runs/start"
	pathSchedulerRunComplete = "/api/internal/scheduler/runs/%s/complete"
)

// SchedulerRunStart registers the start of a scheduled job execution.
// Returns the run ID for tracking.
func (c *Client) SchedulerRunStart(ctx context.Context, jobName, workerInstance string) (string, error) {
	return c.SchedulerRunStartWithConfig(ctx, jobName, workerInstance, nil)
}

// SchedulerRunStartWithConfig registers the start of a scheduled job with optional config.
// Returns the run ID for tracking.
func (c *Client) SchedulerRunStartWithConfig(ctx context.Context, jobName, workerInstance string, jobConfig map[string]interface{}) (string, error) {
	req := &SchedulerJobRunStartRequest{
		JobName:        jobName,
		WorkerInstance: workerInstance,
		JobConfig:      jobConfig,
	}

	var resp SchedulerJobRunResponse
	if err := c.post(ctx, pathSchedulerRunStart, req, &resp); err != nil {
		return "", fmt.Errorf("failed to start scheduler run: %w", err)
	}

	return resp.RunID, nil
}

// SchedulerRunComplete marks a scheduler job run as completed with results.
func (c *Client) SchedulerRunComplete(ctx context.Context, runID string, req *SchedulerJobRunCompleteRequest) error {
	if runID == "" {
		return fmt.Errorf("run ID is required")
	}
	if req == nil {
		return fmt.Errorf("complete request is required")
	}
	if req.Status == "" {
		return fmt.Errorf("status is required")
	}

	path := fmt.Sprintf(pathSchedulerRunComplete, runID)

	var resp SchedulerJobRunResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return fmt.Errorf("failed to complete scheduler run: %w", err)
	}

	return nil
}

// SchedulerRunSuccess is a convenience method to mark a run as successful.
func (c *Client) SchedulerRunSuccess(ctx context.Context, runID string, durationMs int64, summary string, processed, failed int) error {
	return c.SchedulerRunComplete(ctx, runID, &SchedulerJobRunCompleteRequest{
		Status:         "success",
		DurationMs:     durationMs,
		ResultSummary:  summary,
		ItemsProcessed: processed,
		ItemsFailed:    failed,
	})
}

// SchedulerRunFailed is a convenience method to mark a run as failed.
func (c *Client) SchedulerRunFailed(ctx context.Context, runID string, durationMs int64, errorMessage string) error {
	return c.SchedulerRunComplete(ctx, runID, &SchedulerJobRunCompleteRequest{
		Status:       "failed",
		DurationMs:   durationMs,
		ErrorMessage: errorMessage,
	})
}

// SchedulerRunSkipped is a convenience method to mark a run as skipped.
func (c *Client) SchedulerRunSkipped(ctx context.Context, runID string, reason string) error {
	return c.SchedulerRunComplete(ctx, runID, &SchedulerJobRunCompleteRequest{
		Status:        "skipped",
		ResultSummary: reason,
	})
}
