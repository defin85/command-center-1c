// Package processor provides operation processing handlers for the Worker.
// ras_handler.go implements RAS operations handler for Phase 4 - Context Menu Actions.
package processor

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
	"github.com/commandcenter1c/commandcenter/worker/internal/rasadapter"
)

// RAS operation types supported by this handler
const (
	OpLockScheduledJobs   = "lock_scheduled_jobs"
	OpUnlockScheduledJobs = "unlock_scheduled_jobs"
	OpBlockSessions       = "block_sessions"
	OpUnblockSessions     = "unblock_sessions"
	OpTerminateSessions   = "terminate_sessions"

	// maxConcurrentRASOperations limits parallel RAS API calls to prevent overload
	maxConcurrentRASOperations = 20

	// maxBatchOperationTimeout limits total time for batch RAS operation
	maxBatchOperationTimeout = 5 * time.Minute
)

// IsRASOperation checks if operation type is a RAS operation
func IsRASOperation(opType string) bool {
	switch opType {
	case OpLockScheduledJobs, OpUnlockScheduledJobs, OpBlockSessions, OpUnblockSessions, OpTerminateSessions:
		return true
	default:
		return false
	}
}

// RASHandler processes RAS operations (lock, unlock, block, terminate)
type RASHandler struct {
	client          *rasadapter.Client
	clusterResolver ClusterInfoResolver
	eventPublisher  *events.EventPublisher
	workerID        string
}

// NewRASHandler creates a new RAS operations handler
func NewRASHandler(rasAdapterURL string, clusterResolver ClusterInfoResolver, eventPublisher *events.EventPublisher, workerID string) (*RASHandler, error) {
	client, err := rasadapter.NewClientWithConfig(rasadapter.ClientConfig{
		BaseURL:     rasAdapterURL,
		Timeout:     30 * time.Second,
		MaxRetries:  3,
		BaseBackoff: 500 * time.Millisecond,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create RAS adapter client: %w", err)
	}

	return &RASHandler{
		client:          client,
		clusterResolver: clusterResolver,
		eventPublisher:  eventPublisher,
		workerID:        workerID,
	}, nil
}

// RASOperationResult holds the result for a single database RAS operation
type RASOperationResult struct {
	DatabaseID   string  `json:"database_id"`
	DatabaseName string  `json:"database_name,omitempty"`
	ClusterID    string  `json:"cluster_id,omitempty"`
	InfobaseID   string  `json:"infobase_id,omitempty"`
	Success      bool    `json:"success"`
	Error        string  `json:"error,omitempty"`
	Duration     float64 `json:"duration_seconds"`
}

// BlockSessionsConfig contains optional parameters for BlockSessions operation
type BlockSessionsConfig struct {
	Message        string `json:"message,omitempty"`
	PermissionCode string `json:"permission_code,omitempty"`
	DeniedFrom     string `json:"denied_from,omitempty"`
	DeniedTo       string `json:"denied_to,omitempty"`
}

// Process executes RAS operation for all target databases in parallel
func (h *RASHandler) Process(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()

	log.WithFields(map[string]interface{}{
		"operation_id":   msg.OperationID,
		"operation_type": msg.OperationType,
		"target_count":   len(msg.TargetDatabases),
	}).Info("Processing RAS operation")

	// Publish PROCESSING event
	if h.eventPublisher != nil {
		if err := h.eventPublisher.PublishProcessing(ctx, msg.OperationID, "ras", h.workerID); err != nil {
			log.WithFields(map[string]interface{}{
				"operation_id": msg.OperationID,
				"error":        err,
			}).Error("failed to publish PROCESSING event")
		}
	}

	if len(msg.TargetDatabases) == 0 {
		return h.emptyResult(msg.OperationID)
	}

	// Create cancellable context with timeout for entire batch
	batchCtx, batchCancel := context.WithTimeout(ctx, maxBatchOperationTimeout)
	defer batchCancel()

	// Extract block sessions config if applicable
	var blockConfig *BlockSessionsConfig
	if msg.OperationType == OpBlockSessions {
		blockConfig = h.extractBlockSessionsConfig(msg)
	}

	// Process all databases in parallel with limited concurrency
	results := make([]RASOperationResult, len(msg.TargetDatabases))
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Semaphore to limit concurrent RAS operations
	sem := make(chan struct{}, maxConcurrentRASOperations)

	for i, dbTarget := range msg.TargetDatabases {
		wg.Add(1)
		go func(idx int, target models.TargetDatabase) {
			defer wg.Done()

			result := h.processDatabaseWithCancellation(
				batchCtx, sem, msg.OperationType, target, blockConfig,
			)

			mu.Lock()
			results[idx] = result
			mu.Unlock()
		}(i, dbTarget)
	}

	// Wait with timeout protection (prevents hanging on stuck goroutines)
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// All goroutines completed normally
	case <-batchCtx.Done():
		log.WithFields(map[string]interface{}{
			"operation_id": msg.OperationID,
			"reason":       batchCtx.Err(),
		}).Warn("Batch operation context cancelled, some results may be incomplete")
	}

	// Calculate summary and convert results
	result := h.buildResult(msg.OperationID, results)

	// Publish SUCCESS/FAILED event based on result
	if h.eventPublisher != nil {
		if result.Summary.Failed == 0 {
			if err := h.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
				log.WithFields(map[string]interface{}{
					"operation_id": msg.OperationID,
					"error":        err,
				}).Error("failed to publish SUCCESS event")
			}
		} else {
			errorMsg := fmt.Sprintf("RAS operation failed for %d/%d databases", result.Summary.Failed, result.Summary.Total)
			if err := h.eventPublisher.PublishFailed(ctx, msg.OperationID, errorMsg); err != nil {
				log.WithFields(map[string]interface{}{
					"operation_id": msg.OperationID,
					"error":        err,
				}).Error("failed to publish FAILED event")
			}
		}
	}

	return result
}

// processDatabaseWithCancellation handles single database with proper cancellation checks
func (h *RASHandler) processDatabaseWithCancellation(
	ctx context.Context,
	sem chan struct{},
	opType string,
	dbTarget models.TargetDatabase,
	blockConfig *BlockSessionsConfig,
) RASOperationResult {
	log := logger.GetLogger()
	start := time.Now()

	// Check cancellation BEFORE acquiring semaphore
	if err := ctx.Err(); err != nil {
		return RASOperationResult{
			DatabaseID: dbTarget.ID,
			Success:    false,
			Error:      fmt.Sprintf("cancelled before start: %v", err),
			Duration:   time.Since(start).Seconds(),
		}
	}

	// Acquire semaphore with cancellation support
	select {
	case sem <- struct{}{}:
		defer func() { <-sem }()
	case <-ctx.Done():
		return RASOperationResult{
			DatabaseID: dbTarget.ID,
			Success:    false,
			Error:      fmt.Sprintf("cancelled while waiting for semaphore: %v", ctx.Err()),
			Duration:   time.Since(start).Seconds(),
		}
	}

	// Check cancellation AFTER acquiring semaphore (CRITICAL FIX for race condition)
	if err := ctx.Err(); err != nil {
		log.WithFields(map[string]interface{}{
			"database_id": dbTarget.ID,
			"operation":   opType,
		}).Debug("Context cancelled after semaphore acquisition, skipping RAS call")

		return RASOperationResult{
			DatabaseID: dbTarget.ID,
			Success:    false,
			Error:      fmt.Sprintf("cancelled after semaphore: %v", err),
			Duration:   time.Since(start).Seconds(),
		}
	}

	// Execute the actual operation
	return h.processSingleDatabase(ctx, opType, dbTarget, blockConfig)
}

// emptyResult creates result for empty target list
func (h *RASHandler) emptyResult(operationID string) *models.OperationResultV2 {
	return &models.OperationResultV2{
		OperationID: operationID,
		Status:      "failed",
		WorkerID:    "",
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
		Summary: models.ResultSummary{
			Total:  0,
			Failed: 0,
		},
	}
}

// processSingleDatabase executes RAS operation for a single database
func (h *RASHandler) processSingleDatabase(ctx context.Context, opType string, dbTarget models.TargetDatabase, blockConfig *BlockSessionsConfig) RASOperationResult {
	log := logger.GetLogger()
	start := time.Now()

	result := RASOperationResult{
		DatabaseID:   dbTarget.ID,
		DatabaseName: dbTarget.Name,
	}

	// Check context before expensive operations
	if err := ctx.Err(); err != nil {
		result.Success = false
		result.Error = fmt.Sprintf("context cancelled: %v", err)
		result.Duration = time.Since(start).Seconds()
		return result
	}

	var clusterID, infobaseID string

	// Use ClusterID/RASInfobaseID from TargetDatabase if provided, otherwise resolve
	if dbTarget.ClusterID != "" && dbTarget.RASInfobaseID != "" {
		clusterID = dbTarget.ClusterID
		infobaseID = dbTarget.RASInfobaseID

		log.WithFields(map[string]interface{}{
			"database_id": dbTarget.ID,
			"cluster_id":  clusterID,
			"infobase_id": infobaseID,
		}).Debug("Using pre-resolved cluster info from TargetDatabase")
	} else {
		// Resolve cluster info (cluster_id, infobase_id) from database_id
		clusterInfo, err := h.clusterResolver.Resolve(ctx, dbTarget.ID)
		if err != nil {
			result.Success = false
			// Differentiate cancellation errors
			if ctx.Err() != nil {
				result.Error = fmt.Sprintf("cancelled during cluster resolution: %v", ctx.Err())
			} else {
				result.Error = fmt.Sprintf("failed to resolve cluster info: %v", err)
			}
			result.Duration = time.Since(start).Seconds()

			log.WithFields(map[string]interface{}{
				"database_id": dbTarget.ID,
				"error":       err,
			}).Error("Failed to resolve cluster info for RAS operation")

			return result
		}

		clusterID = clusterInfo.ClusterID
		infobaseID = clusterInfo.InfobaseID
	}

	result.ClusterID = clusterID
	result.InfobaseID = infobaseID
	// Use database name from target if available, otherwise use ID
	if result.DatabaseName == "" {
		result.DatabaseName = dbTarget.ID
	}

	// Final cancellation check before RAS call
	if err := ctx.Err(); err != nil {
		result.Success = false
		result.Error = fmt.Sprintf("cancelled before RAS call: %v", err)
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Execute the operation
	var err error
	switch opType {
	case OpLockScheduledJobs:
		_, err = h.client.LockScheduledJobs(ctx, clusterID, infobaseID, nil)
	case OpUnlockScheduledJobs:
		_, err = h.client.UnlockScheduledJobs(ctx, clusterID, infobaseID, nil)
	case OpBlockSessions:
		req := h.buildBlockSessionsRequest(blockConfig)
		_, err = h.client.BlockSessions(ctx, clusterID, infobaseID, req)
	case OpUnblockSessions:
		_, err = h.client.UnblockSessions(ctx, clusterID, infobaseID, nil)
	case OpTerminateSessions:
		_, err = h.client.TerminateAllSessions(ctx, clusterID, infobaseID)
	default:
		err = fmt.Errorf("unknown RAS operation type: %s", opType)
	}

	result.Duration = time.Since(start).Seconds()

	if err != nil {
		result.Success = false
		// Differentiate cancellation errors
		if ctx.Err() != nil {
			result.Error = fmt.Sprintf("cancelled during RAS operation: %v", ctx.Err())
		} else {
			result.Error = err.Error()
		}

		log.WithFields(map[string]interface{}{
			"database_id":    dbTarget.ID,
			"cluster_id":     clusterID,
			"infobase_id":    infobaseID,
			"operation_type": opType,
			"error":          err,
			"duration":       result.Duration,
		}).Error("RAS operation failed")
	} else {
		result.Success = true

		log.WithFields(map[string]interface{}{
			"database_id":    dbTarget.ID,
			"cluster_id":     clusterID,
			"infobase_id":    infobaseID,
			"operation_type": opType,
			"duration":       result.Duration,
		}).Info("RAS operation succeeded")
	}

	return result
}

// extractBlockSessionsConfig extracts block sessions configuration from operation message
func (h *RASHandler) extractBlockSessionsConfig(msg *models.OperationMessage) *BlockSessionsConfig {
	if msg.Payload.Data == nil {
		return nil
	}

	config := &BlockSessionsConfig{}

	if v, ok := msg.Payload.Data["message"].(string); ok {
		config.Message = v
	}
	if v, ok := msg.Payload.Data["permission_code"].(string); ok {
		config.PermissionCode = v
	}
	if v, ok := msg.Payload.Data["denied_from"].(string); ok {
		config.DeniedFrom = v
	}
	if v, ok := msg.Payload.Data["denied_to"].(string); ok {
		config.DeniedTo = v
	}

	return config
}

// buildBlockSessionsRequest converts BlockSessionsConfig to rasadapter.BlockSessionsRequest
func (h *RASHandler) buildBlockSessionsRequest(config *BlockSessionsConfig) *rasadapter.BlockSessionsRequest {
	if config == nil {
		return nil
	}

	return &rasadapter.BlockSessionsRequest{
		DeniedMessage:  config.Message,
		PermissionCode: config.PermissionCode,
		DeniedFrom:     config.DeniedFrom,
		DeniedTo:       config.DeniedTo,
	}
}

// buildResult converts RAS operation results to OperationResultV2
func (h *RASHandler) buildResult(operationID string, results []RASOperationResult) *models.OperationResultV2 {
	succeeded := 0
	failed := 0
	totalDuration := 0.0

	dbResults := make([]models.DatabaseResultV2, len(results))

	for i, r := range results {
		if r.Success {
			succeeded++
		} else {
			failed++
		}
		totalDuration += r.Duration

		dbResults[i] = models.DatabaseResultV2{
			DatabaseID: r.DatabaseID,
			Success:    r.Success,
			Error:      r.Error,
			Duration:   r.Duration,
			Data: map[string]interface{}{
				"cluster_id":    r.ClusterID,
				"infobase_id":   r.InfobaseID,
				"database_name": r.DatabaseName,
			},
		}
	}

	// Determine overall status
	status := "completed"
	if succeeded == 0 && failed > 0 {
		status = "failed"
	}

	avgDuration := 0.0
	if len(results) > 0 {
		avgDuration = totalDuration / float64(len(results))
	}

	return &models.OperationResultV2{
		OperationID: operationID,
		Status:      status,
		Timestamp:   time.Now(),
		Results:     dbResults,
		Summary: models.ResultSummary{
			Total:       len(results),
			Succeeded:   succeeded,
			Failed:      failed,
			AvgDuration: avgDuration,
		},
	}
}

// GetClient returns the underlying RAS adapter client for advanced operations
func (h *RASHandler) GetClient() *rasadapter.Client {
	return h.client
}

// HealthCheck verifies connectivity to RAS Adapter
func (h *RASHandler) HealthCheck(ctx context.Context) error {
	_, err := h.client.Health(ctx)
	if err != nil {
		return fmt.Errorf("RAS adapter health check failed: %w", err)
	}
	return nil
}
