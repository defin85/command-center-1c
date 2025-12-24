package odataops

import (
	"context"
	"fmt"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/commandcenter1c/commandcenter/worker/internal/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/template"
	"github.com/commandcenter1c/commandcenter/worker/internal/templatesvc"
)

// Driver handles OData operations directly from the worker.
type Driver struct {
	cfg            *config.Config
	credsClient    credentials.Fetcher
	service        *odata.Service
	templateEngine *template.EngineWithFallback
	templateClient templatesvc.TemplateClient
	logger         *zap.Logger
	timeline       tracing.TimelineRecorder
}

func NewDriver(
	cfg *config.Config,
	credsClient credentials.Fetcher,
	service *odata.Service,
	templateEngine *template.EngineWithFallback,
	templateClient templatesvc.TemplateClient,
	logger *zap.Logger,
	timeline tracing.TimelineRecorder,
) *Driver {
	if cfg == nil {
		cfg = &config.Config{}
	}
	if logger == nil {
		logger, _ = zap.NewProduction()
	}
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}

	return &Driver{
		cfg:            cfg,
		credsClient:    credsClient,
		service:        service,
		templateEngine: templateEngine,
		templateClient: templateClient,
		logger:         logger,
		timeline:       timeline,
	}
}

func (d *Driver) Name() string { return "odata" }

func (d *Driver) OperationTypes() []string {
	return []string{"create", "update", "delete", "query"}
}

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	eventBase := fmt.Sprintf("odata.%s", msg.OperationType)
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", events.MergeMetadata(map[string]interface{}{
		"database_id":    databaseID,
		"operation_type": msg.OperationType,
		"entity":         msg.Entity,
	}, workflowMetadata))

	if d.credsClient == nil {
		result := models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "credentials client not configured",
			ErrorCode:  "CREDENTIALS_ERROR",
		}
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
		}, workflowMetadata))
		return result, nil
	}

	creds, err := d.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		result := models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to fetch credentials: %v", err),
			ErrorCode:  "CREDENTIALS_ERROR",
		}
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
		}, workflowMetadata))
		return result, nil
	}
	if creds == nil {
		result := models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "credentials not found",
			ErrorCode:  "CREDENTIALS_ERROR",
		}
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
		}, workflowMetadata))
		return result, nil
	}
	if d.service == nil {
		result := models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata service not configured",
			ErrorCode:  "SERVICE_NOT_CONFIGURED",
		}
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
		}, workflowMetadata))
		return result, nil
	}

	if creds.ODataURL == "" || creds.Username == "" {
		result := models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata_url and username are required",
			ErrorCode:  "VALIDATION_ERROR",
		}
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
		}, workflowMetadata))
		return result, nil
	}

	if msg.Metadata.TemplateID != "" {
		renderStart := time.Now()
		d.timeline.Record(ctx, msg.OperationID, "template.render.started", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"template_id": msg.Metadata.TemplateID,
		}, workflowMetadata))
		renderedPayload, err := d.renderTemplatePayload(ctx, msg, databaseID, creds)
		if err != nil {
			result := models.DatabaseResultV2{
				DatabaseID: databaseID,
				Success:    false,
				Error:      fmt.Sprintf("template rendering failed: %v", err),
				ErrorCode:  "TEMPLATE_ERROR",
			}
			d.timeline.Record(ctx, msg.OperationID, "template.render.failed", events.MergeMetadata(map[string]interface{}{
				"database_id": databaseID,
				"template_id": msg.Metadata.TemplateID,
				"error":       result.Error,
			}, workflowMetadata))
			d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
				"database_id": databaseID,
				"error":       result.Error,
			}, workflowMetadata))
			return result, nil
		}
		msg.Payload.Data = renderedPayload
		d.timeline.Record(ctx, msg.OperationID, "template.render.completed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"template_id": msg.Metadata.TemplateID,
			"duration_ms": time.Since(renderStart).Milliseconds(),
		}, workflowMetadata))
	}

	var result models.DatabaseResultV2
	switch msg.OperationType {
	case "create":
		result = d.executeCreate(ctx, msg, databaseID, creds)
	case "update":
		result = d.executeUpdate(ctx, msg, databaseID, creds)
	case "delete":
		result = d.executeDelete(ctx, msg, databaseID, creds)
	case "query":
		result = d.executeQuery(ctx, msg, databaseID, creds)
	default:
		result = models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("unknown operation type: %s", msg.OperationType),
			ErrorCode:  "INVALID_OPERATION",
		}
	}

	if result.Success {
		d.timeline.Record(ctx, msg.OperationID, eventBase+".completed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"duration_ms": time.Since(start).Milliseconds(),
		}, workflowMetadata))
	} else {
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       result.Error,
			"error_code":  result.ErrorCode,
		}, workflowMetadata))
	}

	return result, nil
}

func (d *Driver) executeCreate(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := d.getODataService()
	if client == nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata service not configured",
			ErrorCode:  "SERVICE_NOT_CONFIGURED",
		}
	}

	log.Infof("executing create operation, entity=%s, odata_url=%s", msg.Entity, creds.ODataURL)

	result, err := client.Create(ctx, toODataCreds(creds), msg.Entity, msg.Payload.Data)
	if err != nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Data:       result,
	}
}

func (d *Driver) executeUpdate(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := d.getODataService()
	if client == nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata service not configured",
			ErrorCode:  "SERVICE_NOT_CONFIGURED",
		}
	}

	entityID, ok := msg.Payload.Filters["entity_id"].(string)
	if !ok || entityID == "" {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "entity_id is required in filters for update operation",
			ErrorCode:  "VALIDATION_ERROR",
		}
	}

	log.Infof("executing update operation, entity=%s, id=%s", msg.Entity, entityID)

	err := client.Update(ctx, toODataCreds(creds), msg.Entity, entityID, msg.Payload.Data)
	if err != nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Data: map[string]interface{}{
			"updated": true,
		},
	}
}

func (d *Driver) executeDelete(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := d.getODataService()
	if client == nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata service not configured",
			ErrorCode:  "SERVICE_NOT_CONFIGURED",
		}
	}

	entityID, ok := msg.Payload.Filters["entity_id"].(string)
	if !ok || entityID == "" {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "entity_id is required in filters for delete operation",
			ErrorCode:  "VALIDATION_ERROR",
		}
	}

	log.Infof("executing delete operation, entity=%s, id=%s", msg.Entity, entityID)

	err := client.Delete(ctx, toODataCreds(creds), msg.Entity, entityID)
	if err != nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Data: map[string]interface{}{
			"deleted": true,
		},
	}
}

func (d *Driver) executeQuery(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) models.DatabaseResultV2 {
	log := logger.GetLogger()
	client := d.getODataService()
	if client == nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      "odata service not configured",
			ErrorCode:  "SERVICE_NOT_CONFIGURED",
		}
	}

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

	results, err := client.Query(ctx, toODataCreds(creds), msg.Entity, &sharedodata.QueryParams{
		Filter: filter,
		Select: selectFields,
		Top:    top,
		Skip:   skip,
	})
	if err != nil {
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  categorizeODataError(err),
		}
	}

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Data: map[string]interface{}{
			"results": results,
			"count":   len(results),
		},
	}
}

func (d *Driver) getODataService() *odata.Service {
	return d.service
}

// CacheSize exposes current OData client cache size (used in tests).
func (d *Driver) CacheSize() int {
	if d.service == nil {
		return 0
	}
	return d.service.CacheSize()
}

func toODataCreds(creds *credentials.DatabaseCredentials) sharedodata.ODataCredentials {
	if creds == nil {
		return sharedodata.ODataCredentials{}
	}
	return sharedodata.ODataCredentials{
		BaseURL:  creds.ODataURL,
		Username: creds.Username,
		Password: creds.Password,
	}
}

func (d *Driver) renderTemplatePayload(ctx context.Context, msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) (map[string]interface{}, error) {
	templateID := msg.Metadata.TemplateID
	start := time.Now()

	if d.templateEngine == nil {
		metrics.RecordTemplateFallback("disabled")
		return nil, fmt.Errorf("template engine not configured")
	}
	if d.templateClient == nil {
		metrics.RecordTemplateFallback("disabled")
		return nil, fmt.Errorf("template client not configured")
	}

	tmpl, err := d.templateClient.GetTemplate(ctx, templateID)
	if err != nil {
		metrics.RecordTemplateRenderError("go", time.Since(start).Seconds(), "network")
		return nil, fmt.Errorf("failed to fetch template %s: %w", templateID, err)
	}

	templateContext := d.buildTemplateContext(msg, databaseID, creds)

	renderCtx := ctx
	if d.cfg.TemplateRenderTimeout > 0 {
		var cancel context.CancelFunc
		renderCtx, cancel = context.WithTimeout(ctx, d.cfg.TemplateRenderTimeout)
		defer cancel()
	}

	rendered, err := d.templateEngine.RenderWithFallback(renderCtx, templateID, tmpl.TemplateData, templateContext)
	duration := time.Since(start).Seconds()

	if err != nil {
		errorType := categorizeTemplateError(err)
		metrics.RecordTemplateRenderError("go", duration, errorType)
		d.logger.Error("template rendering failed",
			zap.String("template_id", templateID),
			zap.String("database_id", databaseID),
			zap.String("error_type", errorType),
			zap.Error(err),
		)
		return nil, err
	}

	metrics.RecordTemplateRenderSuccess("go", duration)
	d.logger.Info("template rendered",
		zap.String("template_id", templateID),
		zap.String("database_id", databaseID),
		zap.Float64("duration_seconds", duration),
	)

	return rendered, nil
}

func (d *Driver) buildTemplateContext(msg *models.OperationMessage, databaseID string, creds *credentials.DatabaseCredentials) map[string]interface{} {
	builder := template.NewContextBuilder().
		WithSystemVars().
		WithOperationID(msg.OperationID).
		WithTemplateID(msg.Metadata.TemplateID)

	dbContext := map[string]interface{}{
		"id":        databaseID,
		"odata_url": creds.ODataURL,
	}
	builder.WithDatabase(dbContext)

	builder.With("operation_type", msg.OperationType)
	builder.With("entity", msg.Entity)

	if msg.Payload.Data != nil {
		builder.WithData(msg.Payload.Data)
	}
	if msg.Payload.Filters != nil {
		builder.With("filters", msg.Payload.Filters)
	}
	if msg.Payload.Options != nil {
		builder.With("options", msg.Payload.Options)
	}

	return builder.Build()
}

func categorizeODataError(err error) string {
	if odataErr, ok := err.(*odata.ODataError); ok {
		return odataErr.Code
	}
	return "UNKNOWN_ERROR"
}

func categorizeTemplateError(err error) string {
	if err == nil {
		return "unknown"
	}

	errStr := strings.ToLower(err.Error())

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

func containsAny(s string, substrs ...string) bool {
	for _, sub := range substrs {
		if strings.Contains(s, strings.ToLower(sub)) {
			return true
		}
	}
	return false
}
