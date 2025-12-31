// go-services/worker/internal/drivers/designerops/driver.go
package designerops

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/cli"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

// Driver executes arbitrary DESIGNER CLI commands (designer_cli).
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
	return []string{"designer_cli"}
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

	exec, err := cli.NewV8ExecutorFromEnv()
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
	if server == "" || creds.InfobaseName == "" {
		return d.failResult(msg, databaseID, start, "designer credentials are incomplete", "CREDENTIALS_ERROR"), nil
	}

	command := extractString(msg.Payload.Data, "command")
	if strings.TrimSpace(command) == "" {
		return d.failResult(msg, databaseID, start, "command is required", "VALIDATION_ERROR"), nil
	}

	args, err := extractStringSlice(msg.Payload.Data["args"])
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	options := cli.DefaultCommandOptions()
	if value := extractBoolOption(msg.Payload.Data, "disable_startup_messages"); value != nil {
		options.DisableStartupMessages = *value
	}
	if value := extractBoolOption(msg.Payload.Data, "disable_startup_dialogs"); value != nil {
		options.DisableStartupDialogs = *value
	}
	if rawOptions, ok := msg.Payload.Data["options"]; ok {
		if optMap, ok := rawOptions.(map[string]interface{}); ok {
			if value := extractBoolOption(optMap, "disable_startup_messages"); value != nil {
				options.DisableStartupMessages = *value
			}
			if value := extractBoolOption(optMap, "disable_startup_dialogs"); value != nil {
				options.DisableStartupDialogs = *value
			}
		}
	}

	cmdArgs, err := cli.BuildDesignerCommandArgs(
		server,
		creds.InfobaseName,
		creds.Username,
		creds.Password,
		command,
		args,
		options,
	)
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	res, err := exec.Execute(ctx, cmdArgs)
	maskedArgs := cli.MaskSensitiveArgs(cmdArgs)
	return d.buildResult(msg, databaseID, start, command, args, maskedArgs, res, err), nil
}

func (d *Driver) buildResult(
	msg *models.OperationMessage,
	databaseID string,
	start time.Time,
	command string,
	userArgs []string,
	fullArgs []string,
	res *cli.ExecutionResult,
	err error,
) models.DatabaseResultV2 {
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
		"command":     command,
		"args":        userArgs,
		"cli_args":    fullArgs,
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

func extractStringSlice(value interface{}) ([]string, error) {
	if value == nil {
		return nil, nil
	}

	switch raw := value.(type) {
	case []string:
		return raw, nil
	case []interface{}:
		out := make([]string, 0, len(raw))
		for _, item := range raw {
			if item == nil {
				continue
			}
			s, ok := item.(string)
			if !ok {
				return nil, fmt.Errorf("args must be array of strings")
			}
			if strings.TrimSpace(s) == "" {
				continue
			}
			out = append(out, s)
		}
		return out, nil
	case string:
		lines := strings.Split(raw, "\n")
		out := make([]string, 0, len(lines))
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line != "" {
				out = append(out, line)
			}
		}
		return out, nil
	default:
		return nil, fmt.Errorf("args must be array of strings")
	}
}

func extractBoolOption(data map[string]interface{}, key string) *bool {
	if data == nil {
		return nil
	}
	raw, ok := data[key]
	if !ok || raw == nil {
		return nil
	}
	switch value := raw.(type) {
	case bool:
		return &value
	case string:
		parsed, err := strconv.ParseBool(value)
		if err != nil {
			return nil
		}
		return &parsed
	case float64:
		parsed := value != 0
		return &parsed
	default:
		return nil
	}
}
