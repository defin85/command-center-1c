// go-services/worker/internal/drivers/designerops/driver.go
package designerops

import (
	"context"
	"fmt"
	"os"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/cli"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

// Driver executes designer operations via direct CLI.
type Driver struct {
	credsClient credentials.Fetcher
	timeline    tracing.TimelineRecorder
}

// NewDriver creates a new designer CLI driver.
func NewDriver(credsClient credentials.Fetcher, timeline tracing.TimelineRecorder) *Driver {
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}
	return &Driver{
		credsClient: credsClient,
		timeline:    timeline,
	}
}

func (d *Driver) Name() string { return "designer-cli" }

func (d *Driver) OperationTypes() []string {
	return []string{"remove_extension", "config_update", "config_load", "config_dump"}
}

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	eventBase := fmt.Sprintf("cli.%s", msg.OperationType)
	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
	}, workflowMetadata))

	if os.Getenv("USE_DIRECT_CLI") == "false" {
		return d.failResult(msg, databaseID, start, "direct CLI disabled (USE_DIRECT_CLI=false)", "CLI_DISABLED"), nil
	}

	exec, err := cli.NewDesignerExecutorFromEnv()
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("cli executor not configured: %v", err), "CLI_NOT_CONFIGURED"), nil
	}

	creds, err := d.fetchDesignerCredentials(ctx, databaseID)
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("failed to fetch credentials: %v", err), "CREDENTIALS_ERROR"), nil
	}

	server := creds.ServerAddress
	if creds.ServerPort > 0 {
		server = fmt.Sprintf("%s:%d", creds.ServerAddress, creds.ServerPort)
	}
	if server == "" || creds.InfobaseName == "" || creds.Username == "" {
		return d.failResult(msg, databaseID, start, "designer credentials are incomplete", "CREDENTIALS_ERROR"), nil
	}

	switch msg.OperationType {
	case "remove_extension":
		extName := extractString(msg.Payload.Data, "extension_name")
		if extName == "" {
			return d.failResult(msg, databaseID, start, "extension_name is required", "VALIDATION_ERROR"), nil
		}
		res, err := exec.RemoveExtension(ctx, server, creds.InfobaseName, creds.Username, creds.Password, extName)
		return d.buildResult(msg, databaseID, start, res, err), nil
	case "config_update":
		res, err := exec.UpdateDBCfg(ctx, server, creds.InfobaseName, creds.Username, creds.Password)
		return d.buildResult(msg, databaseID, start, res, err), nil
	case "config_load":
		sourcePath := extractString(msg.Payload.Data, "source_path")
		if sourcePath == "" {
			sourcePath = extractString(msg.Payload.Data, "config_path")
		}
		if sourcePath == "" {
			return d.failResult(msg, databaseID, start, "source_path is required", "VALIDATION_ERROR"), nil
		}
		res, err := exec.LoadConfig(ctx, server, creds.InfobaseName, creds.Username, creds.Password, sourcePath)
		return d.buildResult(msg, databaseID, start, res, err), nil
	case "config_dump":
		targetPath := extractString(msg.Payload.Data, "target_path")
		if targetPath == "" {
			return d.failResult(msg, databaseID, start, "target_path is required", "VALIDATION_ERROR"), nil
		}
		res, err := exec.DumpConfig(ctx, server, creds.InfobaseName, creds.Username, creds.Password, targetPath)
		return d.buildResult(msg, databaseID, start, res, err), nil
	default:
		return d.failResult(msg, databaseID, start, fmt.Sprintf("unsupported operation type: %s", msg.OperationType), "INVALID_OPERATION"), nil
	}
}

func (d *Driver) buildResult(msg *models.OperationMessage, databaseID string, start time.Time, res *cli.ExecutionResult, err error) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("cli.%s", msg.OperationType)
	if err != nil {
		logger.GetLogger().Warn("designer CLI operation failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.String("database_id", databaseID),
			zap.Error(err),
		)
		d.timeline.Record(context.Background(), msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       err.Error(),
			"duration_ms": duration.Milliseconds(),
		}, events.WorkflowMetadataFromMessage(msg)))
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      err.Error(),
			ErrorCode:  "CLI_ERROR",
			Duration:   duration.Seconds(),
		}
	}

	data := map[string]interface{}{
		"duration_ms": duration.Milliseconds(),
	}
	if res != nil {
		data["exit_code"] = res.ExitCode
		data["stdout"] = res.Stdout
		data["stderr"] = res.Stderr
	}

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Duration:   duration.Seconds(),
		Data:       data,
	}

	d.timeline.Record(context.Background(), msg.OperationID, eventBase+".completed", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
		"duration_ms": duration.Milliseconds(),
	}, events.WorkflowMetadataFromMessage(msg)))
	return result
}

func (d *Driver) failResult(msg *models.OperationMessage, databaseID string, start time.Time, message, code string) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("cli.%s", msg.OperationType)
	d.timeline.Record(context.Background(), msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
		"error":       message,
		"duration_ms": duration.Milliseconds(),
	}, events.WorkflowMetadataFromMessage(msg)))
	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    false,
		Error:      message,
		ErrorCode:  code,
		Duration:   duration.Seconds(),
	}
}

func (d *Driver) fetchDesignerCredentials(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	if d.credsClient == nil {
		return nil, fmt.Errorf("credentials client not configured")
	}

	creds, err := d.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		return nil, err
	}
	return creds, nil
}

func extractString(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	v, ok := data[key]
	if !ok || v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprintf("%v", v)
}
