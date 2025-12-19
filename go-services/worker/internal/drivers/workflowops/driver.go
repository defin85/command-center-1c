package workflowops

import (
	"context"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

type Driver struct {
	workerID       string
	eventPublisher *events.EventPublisher
	handler        *WorkflowHandler
	timeline       tracing.TimelineRecorder
}

func NewDriver(workerID string, publisher *events.EventPublisher, handler *WorkflowHandler, timeline tracing.TimelineRecorder) *Driver {
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}
	return &Driver{
		workerID:       workerID,
		eventPublisher: publisher,
		handler:        handler,
		timeline:       timeline,
	}
}

func (d *Driver) Name() string { return "workflow" }

func (d *Driver) OperationTypes() []string { return []string{"execute_workflow"} }

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage) (*models.OperationResultV2, error) {
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    d.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	log := logger.GetLogger()

	d.timeline.Record(ctx, msg.OperationID, "workflow.driver.started", map[string]interface{}{
		"operation_type": msg.OperationType,
	})

	if d.handler == nil {
		log.Errorf("workflow handler not initialized, cannot execute workflow: operation_id=%s", msg.OperationID)
		result.Status = "failed"
		result.Results = append(result.Results, models.DatabaseResultV2{
			DatabaseID: "workflow",
			Success:    false,
			Error:      "workflow handler not configured",
			ErrorCode:  "WORKFLOW_DISABLED",
			Duration:   time.Since(start).Seconds(),
		})
		result.Summary = models.ResultSummary{
			Total:       1,
			Succeeded:   0,
			Failed:      1,
			AvgDuration: time.Since(start).Seconds(),
		}
		d.timeline.Record(ctx, msg.OperationID, "workflow.driver.failed", map[string]interface{}{
			"operation_type": msg.OperationType,
			"error":          "workflow handler not configured",
			"duration_ms":    time.Since(start).Milliseconds(),
		})
		return result, nil
	}

	if d.eventPublisher != nil {
		if err := d.eventPublisher.PublishProcessing(ctx, msg.OperationID, "workflow", d.workerID); err != nil {
			log.Errorf("failed to publish PROCESSING event: %v", err)
		}
	}

	dbResult := d.handler.ExecuteWorkflow(ctx, msg)
	dbResult.DatabaseID = "workflow"
	result.Results = append(result.Results, dbResult)

	if dbResult.Success {
		result.Status = "completed"
		result.Summary = models.ResultSummary{
			Total:       1,
			Succeeded:   1,
			Failed:      0,
			AvgDuration: dbResult.Duration,
		}
		if d.eventPublisher != nil {
			if err := d.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
				log.Errorf("failed to publish SUCCESS event: %v", err)
			}
		}
		d.timeline.Record(ctx, msg.OperationID, "workflow.driver.completed", map[string]interface{}{
			"operation_type": msg.OperationType,
			"duration_ms":    time.Since(start).Milliseconds(),
		})
		return result, nil
	}

	result.Status = "failed"
	result.Summary = models.ResultSummary{
		Total:       1,
		Succeeded:   0,
		Failed:      1,
		AvgDuration: dbResult.Duration,
	}
	if d.eventPublisher != nil {
		if err := d.eventPublisher.PublishFailed(ctx, msg.OperationID, dbResult.Error); err != nil {
			log.Errorf("failed to publish FAILED event: %v", err)
		}
	}

	d.timeline.Record(ctx, msg.OperationID, "workflow.driver.failed", map[string]interface{}{
		"operation_type": msg.OperationType,
		"error":          dbResult.Error,
		"duration_ms":    time.Since(start).Milliseconds(),
	})

	return result, nil
}
