package orchestrator

import (
	"context"
	"fmt"
)

const (
	// API paths for task execution endpoints
	pathTaskStart    = "/api/v2/internal/start-task"
	pathTaskComplete = "/api/v2/internal/complete-task"
)

// TaskStart registers the start of a task execution.
// Returns the task ID for tracking.
func (c *Client) TaskStart(ctx context.Context, req *TaskExecutionStartRequest) (string, error) {
	if req == nil {
		return "", fmt.Errorf("task start request is required")
	}
	if req.OperationID == "" {
		return "", fmt.Errorf("operation ID is required")
	}
	if req.TaskType == "" {
		return "", fmt.Errorf("task type is required")
	}
	if req.TargetID == "" {
		return "", fmt.Errorf("target ID is required")
	}

	var resp TaskExecutionResponse
	if err := c.post(ctx, pathTaskStart, req, &resp); err != nil {
		return "", fmt.Errorf("failed to start task: %w", err)
	}
	return fmt.Sprintf("%d", resp.TaskID), nil
}

// TaskComplete marks a task execution as completed with results.
func (c *Client) TaskComplete(ctx context.Context, taskID string, req *TaskExecutionCompleteRequest) error {
	if taskID == "" {
		return fmt.Errorf("task ID is required")
	}
	if req == nil {
		return fmt.Errorf("complete request is required")
	}
	if req.Status == "" {
		return fmt.Errorf("status is required")
	}

	path := fmt.Sprintf("%s?task_id=%s", pathTaskComplete, taskID)

	var resp TaskExecutionResponse
	if err := c.post(ctx, path, req, &resp); err != nil {
		return fmt.Errorf("failed to complete task: %w", err)
	}

	return nil
}

// TaskSuccess is a convenience method to mark a task as successful.
func (c *Client) TaskSuccess(ctx context.Context, taskID string, durationMs int64, result map[string]interface{}) error {
	return c.TaskComplete(ctx, taskID, &TaskExecutionCompleteRequest{
		Status:     "success",
		DurationMs: durationMs,
		Result:     result,
	})
}

// TaskFailed is a convenience method to mark a task as failed.
func (c *Client) TaskFailed(ctx context.Context, taskID string, durationMs int64, errorMessage, errorCode string, retryCount int) error {
	return c.TaskComplete(ctx, taskID, &TaskExecutionCompleteRequest{
		Status:       "failed",
		DurationMs:   durationMs,
		ErrorMessage: errorMessage,
		ErrorCode:    errorCode,
		RetryCount:   retryCount,
	})
}

// TaskSkipped is a convenience method to mark a task as skipped.
func (c *Client) TaskSkipped(ctx context.Context, taskID string, reason string) error {
	return c.TaskComplete(ctx, taskID, &TaskExecutionCompleteRequest{
		Status:       "skipped",
		ErrorMessage: reason,
	})
}

// StartHealthCheckTask is a convenience method to start a health check task.
func (c *Client) StartHealthCheckTask(ctx context.Context, operationID, databaseID, workerInstance string) (string, error) {
	return c.TaskStart(ctx, &TaskExecutionStartRequest{
		OperationID:    operationID,
		TaskType:       "health_check",
		TargetID:       databaseID,
		TargetType:     "database",
		WorkerInstance: workerInstance,
	})
}

// StartLockInfobaseTask is a convenience method to start a lock infobase task.
func (c *Client) StartLockInfobaseTask(ctx context.Context, operationID, infobaseID, workerInstance string, params map[string]interface{}) (string, error) {
	return c.TaskStart(ctx, &TaskExecutionStartRequest{
		OperationID:    operationID,
		TaskType:       "lock_infobase",
		TargetID:       infobaseID,
		TargetType:     "infobase",
		WorkerInstance: workerInstance,
		Parameters:     params,
	})
}

// StartUnlockInfobaseTask is a convenience method to start an unlock infobase task.
func (c *Client) StartUnlockInfobaseTask(ctx context.Context, operationID, infobaseID, workerInstance string) (string, error) {
	return c.TaskStart(ctx, &TaskExecutionStartRequest{
		OperationID:    operationID,
		TaskType:       "unlock_infobase",
		TargetID:       infobaseID,
		TargetType:     "infobase",
		WorkerInstance: workerInstance,
	})
}
