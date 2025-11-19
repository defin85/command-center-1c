// go-services/worker/internal/processor/dual_mode.go
package processor

import (
	"context"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/config"
)

// ExecutionMode represents execution mode (Event-Driven vs HTTP Sync)
type ExecutionMode string

const (
	ModeEventDriven ExecutionMode = "event_driven"
	ModeHTTPSync    ExecutionMode = "http_sync"
)

// DualModeProcessor handles dual-mode execution
type DualModeProcessor struct {
	featureFlags *config.FeatureFlags
	processor    *TaskProcessor
}

// NewDualModeProcessor creates new DualModeProcessor instance
func NewDualModeProcessor(ff *config.FeatureFlags, processor *TaskProcessor) *DualModeProcessor {
	return &DualModeProcessor{
		featureFlags: ff,
		processor:    processor,
	}
}

// ProcessExtensionInstall processes extension installation with dual-mode support
func (dm *DualModeProcessor) ProcessExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()
	log := logger.GetLogger()

	// Determine execution mode
	mode := dm.determineExecutionMode(msg.OperationType, databaseID)

	log.Infof("processing extension install: operation_id=%s, database_id=%s, mode=%s",
		msg.OperationID, databaseID, string(mode))

	// Record decision metrics (if metrics enabled)
	metrics.ExecutionMode.WithLabelValues(string(mode)).Inc()

	// Execute based on mode
	var result models.DatabaseResultV2
	var err error

	if mode == ModeEventDriven {
		result, err = dm.processEventDriven(ctx, msg, databaseID)
	} else {
		result, err = dm.processHTTPSync(ctx, msg, databaseID)
	}

	// Record metrics
	duration := time.Since(start)
	durationSeconds := duration.Seconds()
	metrics.ExecutionDuration.WithLabelValues(string(mode)).Observe(durationSeconds)

	if err != nil {
		metrics.ExecutionFailure.WithLabelValues(string(mode)).Inc()
		log.Errorf("execution failed: mode=%s, error=%v, duration=%v",
			string(mode), err, duration)

		// Return error result
		result = models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("%s mode failed: %v", mode, err),
			ErrorCode:  "EXECUTION_ERROR",
			Duration:   duration.Seconds(),
		}
	} else {
		metrics.ExecutionSuccess.WithLabelValues(string(mode)).Inc()
		log.Infof("execution completed: mode=%s, success=%v, duration=%v",
			string(mode), result.Success, duration)
	}

	return result
}

// determineExecutionMode determines which execution mode to use
func (dm *DualModeProcessor) determineExecutionMode(operationType string, databaseID string) ExecutionMode {
	// Normalize operation type
	normalizedOpType := operationType
	if operationType == "install_extension" {
		normalizedOpType = "extension"
	}

	// Check feature flags
	if dm.featureFlags.ShouldUseEventDriven(normalizedOpType, databaseID) {
		return ModeEventDriven
	}

	return ModeHTTPSync
}

// validateExtensionInstallParams validates extension installation parameters
func validateExtensionInstallParams(data map[string]interface{}) (extensionName, extensionPath, databaseID string, err error) {
	// Validate extension_name
	extensionName, ok := data["extension_name"].(string)
	if !ok || extensionName == "" {
		return "", "", "", fmt.Errorf("extension_name is required")
	}

	// Length validation
	if len(extensionName) > 255 {
		return "", "", "", fmt.Errorf("extension_name too long (max 255 chars): %d", len(extensionName))
	}

	// Format validation (alphanumeric + underscore/dash only)
	validNamePattern := regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)
	if !validNamePattern.MatchString(extensionName) {
		return "", "", "", fmt.Errorf("extension_name contains invalid characters: %s", extensionName)
	}

	// Validate extension_path
	extensionPath, ok = data["extension_path"].(string)
	if !ok || extensionPath == "" {
		return "", "", "", fmt.Errorf("extension_path is required")
	}

	// Path traversal protection
	cleanPath := filepath.Clean(extensionPath)
	if strings.Contains(cleanPath, "..") {
		return "", "", "", fmt.Errorf("path traversal detected in extension_path: %s", extensionPath)
	}

	// Length validation
	if len(extensionPath) > 1024 {
		return "", "", "", fmt.Errorf("extension_path too long (max 1024 chars): %d", len(extensionPath))
	}

	// Validate database_id (if present in data, for processEventDriven it comes from msg)
	if dbID, ok := data["database_id"].(string); ok {
		if dbID == "" {
			return "", "", "", fmt.Errorf("database_id cannot be empty")
		}
		databaseID = dbID
	}

	return extensionName, extensionPath, databaseID, nil
}

// processEventDriven executes through Event-Driven State Machine
func (dm *DualModeProcessor) processEventDriven(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	log := logger.GetLogger()

	log.Infof("executing via Event-Driven State Machine: operation_id=%s, database_id=%s",
		msg.OperationID, databaseID)

	// Validate parameters
	_, _, _, err := validateExtensionInstallParams(msg.Payload.Data)
	if err != nil {
		return models.DatabaseResultV2{}, err
	}

	// NOTE: This is a simplified version for Task 3.2.1
	// Full State Machine integration requires Redis Pub/Sub setup (from Task 2.1)
	correlationID := fmt.Sprintf("%s-%s-%d", msg.OperationID, databaseID, time.Now().UnixNano())

	// TODO: Initialize real EventPublisher and EventSubscriber (from Task 2.1)
	// For now, this is a placeholder that shows the integration pattern
	log.Warnf("Event-Driven mode selected but State Machine integration not fully implemented: correlation_id=%s, operation_id=%s, database_id=%s",
		correlationID, msg.OperationID, databaseID)

	// Fallback to HTTP Sync for now
	log.Infof("falling back to HTTP Sync mode (Event-Driven not fully implemented yet)")
	return dm.processHTTPSync(ctx, msg, databaseID)

	// FUTURE: Full State Machine integration
	/*
	sm, err := statemachine.NewStateMachine(
		ctx,
		msg.OperationID,
		databaseID,
		correlationID,
		publisher,   // TODO: Get from TaskProcessor
		subscriber,  // TODO: Get from TaskProcessor
		redisClient, // TODO: Get from TaskProcessor
		smConfig,    // TODO: Load from config
	)
	if err != nil {
		return models.DatabaseResultV2{}, fmt.Errorf("failed to create state machine: %w", err)
	}

	// Set workflow data
	sm.ClusterID = clusterInfo.ClusterID
	sm.InfobaseID = clusterInfo.InfobaseID
	sm.ExtensionPath = extensionPath
	sm.ExtensionName = extensionName

	// Run State Machine
	if err := sm.Run(ctx); err != nil {
		return models.DatabaseResultV2{}, fmt.Errorf("state machine failed: %w", err)
	}

	// Get final state
	finalState := sm.GetState()

	// Build result based on final state
	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	if finalState == statemachine.StateCompleted {
		result.Success = true
		result.Data = map[string]interface{}{
			"extension_name": extensionName,
			"mode":           "event_driven",
			"correlation_id": correlationID,
		}
	} else {
		result.Success = false
		result.Error = fmt.Sprintf("state machine ended in state: %s", finalState)
		result.ErrorCode = "STATE_MACHINE_ERROR"
	}

	return result, nil
	*/
}

// processHTTPSync executes through HTTP Sync calls (legacy mode)
func (dm *DualModeProcessor) processHTTPSync(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	log := logger.GetLogger()

	log.Infof("executing via HTTP Sync (legacy mode): operation_id=%s, database_id=%s",
		msg.OperationID, databaseID)

	// Use existing executeExtensionInstall method
	result := dm.processor.executeExtensionInstall(ctx, msg, databaseID)

	// Check for errors
	if !result.Success {
		return result, fmt.Errorf("HTTP Sync execution failed: %s", result.Error)
	}

	return result, nil
}

// GetFeatureFlags returns current feature flags configuration
func (dm *DualModeProcessor) GetFeatureFlags() map[string]interface{} {
	return dm.featureFlags.GetConfig()
}

// ReloadFeatureFlags hot-reloads feature flags from environment
func (dm *DualModeProcessor) ReloadFeatureFlags() error {
	log := logger.GetLogger()
	log.Infof("reloading feature flags from environment")
	return dm.featureFlags.Reload()
}

// Metrics recording functions (placeholder - to be implemented with Prometheus)




