// go-services/worker/internal/processor/processor.go
package processor

import (
	"context"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
)

// TaskProcessor handles task processing logic
type TaskProcessor struct {
	config      *config.Config
	credsClient *credentials.Client
	workerID    string
}

// NewTaskProcessor creates a new task processor
func NewTaskProcessor(cfg *config.Config, credsClient *credentials.Client) *TaskProcessor {
	return &TaskProcessor{
		config:      cfg,
		credsClient: credsClient,
		workerID:    cfg.WorkerID,
	}
}

// Process processes an operation message
func (p *TaskProcessor) Process(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Process each target database
	totalDatabases := len(msg.TargetDatabases)
	succeeded := 0
	failed := 0
	totalDuration := 0.0

	for i, databaseID := range msg.TargetDatabases {
		log.Infof("processing database %s, progress: %d%%", databaseID, (i+1)*100/totalDatabases)

		dbResult := p.processSingleDatabase(ctx, msg, databaseID)
		result.Results = append(result.Results, dbResult)

		if dbResult.Success {
			succeeded++
		} else {
			failed++
		}

		totalDuration += dbResult.Duration
	}

	// Calculate summary
	result.Summary = models.ResultSummary{
		Total:       totalDatabases,
		Succeeded:   succeeded,
		Failed:      failed,
		AvgDuration: totalDuration / float64(totalDatabases),
	}

	// Determine overall status
	if failed == 0 {
		result.Status = "completed"
	} else if succeeded == 0 {
		result.Status = "failed"
	} else {
		result.Status = "completed" // Partial success
	}

	// Check timeout
	if ctx.Err() == context.DeadlineExceeded {
		result.Status = "timeout"
	}

	return result
}

func (p *TaskProcessor) processSingleDatabase(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	// Fetch credentials
	creds, err := p.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Execute operation via OData
	switch msg.OperationType {
	case "create":
		result = p.executeCreate(ctx, msg, creds)
	case "update":
		result = p.executeUpdate(ctx, msg, creds)
	case "delete":
		result = p.executeDelete(ctx, msg, creds)
	case "query":
		result = p.executeQuery(ctx, msg, creds)
	default:
		result.Success = false
		result.Error = fmt.Sprintf("unknown operation type: %s", msg.OperationType)
		result.ErrorCode = "INVALID_OPERATION"
	}

	result.DatabaseID = databaseID
	result.Duration = time.Since(start).Seconds()

	return result
}

func (p *TaskProcessor) executeCreate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	// TODO: Implement OData POST
	// Placeholder implementation
	logger.Infof("executing create operation (stub), entity=%s, odata_url=%s", msg.Entity, creds.ODataURL)

	// Simulate work
	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"created": true,
			"entity":  msg.Entity,
		},
	}
}

func (p *TaskProcessor) executeUpdate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	// TODO: Implement OData PATCH/PUT
	logger.Info("executing update operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"updated": true,
		},
	}
}

func (p *TaskProcessor) executeDelete(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	// TODO: Implement OData DELETE
	logger.Info("executing delete operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"deleted": true,
		},
	}
}

func (p *TaskProcessor) executeQuery(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	// TODO: Implement OData GET
	logger.Info("executing query operation (stub)")

	time.Sleep(100 * time.Millisecond)

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"results": []interface{}{},
		},
	}
}
