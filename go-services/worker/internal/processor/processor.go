// go-services/worker/internal/processor/processor.go
package processor

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
)

// TaskProcessor handles task processing logic
type TaskProcessor struct {
	config       *config.Config
	credsClient  credentials.Fetcher
	odataClients map[string]*odata.Client // Cache clients per database
	clientsMutex sync.RWMutex
	workerID     string
}

// NewTaskProcessor creates a new task processor
func NewTaskProcessor(cfg *config.Config, credsClient credentials.Fetcher) *TaskProcessor {
	return &TaskProcessor{
		config:       cfg,
		credsClient:  credsClient,
		odataClients: make(map[string]*odata.Client),
		workerID:     cfg.WorkerID,
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

// getODataClient retrieves or creates OData client for database
func (p *TaskProcessor) getODataClient(creds *credentials.DatabaseCredentials) *odata.Client {
	p.clientsMutex.RLock()
	if client, exists := p.odataClients[creds.DatabaseID]; exists {
		p.clientsMutex.RUnlock()
		return client
	}
	p.clientsMutex.RUnlock()

	// Create new client
	p.clientsMutex.Lock()
	defer p.clientsMutex.Unlock()

	// Double-check after acquiring write lock
	if client, exists := p.odataClients[creds.DatabaseID]; exists {
		return client
	}

	client := odata.NewClient(odata.ClientConfig{
		BaseURL: creds.ODataURL,
		Auth: odata.Auth{
			Username: creds.Username,
			Password: creds.Password,
		},
		Timeout:       30 * time.Second,
		MaxRetries:    3,
		RetryWaitTime: 500 * time.Millisecond,
	})

	p.odataClients[creds.DatabaseID] = client
	return client
}

func (p *TaskProcessor) processSingleDatabase(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	// Special handling for extension installation (fetches credentials internally)
	if msg.OperationType == "install_extension" {
		result = p.executeExtensionInstall(ctx, msg, databaseID)
		result.DatabaseID = databaseID
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Fetch credentials for OData operations
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
	log := logger.GetLogger()
	client := p.getODataClient(creds)

	log.Infof("executing create operation, entity=%s, odata_url=%s", msg.Entity, creds.ODataURL)

	// Create entity via OData
	result, err := client.Create(ctx, msg.Entity, msg.Payload.Data)
	if err != nil {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     err.Error(),
			ErrorCode: categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		Success: true,
		Data:    result,
	}
}

func (p *TaskProcessor) executeUpdate(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := p.getODataClient(creds)

	// Extract entity ID from filters (expected format: {"entity_id": "guid'...'"})
	entityID, ok := msg.Payload.Filters["entity_id"].(string)
	if !ok || entityID == "" {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "entity_id is required in filters for update operation",
			ErrorCode: "VALIDATION_ERROR",
		}
	}

	log.Infof("executing update operation, entity=%s, id=%s", msg.Entity, entityID)

	// Update entity via OData
	err := client.Update(ctx, msg.Entity, entityID, msg.Payload.Data)
	if err != nil {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     err.Error(),
			ErrorCode: categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"updated": true,
		},
	}
}

func (p *TaskProcessor) executeDelete(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := p.getODataClient(creds)

	// Extract entity ID from filters
	entityID, ok := msg.Payload.Filters["entity_id"].(string)
	if !ok || entityID == "" {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "entity_id is required in filters for delete operation",
			ErrorCode: "VALIDATION_ERROR",
		}
	}

	log.Infof("executing delete operation, entity=%s, id=%s", msg.Entity, entityID)

	// Delete entity via OData
	err := client.Delete(ctx, msg.Entity, entityID)
	if err != nil {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     err.Error(),
			ErrorCode: categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"deleted": true,
		},
	}
}

func (p *TaskProcessor) executeQuery(ctx context.Context, msg *models.OperationMessage, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := p.getODataClient(creds)

	// Extract query parameters from options
	filter := ""
	if f, ok := msg.Payload.Options["filter"].(string); ok {
		filter = f
	}

	var selectFields []string
	if s, ok := msg.Payload.Options["select"].([]interface{}); ok {
		for _, field := range s {
			if fieldStr, ok := field.(string); ok {
				selectFields = append(selectFields, fieldStr)
			}
		}
	}

	top := 0
	if t, ok := msg.Payload.Options["top"].(float64); ok {
		top = int(t)
	}

	skip := 0
	if s, ok := msg.Payload.Options["skip"].(float64); ok {
		skip = int(s)
	}

	log.Infof("executing query operation, entity=%s, filter=%s", msg.Entity, filter)

	// Query entities via OData
	results, err := client.Query(ctx, odata.QueryRequest{
		Entity: msg.Entity,
		Filter: filter,
		Select: selectFields,
		Top:    top,
		Skip:   skip,
	})
	if err != nil {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     err.Error(),
			ErrorCode: categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"results": results,
			"count":   len(results),
		},
	}
}

// categorizeODataError categorizes OData error for result
func categorizeODataError(err error) string {
	if odataErr, ok := err.(*odata.ODataError); ok {
		return odataErr.Code
	}
	return "UNKNOWN_ERROR"
}
