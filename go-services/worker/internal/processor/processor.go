// go-services/worker/internal/processor/processor.go
package processor

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/config"
	sharedEvents "github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	sharedMetrics "github.com/commandcenter1c/commandcenter/shared/metrics"
	"github.com/commandcenter1c/commandcenter/shared/models"
	workerConfig "github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/credentials"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/template"
)

// TemplateClient is an interface for fetching templates from Orchestrator
type TemplateClient interface {
	GetTemplate(ctx context.Context, templateID string) (*TemplateData, error)
}

// TemplateData represents template data from Orchestrator
type TemplateData struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	OperationType string                 `json:"operation_type"`
	TargetEntity  string                 `json:"target_entity"`
	TemplateData  map[string]interface{} `json:"template_data"`
	Version       int                    `json:"version"`
	IsActive      bool                   `json:"is_active"`
}

// TaskProcessor handles task processing logic
type TaskProcessor struct {
	config         *config.Config
	credsClient    credentials.Fetcher
	odataClients   map[string]*odata.Client // Cache clients per database
	clientsMutex   sync.RWMutex
	workerID       string
	featureFlags   *workerConfig.FeatureFlags  // Feature flags for dual-mode
	dualModeProc   *DualModeProcessor          // Dual-mode processor
	eventPublisher *events.EventPublisher      // Event publisher for workflow tracking (internal)

	// State Machine dependencies (Sprint 2.1)
	redisClient     *redis.Client             // Redis client for State Machine persistence
	eventSubscriber *sharedEvents.Subscriber  // Subscriber for events from ras-adapter/batch-service

	// Template Engine (Phase 4.6)
	templateEngine *template.EngineWithFallback // Go template engine with Python fallback
	templateClient TemplateClient               // Client for fetching templates from Orchestrator
	logger         *zap.Logger                  // Structured logger for template operations

	// Workflow Engine (Phase 5)
	workflowHandler *WorkflowHandler // Handler for execute_workflow operations

	// RAS Operations Handler (Phase 4 - Context Menu Actions)
	rasHandler *RASHandler // Handler for RAS operations (lock, unlock, block, terminate)

	// Prometheus metrics for Service Mesh monitoring
	appMetrics *sharedMetrics.Metrics
}

// DefaultConsumerGroupWorker is the default consumer group name for Worker event subscribers
// Can be overridden via WORKER_CONSUMER_GROUP environment variable
const DefaultConsumerGroupWorker = "worker-state-machine"

// ProcessorOptions contains optional dependencies for TaskProcessor
type ProcessorOptions struct {
	TemplateEngine   *template.EngineWithFallback
	TemplateClient   TemplateClient
	WorkflowClient   WorkflowClient            // Client for workflow operations (optional)
	OrchestratorURL  string                    // Orchestrator URL for workflow engine (optional)
	Logger           *zap.Logger
	Metrics          *sharedMetrics.Metrics    // Prometheus metrics for Service Mesh monitoring (optional)
}

// NewTaskProcessor creates a new task processor
func NewTaskProcessor(cfg *config.Config, credsClient credentials.Fetcher, redisClient *redis.Client) *TaskProcessor {
	return NewTaskProcessorWithOptions(cfg, credsClient, redisClient, ProcessorOptions{})
}

// NewTaskProcessorWithOptions creates a new task processor with optional dependencies
func NewTaskProcessorWithOptions(cfg *config.Config, credsClient credentials.Fetcher, redisClient *redis.Client, opts ProcessorOptions) *TaskProcessor {
	log := logger.GetLogger()

	// Load feature flags from environment
	featureFlags := workerConfig.LoadFeatureFlagsFromEnv()

	// Get consumer group from config (configurable via WORKER_CONSUMER_GROUP env var)
	consumerGroup := cfg.WorkerConsumerGroup
	if consumerGroup == "" {
		consumerGroup = DefaultConsumerGroupWorker
	}

	// Get or create logger
	zapLogger := opts.Logger
	if zapLogger == nil {
		zapLogger, _ = zap.NewProduction()
	}

	processor := &TaskProcessor{
		config:         cfg,
		credsClient:    credsClient,
		odataClients:   make(map[string]*odata.Client),
		workerID:       cfg.WorkerID,
		featureFlags:   featureFlags,
		eventPublisher: events.NewEventPublisher(redisClient),
		redisClient:    redisClient,
		templateEngine: opts.TemplateEngine,
		templateClient: opts.TemplateClient,
		logger:         zapLogger,
		appMetrics:     opts.Metrics,
	}

	// Initialize dual-mode processor
	processor.dualModeProc = NewDualModeProcessor(featureFlags, processor)

	// Initialize shared events subscriber for State Machine
	// Uses Watermill logger adapter
	wmLogger := watermill.NewStdLogger(false, false)
	subscriber, err := sharedEvents.NewSubscriber(redisClient, consumerGroup, wmLogger)
	if err != nil {
		log.Error("failed to create event subscriber, State Machine events disabled",
			zap.Error(err),
			zap.String("consumer_group", consumerGroup),
		)
		// Continue without subscriber - State Machine will work in degraded mode
	} else {
		processor.eventSubscriber = subscriber
		log.Info("event subscriber initialized",
			zap.String("consumer_group", consumerGroup),
		)
	}

	// Log template engine status
	if processor.templateEngine != nil {
		log.Info("template engine initialized",
			zap.Bool("go_engine_enabled", cfg.EnableGoTemplateEngine),
			zap.Bool("has_fallback", processor.templateEngine.HasFallback()),
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

		workflowHandler, err := NewWorkflowHandler(
			opts.WorkflowClient,
			redisClient,
			orchestratorURL,
			zapLogger,
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

	// Initialize RAS handler for context menu operations (Phase 4)
	// Uses existing ClusterResolver from DualModeProcessor
	rasAdapterURL := cfg.RASAdapterURL
	if rasAdapterURL == "" {
		rasAdapterURL = "http://localhost:8188"
	}

	// Create ClusterResolver config with Redis caching
	resolverCfg := DefaultResolverConfig()
	if redisClient != nil {
		resolverCfg.RedisClient = redisClient
	}
	resolverCfg.OrchestratorURL = cfg.OrchestratorURL

	clusterResolver := NewOrchestratorClusterResolver(resolverCfg)
	rasHandler, err := NewRASHandler(rasAdapterURL, clusterResolver, processor.eventPublisher, cfg.WorkerID)
	if err != nil {
		log.Error("failed to create RAS handler, RAS operations disabled",
			zap.Error(err),
		)
	} else {
		processor.rasHandler = rasHandler
		log.Info("RAS handler initialized for context menu operations",
			zap.String("ras_adapter_url", rasAdapterURL),
		)
	}

	return processor
}

// Process processes an operation message
func (p *TaskProcessor) Process(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()
	taskStart := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Special handling for meta-operations (not per-database)
	if msg.OperationType == "execute_workflow" {
		workflowResult := p.processWorkflow(ctx, msg)
		p.recordTaskMetrics(msg.OperationType, workflowResult.Status, time.Since(taskStart).Seconds())
		return workflowResult
	}
	if msg.OperationType == "sync_cluster" {
		syncResult := p.processSyncCluster(ctx, msg)
		p.recordTaskMetrics(msg.OperationType, syncResult.Status, time.Since(taskStart).Seconds())
		return syncResult
	}
	if msg.OperationType == "discover_clusters" {
		discoverResult := p.processDiscoverClusters(ctx, msg)
		p.recordTaskMetrics(msg.OperationType, discoverResult.Status, time.Since(taskStart).Seconds())
		return discoverResult
	}

	// RAS operations handler (Phase 4 - Context Menu Actions)
	// These operations are handled in parallel by RASHandler
	if IsRASOperation(msg.OperationType) {
		if p.rasHandler == nil {
			log.Error("RAS handler not initialized, cannot process RAS operation",
				zap.String("operation_id", msg.OperationID),
				zap.String("operation_type", msg.OperationType),
			)
			result.Status = "failed"
			result.Results = append(result.Results, models.DatabaseResultV2{
				DatabaseID: "ras_handler",
				Success:    false,
				Error:      "RAS handler not configured",
				ErrorCode:  "RAS_HANDLER_DISABLED",
			})
			result.Summary = models.ResultSummary{
				Total:  1,
				Failed: 1,
			}
			p.recordTaskMetrics(msg.OperationType, result.Status, time.Since(taskStart).Seconds())
			return result
		}

		log.Info("delegating to RAS handler",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.Int("target_count", len(msg.TargetDatabases)),
		)

		rasResult := p.rasHandler.Process(ctx, msg)
		rasResult.WorkerID = p.workerID
		p.recordTaskMetrics(msg.OperationType, rasResult.Status, time.Since(taskStart).Seconds())
		return rasResult
	}

	// Process each target database
	totalDatabases := len(msg.TargetDatabases)
	succeeded := 0
	failed := 0
	totalDuration := 0.0

	for i, dbTarget := range msg.TargetDatabases {
		log.Infof("processing database %s, progress: %d%%", dbTarget.ID, (i+1)*100/totalDatabases)

		dbResult := p.processSingleDatabase(ctx, msg, dbTarget.ID)
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

	// Record metrics for Service Mesh monitoring
	p.recordTaskMetrics(msg.OperationType, result.Status, time.Since(taskStart).Seconds())

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
	log := logger.GetLogger()

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	// Publish PROCESSING event
	if err := p.eventPublisher.PublishProcessing(ctx, msg.OperationID, databaseID, p.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	// Special handling for extension installation (with dual-mode support)
	if msg.OperationType == "install_extension" {
		// Use dual-mode processor
		result = p.dualModeProc.ProcessExtensionInstall(ctx, msg, databaseID)
		result.DatabaseID = databaseID
		result.Duration = time.Since(start).Seconds()

		// Publish SUCCESS/FAILED event for extension installation
		if result.Success {
			if err := p.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
				log.Error("failed to publish SUCCESS event", zap.Error(err))
			}
		} else {
			if err := p.eventPublisher.PublishFailed(ctx, msg.OperationID, result.Error); err != nil {
				log.Error("failed to publish FAILED event", zap.Error(err))
			}
		}

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

	// Render template if template_id is present
	if msg.Metadata.TemplateID != "" {
		renderedPayload, err := p.renderTemplatePayload(ctx, msg, databaseID, creds)
		if err != nil {
			result.Success = false
			result.Error = fmt.Sprintf("template rendering failed: %v", err)
			result.ErrorCode = "TEMPLATE_ERROR"
			result.Duration = time.Since(start).Seconds()

			// Publish FAILED event
			if pubErr := p.eventPublisher.PublishFailed(ctx, msg.OperationID, result.Error); pubErr != nil {
				log.Error("failed to publish FAILED event", zap.Error(pubErr))
			}

			return result
		}

		// Replace payload with rendered version
		msg.Payload.Data = renderedPayload
		log.Debug("template rendered successfully",
			zap.String("template_id", msg.Metadata.TemplateID),
			zap.String("database_id", databaseID),
		)
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

	// Publish SUCCESS/FAILED event for OData operations
	if result.Success {
		if err := p.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
			log.Error("failed to publish SUCCESS event", zap.Error(err))
		}
	} else {
		if err := p.eventPublisher.PublishFailed(ctx, msg.OperationID, result.Error); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
	}

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

// --- Template Rendering (Phase 4.6) ---

// renderTemplatePayload renders template payload using Go template engine with Python fallback.
// Returns the rendered payload data ready for OData operation.
func (p *TaskProcessor) renderTemplatePayload(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) (map[string]interface{}, error) {
	templateID := msg.Metadata.TemplateID
	start := time.Now()

	// Check if template engine is available
	if p.templateEngine == nil {
		metrics.RecordTemplateFallback("disabled")
		return nil, fmt.Errorf("template engine not configured")
	}

	// Check if template client is available
	if p.templateClient == nil {
		metrics.RecordTemplateFallback("disabled")
		return nil, fmt.Errorf("template client not configured")
	}

	// Fetch template from Orchestrator
	tmpl, err := p.templateClient.GetTemplate(ctx, templateID)
	if err != nil {
		metrics.RecordTemplateRenderError("go", time.Since(start).Seconds(), "network")
		return nil, fmt.Errorf("failed to fetch template %s: %w", templateID, err)
	}

	// Build template context
	templateContext := p.buildTemplateContext(msg, databaseID, creds)

	// Render template with fallback support
	renderCtx := ctx
	if p.config.TemplateRenderTimeout > 0 {
		var cancel context.CancelFunc
		renderCtx, cancel = context.WithTimeout(ctx, p.config.TemplateRenderTimeout)
		defer cancel()
	}

	rendered, err := p.templateEngine.RenderWithFallback(renderCtx, templateID, tmpl.TemplateData, templateContext)
	duration := time.Since(start).Seconds()

	if err != nil {
		// Categorize error for metrics
		errorType := categorizeTemplateError(err)
		metrics.RecordTemplateRenderError("go", duration, errorType)

		p.logger.Error("template rendering failed",
			zap.String("template_id", templateID),
			zap.String("database_id", databaseID),
			zap.String("error_type", errorType),
			zap.Error(err),
		)

		return nil, err
	}

	// Record success metrics
	metrics.RecordTemplateRenderSuccess("go", duration)

	p.logger.Info("template rendered",
		zap.String("template_id", templateID),
		zap.String("database_id", databaseID),
		zap.Float64("duration_seconds", duration),
	)

	return rendered, nil
}

// buildTemplateContext constructs the context for template rendering.
// Includes system variables, operation metadata, and database info.
func (p *TaskProcessor) buildTemplateContext(msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) map[string]interface{} {
	builder := template.NewContextBuilder().
		WithSystemVars().
		WithOperationID(msg.OperationID).
		WithTemplateID(msg.Metadata.TemplateID)

	// Add database context
	dbContext := map[string]interface{}{
		"id":        databaseID,
		"odata_url": creds.ODataURL,
	}
	builder.WithDatabase(dbContext)

	// Add operation-specific data
	builder.With("operation_type", msg.OperationType)
	builder.With("entity", msg.Entity)

	// Add user-provided payload data (may contain values to merge with template)
	if msg.Payload.Data != nil {
		builder.WithData(msg.Payload.Data)
	}

	// Add filters as context variables
	if msg.Payload.Filters != nil {
		builder.With("filters", msg.Payload.Filters)
	}

	// Add options as context variables
	if msg.Payload.Options != nil {
		builder.With("options", msg.Payload.Options)
	}

	return builder.Build()
}

// categorizeTemplateError categorizes template error for metrics
func categorizeTemplateError(err error) string {
	if err == nil {
		return "unknown"
	}

	errStr := err.Error()

	switch {
	case err == context.DeadlineExceeded:
		return "timeout"
	case err == context.Canceled:
		return "timeout"
	case containsAny(errStr, "validation", "invalid", "not allowed"):
		return "validation"
	case containsAny(errStr, "compile", "syntax", "parse"):
		return "compilation"
	case containsAny(errStr, "execute", "render"):
		return "execution"
	case containsAny(errStr, "network", "connection", "timeout", "refused"):
		return "network"
	default:
		return "execution"
	}
}

// containsAny checks if s contains any of the substrings
func containsAny(s string, substrs ...string) bool {
	sLower := stringToLower(s)
	for _, sub := range substrs {
		if stringContains(sLower, stringToLower(sub)) {
			return true
		}
	}
	return false
}

// stringToLower is a helper to avoid importing strings package
func stringToLower(s string) string {
	result := make([]byte, len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' {
			c += 'a' - 'A'
		}
		result[i] = c
	}
	return string(result)
}

// stringContains is a helper to avoid importing strings package
func stringContains(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// GetFeatureFlags returns current feature flags configuration
func (p *TaskProcessor) GetFeatureFlags() map[string]interface{} {
	return p.dualModeProc.GetFeatureFlags()
}

// ReloadFeatureFlags hot-reloads feature flags from environment
func (p *TaskProcessor) ReloadFeatureFlags() error {
	return p.dualModeProc.ReloadFeatureFlags()
}

// --- State Machine methods (Sprint 2.1) ---

// GetEventSubscriber returns the shared events subscriber for State Machine
// Returns nil if subscriber initialization failed
func (p *TaskProcessor) GetEventSubscriber() *sharedEvents.Subscriber {
	return p.eventSubscriber
}

// GetRedisClient returns the Redis client for State Machine persistence
func (p *TaskProcessor) GetRedisClient() *redis.Client {
	return p.redisClient
}

// StartEventSubscriber starts the event subscriber in background
// Call this after registering all event handlers
// Returns immediately, subscriber runs in background goroutine
func (p *TaskProcessor) StartEventSubscriber(ctx context.Context) error {
	if p.eventSubscriber == nil {
		return nil // Subscriber not initialized, skip
	}

	log := logger.GetLogger()
	log.Info("starting event subscriber for State Machine")

	go func() {
		if err := p.eventSubscriber.Run(ctx); err != nil && err != context.Canceled {
			log.Error("event subscriber stopped with error", zap.Error(err))
		}
	}()

	return nil
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

	// Close event subscriber if initialized
	if p.eventSubscriber != nil {
		if err := p.eventSubscriber.Close(); err != nil {
			log.Error("failed to close event subscriber", zap.Error(err))
			return err
		}
		log.Info("event subscriber closed")
	}

	return nil
}

// processWorkflow handles execute_workflow operation type.
// This is a workflow-level operation that doesn't iterate over databases.
func (p *TaskProcessor) processWorkflow(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
	log := logger.GetLogger()
	start := time.Now()

	result := &models.OperationResultV2{
		OperationID: msg.OperationID,
		WorkerID:    p.workerID,
		Timestamp:   time.Now(),
		Results:     []models.DatabaseResultV2{},
	}

	// Check if workflow handler is available
	if p.workflowHandler == nil {
		log.Error("workflow handler not initialized, cannot execute workflow",
			zap.String("operation_id", msg.OperationID),
		)
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
		return result
	}

	// Publish PROCESSING event
	if err := p.eventPublisher.PublishProcessing(ctx, msg.OperationID, "workflow", p.workerID); err != nil {
		log.Error("failed to publish PROCESSING event", zap.Error(err))
	}

	// Execute workflow
	dbResult := p.workflowHandler.ExecuteWorkflow(ctx, msg)
	dbResult.DatabaseID = "workflow"
	result.Results = append(result.Results, dbResult)

	// Calculate summary
	if dbResult.Success {
		result.Status = "completed"
		result.Summary = models.ResultSummary{
			Total:       1,
			Succeeded:   1,
			Failed:      0,
			AvgDuration: dbResult.Duration,
		}

		// Publish SUCCESS event
		if err := p.eventPublisher.PublishSuccess(ctx, msg.OperationID); err != nil {
			log.Error("failed to publish SUCCESS event", zap.Error(err))
		}
	} else {
		result.Status = "failed"
		result.Summary = models.ResultSummary{
			Total:       1,
			Succeeded:   0,
			Failed:      1,
			AvgDuration: dbResult.Duration,
		}

		// Publish FAILED event
		if err := p.eventPublisher.PublishFailed(ctx, msg.OperationID, dbResult.Error); err != nil {
			log.Error("failed to publish FAILED event", zap.Error(err))
		}
	}

	return result
}
