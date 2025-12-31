// go-services/worker/internal/processor/processor.go
package processor

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	sharedMetrics "github.com/commandcenter1c/commandcenter/shared/metrics"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/clusterinfo"
	workerConfig "github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/designerops"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/healthops"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibcmdops"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/odataops"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/rasops"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/workflowops"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/template"
	"github.com/commandcenter1c/commandcenter/worker/internal/templatesvc"
)

// TaskProcessor handles task processing logic
type TaskProcessor struct {
	config          *config.Config
	credsClient     credentials.Fetcher
	workerID        string
	featureFlags    *workerConfig.FeatureFlags // Feature flags for worker behavior
	eventPublisher  *events.EventPublisher     // Event publisher for workflow tracking (internal)
	clusterResolver clusterinfo.Resolver       // Cluster/infobase resolver for RAS operations

	// State Machine dependencies (Sprint 2.1)
	redisClient *redis.Client // Redis client for State Machine persistence

	// Workflow Engine (Phase 5)
	workflowHandler *workflowops.WorkflowHandler // Handler for execute_workflow operations

	// Prometheus metrics for Service Mesh monitoring
	appMetrics *sharedMetrics.Metrics

	// Timeline recorder for operation tracing
	timeline tracing.TimelineRecorder

	// Operation drivers registry (radical control-plane refactor, Phase 1)
	driverRegistry *drivers.Registry
}

// ProcessorOptions contains optional dependencies for TaskProcessor
type ProcessorOptions struct {
	TemplateEngine  *template.EngineWithFallback
	TemplateClient  templatesvc.TemplateClient
	WorkflowClient  workflowops.WorkflowClient // Client for workflow operations (optional)
	OrchestratorURL string                     // Orchestrator URL for workflow engine (optional)
	ODataService    *odata.Service
	Logger          *zap.Logger
	Metrics         *sharedMetrics.Metrics   // Prometheus metrics for Service Mesh monitoring (optional)
	Timeline        tracing.TimelineRecorder // Timeline recorder for operation tracing (optional)
}

// NewTaskProcessor creates a new task processor with required shared services.
func NewTaskProcessor(cfg *config.Config, credsClient credentials.Fetcher, redisClient *redis.Client, odataService *odata.Service) *TaskProcessor {
	return NewTaskProcessorWithOptions(cfg, credsClient, redisClient, ProcessorOptions{
		ODataService: odataService,
	})
}

// NewTaskProcessorWithOptions creates a new task processor with optional dependencies
func NewTaskProcessorWithOptions(cfg *config.Config, credsClient credentials.Fetcher, redisClient *redis.Client, opts ProcessorOptions) *TaskProcessor {
	log := logger.GetLogger()

	// Load feature flags from environment
	featureFlags := workerConfig.LoadFeatureFlagsFromEnv()

	// Get or create logger
	zapLogger := opts.Logger
	if zapLogger == nil {
		zapLogger, _ = zap.NewProduction()
	}

	// Initialize timeline with noop fallback if not provided
	timeline := opts.Timeline
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}

	processor := &TaskProcessor{
		config:         cfg,
		credsClient:    credsClient,
		workerID:       cfg.WorkerID,
		featureFlags:   featureFlags,
		eventPublisher: events.NewEventPublisher(redisClient),
		redisClient:    redisClient,
		appMetrics:     opts.Metrics,
		timeline:       timeline,
		driverRegistry: drivers.NewRegistry(),
	}

	// Initialize cluster resolver for RAS operations (HTTP-based to avoid Streams waiter dependency here).
	{
		resolverCfg := clusterinfo.DefaultConfig()
		resolverCfg.OrchestratorURL = cfg.OrchestratorURL
		resolverCfg.APIKey = cfg.WorkerAPIKey
		resolverCfg.RedisClient = redisClient
		resolverCfg.UseStreams = false
		processor.clusterResolver = clusterinfo.NewOrchestratorResolver(resolverCfg)
		log.Info("cluster resolver initialized for RAS operations",
			zap.Bool("use_streams", resolverCfg.UseStreams),
			zap.String("orchestrator_url", resolverCfg.OrchestratorURL),
		)
	}

	// Log template engine status
	if opts.TemplateEngine != nil {
		log.Info("template engine initialized",
			zap.Bool("go_engine_enabled", cfg.EnableGoTemplateEngine),
			zap.Bool("has_fallback", opts.TemplateEngine.HasFallback()),
		)
	} else {
		log.Info("template engine not configured, template rendering disabled")
	}

	// Initialize workflow handler if workflow client is provided
	if opts.WorkflowClient != nil {
		orchestratorURL := opts.OrchestratorURL
		if orchestratorURL == "" {
			orchestratorURL = cfg.OrchestratorURL
		}

		workflowHandler, err := workflowops.NewWorkflowHandler(
			opts.WorkflowClient,
			redisClient,
			orchestratorURL,
			zapLogger,
			timeline,
		)
		if err != nil {
			log.Error("failed to create workflow handler, execute_workflow disabled",
				zap.Error(err),
			)
		} else {
			processor.workflowHandler = workflowHandler
			log.Info("workflow handler initialized for execute_workflow operations")
		}
	} else {
		log.Info("workflow client not configured, execute_workflow disabled")
	}

	// Register operation drivers (Phase 1: wrap existing implementations).
	// Meta operations
	_ = processor.driverRegistry.RegisterMeta(
		workflowops.NewDriver(processor.workerID, processor.eventPublisher, processor.workflowHandler, processor.timeline),
	)
	_ = processor.driverRegistry.RegisterMeta(
		rasops.NewMetaDriver(processor.workerID, redisClient, processor.eventPublisher, processor.timeline),
	)

	// Database operations
	_ = processor.driverRegistry.RegisterDatabase(
		designerops.NewDriver(
			processor.credsClient,
			processor.timeline,
		),
	)
	_ = processor.driverRegistry.RegisterDatabase(
		ibcmdops.NewDriver(
			processor.credsClient,
			processor.timeline,
		),
	)
	_ = processor.driverRegistry.RegisterDatabase(
		healthops.NewDriver(
			processor.credsClient,
			opts.ODataService,
			processor.timeline,
		),
	)
	_ = processor.driverRegistry.RegisterDatabase(
		rasops.NewInfobaseDriver(processor.workerID, processor.clusterResolver, processor.timeline),
	)
	_ = processor.driverRegistry.RegisterDatabase(
		odataops.NewDriver(
			cfg,
			processor.credsClient,
			opts.ODataService,
			opts.TemplateEngine,
			opts.TemplateClient,
			zapLogger,
			processor.timeline,
		),
	)

	return processor
}

// Process processes an operation message
func (p *TaskProcessor) Process(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()
	taskStart := time.Now()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	// Record operation start in timeline
	p.timeline.Record(ctx, msg.OperationID, "operation.started", appendWorkflowMetadata(map[string]interface{}{
		"operation_type": msg.OperationType,
		"worker_id":      p.workerID,
		"databases":      len(msg.TargetDatabases),
	}, workflowMetadata))

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Meta-operations (not per-database) via drivers registry
	if metaDriver, ok := p.driverRegistry.LookupMeta(msg.OperationType); ok {
		driverStart := time.Now()
		p.timeline.Record(ctx, msg.OperationID, "driver.started", appendWorkflowMetadata(map[string]interface{}{
			"driver":         metaDriver.Name(),
			"operation_type": msg.OperationType,
		}, workflowMetadata))
		metaResult, err := metaDriver.Execute(ctx, msg)
		if err != nil {
			metaResult = &models.OperationResultV2{
				OperationID: msg.OperationID,
				WorkerID:    p.workerID,
				Timestamp:   time.Now(),
				Status:      "failed",
				Results:     []models.DatabaseResultV2{},
				Summary:     models.ResultSummary{Total: 0, Succeeded: 0, Failed: 0, AvgDuration: 0},
			}
			// Preserve error in timeline (OperationResultV2 has no top-level error field)
			p.timeline.Record(ctx, msg.OperationID, "driver.failed", appendWorkflowMetadata(map[string]interface{}{
				"driver":         metaDriver.Name(),
				"operation_type": msg.OperationType,
				"error":          err.Error(),
			}, workflowMetadata))
		}
		p.timeline.Record(ctx, msg.OperationID, "driver.finished", appendWorkflowMetadata(map[string]interface{}{
			"driver":         metaDriver.Name(),
			"operation_type": msg.OperationType,
			"status":         metaResult.Status,
			"duration_ms":    time.Since(driverStart).Milliseconds(),
		}, workflowMetadata))
		p.recordDriverMetrics(metaDriver.Name(), msg.OperationType, metaResult.Status, time.Since(driverStart).Seconds())
		p.recordTaskMetrics(msg.OperationType, metaResult.Status, time.Since(taskStart).Seconds())
		return metaResult
	}

	// Process each target database
	totalDatabases := len(msg.TargetDatabases)
	succeeded := 0
	failed := 0
	totalDuration := 0.0
	buildProgressMetadata := func(
		processingCount int,
		completedCount int,
		failedCount int,
		databaseID string,
		taskStatus string,
		durationSeconds float64,
	) map[string]interface{} {
		queued := totalDatabases - completedCount - failedCount - processingCount
		processed := completedCount + failedCount
		progressPercent := 0
		if totalDatabases > 0 {
			progressPercent = int(float64(processed) / float64(totalDatabases) * 100)
		}
		metadata := map[string]interface{}{
			"database_id":     databaseID,
			"task_status":     taskStatus,
			"total_tasks":     totalDatabases,
			"completed_tasks": completedCount,
			"failed_tasks":    failedCount,
			"processing_tasks": processingCount,
			"queued_tasks":    queued,
			"progress_percent": progressPercent,
		}
		if durationSeconds > 0 {
			metadata["duration_seconds"] = durationSeconds
		}
		return metadata
	}

	for i, dbTarget := range msg.TargetDatabases {
		log.Infof("processing database %s, progress: %d%%", dbTarget.ID, (i+1)*100/totalDatabases)

		processingMetadata := buildProgressMetadata(1, succeeded, failed, dbTarget.ID, "processing", 0)
		processingMetadata["operation_type"] = msg.OperationType
		p.timeline.Record(ctx, msg.OperationID, "database.processing", appendWorkflowMetadata(
			processingMetadata,
			workflowMetadata,
		))

		dbResult := p.processSingleDatabase(ctx, msg, dbTarget.ID)
		result.Results = append(result.Results, dbResult)

		if dbResult.Success {
			succeeded++
		} else {
			failed++
		}

		totalDuration += dbResult.Duration

		taskStatus := "failed"
		eventName := "database.failed"
		if dbResult.Success {
			taskStatus = "completed"
			eventName = "database.completed"
		}
		progressMetadata := buildProgressMetadata(0, succeeded, failed, dbTarget.ID, taskStatus, dbResult.Duration)
		progressMetadata["duration_ms"] = int64(dbResult.Duration * 1000)
		progressMetadata["error_code"] = dbResult.ErrorCode
		progressMetadata["error"] = dbResult.Error
		p.timeline.Record(ctx, msg.OperationID, eventName, appendWorkflowMetadata(
			progressMetadata,
			workflowMetadata,
		))
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

	// Record metrics for Service Mesh monitoring
	p.recordTaskMetrics(msg.OperationType, result.Status, time.Since(taskStart).Seconds())

	// Record operation completion in timeline
	p.timeline.Record(ctx, msg.OperationID, "operation.completed", appendWorkflowMetadata(map[string]interface{}{
		"status":      result.Status,
		"succeeded":   succeeded,
		"failed":      failed,
		"duration_ms": time.Since(taskStart).Milliseconds(),
	}, workflowMetadata))

	return result
}

// recordTaskMetrics records task processing metrics if metrics are configured
func (p *TaskProcessor) recordTaskMetrics(taskType, status string, duration float64) {
	if p.appMetrics == nil {
		return
	}

	// Map result status to metric status
	metricStatus := "success"
	if status == "failed" || status == "timeout" {
		metricStatus = "failed"
	}

	p.appMetrics.TasksProcessed.WithLabelValues(taskType, metricStatus).Inc()
	p.appMetrics.TaskDuration.WithLabelValues(taskType).Observe(duration)
}

func (p *TaskProcessor) recordDriverMetrics(driverName, operationType, status string, duration float64) {
	if p.appMetrics == nil {
		return
	}
	if driverName == "" {
		driverName = "unknown"
	}
	if operationType == "" {
		operationType = "unknown"
	}
	if status == "" {
		status = "unknown"
	}

	p.appMetrics.DriverExecutions.WithLabelValues(driverName, operationType, status).Inc()
	p.appMetrics.DriverDuration.WithLabelValues(driverName, operationType).Observe(duration)
}

func (p *TaskProcessor) processSingleDatabase(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()
	log := logger.GetLogger()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	// Publish PROCESSING event
	if err := p.eventPublisher.PublishProcessingWithMetadata(ctx, msg.OperationID, databaseID, p.workerID, workflowMetadata); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	dbDriver, ok := p.driverRegistry.LookupDatabase(msg.OperationType)
	if !ok {
		result.Success = false
		result.Error = fmt.Sprintf("unknown operation type: %s", msg.OperationType)
		result.ErrorCode = "INVALID_OPERATION"
		result.Duration = time.Since(start).Seconds()

		p.timeline.Record(ctx, msg.OperationID, "database.failed", appendWorkflowMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error_code":  result.ErrorCode,
			"error":       result.Error,
		}, workflowMetadata))
		if err := p.eventPublisher.PublishFailedWithMetadata(ctx, msg.OperationID, result.Error, workflowMetadata); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
		return result
	}

	driverStart := time.Now()
	p.timeline.Record(ctx, msg.OperationID, "driver.started", appendWorkflowMetadata(map[string]interface{}{
		"driver":         dbDriver.Name(),
		"operation_type": msg.OperationType,
		"database_id":    databaseID,
	}, workflowMetadata))

	dbRes, err := dbDriver.Execute(ctx, msg, databaseID)
	if err != nil {
		dbRes = models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  "EXECUTION_ERROR",
		}
	}
	result = dbRes

	result.DatabaseID = databaseID
	result.Duration = time.Since(start).Seconds()

	// Publish SUCCESS/FAILED event for OData operations
	if result.Success {
		if err := p.eventPublisher.PublishSuccessWithMetadata(ctx, msg.OperationID, workflowMetadata); err != nil {
			log.Error("failed to publish SUCCESS event", zap.Error(err))
		}
	} else {
		if err := p.eventPublisher.PublishFailedWithMetadata(ctx, msg.OperationID, result.Error, workflowMetadata); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
	}

	p.timeline.Record(ctx, msg.OperationID, "driver.finished", appendWorkflowMetadata(map[string]interface{}{
		"driver":         dbDriver.Name(),
		"operation_type": msg.OperationType,
		"database_id":    databaseID,
		"success":        result.Success,
		"error_code":     result.ErrorCode,
		"duration_ms":    time.Since(driverStart).Milliseconds(),
	}, workflowMetadata))
	status := "success"
	if !result.Success {
		status = "failed"
	}
	p.recordDriverMetrics(dbDriver.Name(), msg.OperationType, status, time.Since(driverStart).Seconds())

	return result
}

func appendWorkflowMetadata(
	base map[string]interface{},
	workflowMetadata map[string]interface{},
) map[string]interface{} {
	if len(workflowMetadata) == 0 {
		return base
	}
	if base == nil {
		base = map[string]interface{}{}
	}
	for key, value := range workflowMetadata {
		base[key] = value
	}
	return base
}

// GetFeatureFlags returns current feature flags configuration
func (p *TaskProcessor) GetFeatureFlags() map[string]interface{} {
	if p.featureFlags == nil {
		return map[string]interface{}{}
	}
	return p.featureFlags.GetConfig()
}

// ReloadFeatureFlags hot-reloads feature flags from environment
func (p *TaskProcessor) ReloadFeatureFlags() error {
	if p.featureFlags == nil {
		return fmt.Errorf("feature flags not configured")
	}
	return p.featureFlags.Reload()
}

// GetRedisClient returns the Redis client for State Machine persistence
func (p *TaskProcessor) GetRedisClient() *redis.Client {
	return p.redisClient
}

// GetTimeline returns the timeline recorder for operation tracing
func (p *TaskProcessor) GetTimeline() tracing.TimelineRecorder {
	return p.timeline
}

// Close gracefully shuts down the processor and its dependencies
func (p *TaskProcessor) Close() error {
	log := logger.GetLogger()
	log.Info("closing TaskProcessor")

	// Close workflow handler if initialized
	if p.workflowHandler != nil {
		if err := p.workflowHandler.Close(); err != nil {
			log.Error("failed to close workflow handler", zap.Error(err))
		}
		log.Info("workflow handler closed")
	}

	return nil
}
