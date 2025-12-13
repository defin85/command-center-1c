// go-services/worker/internal/processor/dual_mode.go
package processor

import (
	"context"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/commandcenter1c/commandcenter/worker/internal/statemachine"
)

// ExecutionMode represents execution mode (Event-Driven only since Phase 3)
type ExecutionMode string

const (
	ModeEventDriven ExecutionMode = "event_driven"
)

// DualModeProcessor handles dual-mode execution
type DualModeProcessor struct {
	featureFlags    *config.FeatureFlags
	processor       *TaskProcessor
	smConfig        *statemachine.Config    // State Machine configuration
	clusterResolver ClusterInfoResolver     // Resolver for cluster/infobase IDs
}

// NewDualModeProcessor creates new DualModeProcessor instance
func NewDualModeProcessor(ff *config.FeatureFlags, processor *TaskProcessor) *DualModeProcessor {
	log := logger.GetLogger()

	// Load State Machine config from environment
	// Pass nil for logger since logrus doesn't implement zap interface
	// Config loading will skip debug logging
	smConfig := statemachine.LoadFromEnv(nil)

	// Initialize ClusterInfoResolver
	// Uses OrchestratorClusterResolver with Redis caching if available
	var clusterResolver ClusterInfoResolver
	resolverCfg := DefaultResolverConfig()

	if processor != nil && processor.GetRedisClient() != nil {
		resolverCfg.RedisClient = processor.GetRedisClient()
	}

	if resolverCfg.OrchestratorURL != "" {
		clusterResolver = NewOrchestratorClusterResolver(resolverCfg)
		log.Info("ClusterInfoResolver initialized with OrchestratorClusterResolver")
	} else {
		clusterResolver = &NullClusterResolver{}
		log.Warn("ClusterInfoResolver not configured (OrchestratorURL is empty), Event-Driven mode will fail")
	}

	log.Info("DualModeProcessor initialized with State Machine config")

	return &DualModeProcessor{
		featureFlags:    ff,
		processor:       processor,
		smConfig:        smConfig,
		clusterResolver: clusterResolver,
	}
}

// ProcessExtensionInstall processes extension installation via Event-Driven State Machine
// HTTP Sync mode has been removed in Phase 3 cleanup
func (dm *DualModeProcessor) ProcessExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()
	log := logger.GetLogger()

	mode := ModeEventDriven

	log.Infof("processing extension install: operation_id=%s, database_id=%s, mode=%s",
		msg.OperationID, databaseID, string(mode))

	// Record decision metrics (if metrics enabled)
	metrics.ExecutionMode.WithLabelValues(string(mode)).Inc()

	// Execute via Event-Driven State Machine (only mode since Phase 3)
	result, err := dm.processEventDriven(ctx, msg, databaseID)

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

	// Format validation (allow Unicode letters, digits, underscore/dash/space)
	// Allow Cyrillic and other Unicode characters for extension names
	validNamePattern := regexp.MustCompile(`^[\p{L}\p{N}_\- ]+$`)
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
// This is the REAL implementation - NO fallback to HTTP Sync!
func (dm *DualModeProcessor) processEventDriven(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	log := logger.GetLogger()
	start := time.Now()

	log.Infof("[Event-Driven] Starting State Machine execution: operation_id=%s, database_id=%s",
		msg.OperationID, databaseID)

	// Step 1: Validate parameters
	extensionName, extensionPath, _, err := validateExtensionInstallParams(msg.Payload.Data)
	if err != nil {
		log.Errorf("[Event-Driven] Parameter validation failed: %v", err)
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("parameter validation failed: %v", err),
			ErrorCode:  "VALIDATION_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, err
	}

	log.Infof("[Event-Driven] Parameters validated: extension_name=%s, extension_path=%s",
		extensionName, extensionPath)

	// Step 2: Generate correlation ID for this workflow
	correlationID := fmt.Sprintf("%s-%s-%d", msg.OperationID, databaseID, time.Now().UnixNano())

	log.Infof("[Event-Driven] Generated correlation_id=%s", correlationID)

	// Step 3: Resolve cluster info from Orchestrator (NO fallback!)
	resolveStart := time.Now()
	clusterInfo, err := dm.clusterResolver.Resolve(ctx, databaseID)
	resolveDuration := time.Since(resolveStart)
	metrics.RecordClusterResolveDuration(resolveDuration.Seconds())

	if err != nil {
		log.Errorf("[Event-Driven] Failed to resolve cluster info: database_id=%s, error=%v, duration=%v",
			databaseID, err, resolveDuration)
		// NO fallback - return error directly
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to resolve cluster info: %v", err),
			ErrorCode:  "CLUSTER_RESOLVE_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, fmt.Errorf("failed to resolve cluster info for database %s: %w", databaseID, err)
	}

	log.Infof("[Event-Driven] Cluster info resolved: database_id=%s, cluster_id=%s, infobase_id=%s, duration=%v",
		databaseID, clusterInfo.ClusterID, clusterInfo.InfobaseID, resolveDuration)

	// Step 4: Create State Machine
	sm, err := dm.createStateMachine(
		ctx,
		msg.OperationID,
		databaseID,
		correlationID,
		clusterInfo,
		extensionName,
		extensionPath,
	)
	if err != nil {
		metrics.RecordStateMachineCreated(false)
		log.Errorf("[Event-Driven] Failed to create State Machine: operation_id=%s, error=%v",
			msg.OperationID, err)
		// NO fallback - return error directly
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to create state machine: %v", err),
			ErrorCode:  "STATE_MACHINE_CREATE_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, fmt.Errorf("failed to create state machine: %w", err)
	}

	metrics.RecordStateMachineCreated(true)
	log.Infof("[Event-Driven] State Machine created: sm_id=%s, correlation_id=%s",
		sm.ID, correlationID)

	// Step 5: Run State Machine
	log.Infof("[Event-Driven] Running State Machine: sm_id=%s", sm.ID)
	runErr := sm.Run(ctx)

	// Critical #2 Fix: Ensure publisher is closed after SM completes (success or failure)
	// Publisher is created per-SM in createStateMachine, so we must clean it up here
	defer func() {
		if closeErr := sm.ClosePublisher(); closeErr != nil {
			log.Warnf("[Event-Driven] Failed to close publisher for SM %s: %v", sm.ID, closeErr)
		}
	}()

	// Get final state BEFORE closing (important!)
	finalState := sm.State
	smDuration := time.Since(start)

	log.Infof("[Event-Driven] State Machine finished: sm_id=%s, final_state=%s, duration=%v, error=%v",
		sm.ID, finalState, smDuration, runErr)

	// Record State Machine final state metric
	metrics.RecordStateMachineFinalState(string(finalState))

	// Step 6: Build result based on final state
	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
		Duration:   smDuration.Seconds(),
	}

	// Check final state to determine success/failure
	if finalState == statemachine.StateCompleted {
		result.Success = true
		result.Data = map[string]interface{}{
			"extension_name": extensionName,
			"extension_path": extensionPath,
			"mode":           "event_driven",
			"correlation_id": correlationID,
			"cluster_id":     clusterInfo.ClusterID,
			"infobase_id":    clusterInfo.InfobaseID,
			"final_state":    string(finalState),
		}
		log.Infof("[Event-Driven] Operation completed successfully: operation_id=%s, database_id=%s",
			msg.OperationID, databaseID)
	} else {
		result.Success = false
		result.ErrorCode = "STATE_MACHINE_ERROR"

		// Build error message based on state and run error
		if runErr != nil {
			result.Error = fmt.Sprintf("state machine failed in state '%s': %v", finalState, runErr)
		} else {
			result.Error = fmt.Sprintf("state machine ended in unexpected state: %s", finalState)
		}

		// Add additional context to Data for debugging
		result.Data = map[string]interface{}{
			"mode":           "event_driven",
			"correlation_id": correlationID,
			"final_state":    string(finalState),
		}

		log.Errorf("[Event-Driven] Operation failed: operation_id=%s, database_id=%s, final_state=%s, error=%s",
			msg.OperationID, databaseID, finalState, result.Error)

		// If SM reached Compensating state, compensation was executed
		if finalState == statemachine.StateFailed {
			log.Infof("[Event-Driven] State Machine executed compensation actions before failing")
		}
	}

	// Note: Metrics for Event-Driven execution are recorded in ProcessExtensionInstall()
	// Additional SM-specific metrics can be added here if needed

	return result, runErr
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

// GetClusterResolver returns the ClusterInfoResolver instance
func (dm *DualModeProcessor) GetClusterResolver() ClusterInfoResolver {
	return dm.clusterResolver
}

// SetClusterResolver sets a custom ClusterInfoResolver (useful for testing)
func (dm *DualModeProcessor) SetClusterResolver(resolver ClusterInfoResolver) {
	dm.clusterResolver = resolver
}

// ResolveClusterInfo resolves cluster info for a database ID
// This is a convenience method that wraps clusterResolver.Resolve
func (dm *DualModeProcessor) ResolveClusterInfo(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	if dm.clusterResolver == nil {
		return nil, fmt.Errorf("ClusterInfoResolver not configured")
	}
	return dm.clusterResolver.Resolve(ctx, databaseID)
}

// --- State Machine Factory ---

// Note: ClusterInfo is defined in cluster_resolver.go

// publisherWrapper wraps shared/events.Publisher to implement statemachine.EventPublisher
type publisherWrapper struct {
	publisher *events.Publisher
}

// Publish implements statemachine.EventPublisher
func (pw *publisherWrapper) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	return pw.publisher.Publish(ctx, channel, eventType, payload, correlationID)
}

// Close implements statemachine.EventPublisher
func (pw *publisherWrapper) Close() error {
	return pw.publisher.Close()
}

// subscriberWrapper wraps shared/events.Subscriber to implement statemachine.EventSubscriber
// IMPORTANT: This wrapper does NOT close the underlying subscriber because it's shared
// across multiple State Machines and managed by TaskProcessor
type subscriberWrapper struct {
	subscriber *events.Subscriber
}

// Subscribe implements statemachine.EventSubscriber
func (sw *subscriberWrapper) Subscribe(channel string, handler events.HandlerFunc) error {
	return sw.subscriber.Subscribe(channel, handler)
}

// Close implements statemachine.EventSubscriber
// DO NOT close shared subscriber - it's managed by TaskProcessor
func (sw *subscriberWrapper) Close() error {
	// Critical #1 Fix: shared subscriber lifecycle is managed by TaskProcessor,
	// not by individual State Machines. Closing here would break all other SMs.
	return nil
}

// createStateMachine creates a new ExtensionInstallStateMachine instance
// Returns error if required dependencies are not available
func (dm *DualModeProcessor) createStateMachine(
	ctx context.Context,
	operationID string,
	databaseID string,
	correlationID string,
	clusterInfo *ClusterInfo,
	extensionName string,
	extensionPath string,
) (*statemachine.ExtensionInstallStateMachine, error) {
	log := logger.GetLogger()

	// Get dependencies from TaskProcessor
	redisClient := dm.processor.GetRedisClient()
	subscriber := dm.processor.GetEventSubscriber()

	// Check subscriber availability (graceful degradation)
	if subscriber == nil {
		log.Warnf("event subscriber not available, State Machine cannot be created: operation_id=%s, database_id=%s",
			operationID, databaseID)
		return nil, fmt.Errorf("event subscriber not available for State Machine")
	}

	// Create publisher for State Machine
	// Note: We create a new publisher instance for each State Machine
	// to ensure proper isolation and cleanup
	publisher, err := events.NewPublisher(redisClient, "worker-state-machine", nil)
	if err != nil {
		log.Errorf("failed to create event publisher for State Machine: %v", err)
		return nil, fmt.Errorf("failed to create event publisher: %w", err)
	}

	// Wrap publisher and subscriber to implement statemachine interfaces
	pubWrapper := &publisherWrapper{publisher: publisher}
	subWrapper := &subscriberWrapper{subscriber: subscriber}

	// Get timeline from processor
	timeline := dm.processor.GetTimeline()

	// Create State Machine with timeline
	sm, err := statemachine.NewStateMachine(
		ctx,
		operationID,
		databaseID,
		correlationID,
		pubWrapper,
		subWrapper,
		redisClient,
		dm.smConfig,
		statemachine.WithTimeline(timeline),
	)
	if err != nil {
		// Clean up publisher on error
		publisher.Close()
		log.Errorf("failed to create State Machine: %v", err)
		return nil, fmt.Errorf("failed to create State Machine: %w", err)
	}

	// Set workflow data from ClusterInfo
	if clusterInfo != nil {
		sm.ClusterID = clusterInfo.ClusterID
		sm.InfobaseID = clusterInfo.InfobaseID
	}
	sm.ExtensionName = extensionName
	sm.ExtensionPath = extensionPath

	log.Infof("State Machine created: id=%s, operation_id=%s, database_id=%s, correlation_id=%s",
		sm.ID, operationID, databaseID, correlationID)

	return sm, nil
}

// Metrics recording functions (placeholder - to be implemented with Prometheus)




