// go-services/worker/internal/drivers/designerops/driver.go
package designerops

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
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

	credsCtx := credentials.WithRequestedBy(ctx, strings.TrimSpace(msg.Metadata.CreatedBy))
	creds, err := d.fetchDesignerCredentials(credsCtx, databaseID)
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

	resolvedArgs, cleanup, err := resolveArtifactArgs(ctx, args, msg.OperationID, databaseID)
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("artifact resolve failed: %v", err), "ARTIFACT_ERROR"), nil
	}
	cleanupFns := []func(){cleanup}
	defer func() {
		for _, fn := range cleanupFns {
			fn()
		}
	}()

	options := cli.DefaultCommandOptions()
	if value := extractBoolOption(msg.Payload.Data, "disable_startup_messages"); value != nil {
		options.DisableStartupMessages = *value
	}
	if value := extractBoolOption(msg.Payload.Data, "disable_startup_dialogs"); value != nil {
		options.DisableStartupDialogs = *value
	}
	logCapture := false
	logPath := ""
	logNoTruncate := false
	if value := extractBoolOption(msg.Payload.Data, "log_capture"); value != nil {
		logCapture = *value
	}
	if value := extractBoolOption(msg.Payload.Data, "log_no_truncate"); value != nil {
		logNoTruncate = *value
	}
	if value := extractStringOption(msg.Payload.Data, "log_path"); value != "" {
		logPath = value
	}
	if rawOptions, ok := msg.Payload.Data["options"]; ok {
		if optMap, ok := rawOptions.(map[string]interface{}); ok {
			if value := extractBoolOption(optMap, "disable_startup_messages"); value != nil {
				options.DisableStartupMessages = *value
			}
			if value := extractBoolOption(optMap, "disable_startup_dialogs"); value != nil {
				options.DisableStartupDialogs = *value
			}
			if value := extractBoolOption(optMap, "log_capture"); value != nil {
				logCapture = *value
			}
			if value := extractBoolOption(optMap, "log_no_truncate"); value != nil {
				logNoTruncate = *value
			}
			if value := extractStringOption(optMap, "log_path"); value != "" {
				logPath = value
			}
		}
	}

	username := strings.TrimSpace(creds.IBUsername)
	password := strings.TrimSpace(creds.IBPassword)
	if username == "" {
		createdBy := strings.TrimSpace(msg.Metadata.CreatedBy)
		if createdBy == "" {
			createdBy = "unknown"
		}
		return d.failResult(
			msg,
			databaseID,
			start,
			fmt.Sprintf("infobase user mapping not configured for created_by=%s", createdBy),
			"CREDENTIALS_ERROR",
		), nil
	}

	logPathLocal := ""
	logPathCli := ""
	if logCapture {
		var logCleanup func()
		logPathLocal, logPathCli, logCleanup, err = prepareCliLogPath(
			msg.OperationID,
			databaseID,
			logPath,
		)
		if err != nil {
			return d.failResult(msg, databaseID, start, fmt.Sprintf("failed to prepare log file: %v", err), "LOG_ERROR"), nil
		}
		if logCleanup != nil {
			cleanupFns = append(cleanupFns, logCleanup)
		}
	}

	preArgs := []string{}
	if logCapture && logPathCli != "" {
		preArgs = append(preArgs, "/Out", logPathCli)
		if logNoTruncate {
			preArgs = append(preArgs, "-NoTruncate")
		}
	}

	cmdArgs, err := cli.BuildDesignerCommandArgs(
		server,
		creds.InfobaseName,
		username,
		password,
		command,
		resolvedArgs,
		options,
		preArgs,
	)
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	res, err := exec.Execute(ctx, cmdArgs)
	logOutput := ""
	if logCapture && logPathLocal != "" {
		logOutput = readCliLog(logPathLocal)
	}
	maskedArgs := cli.MaskSensitiveArgs(cmdArgs)
	return d.buildResult(msg, databaseID, start, command, args, maskedArgs, res, err, logOutput), nil
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
	logOutput string,
) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("cli.%s", msg.OperationType)
	if err != nil {
		errorMessage := formatCliError(err, res, logOutput)
		logger.GetLogger().Warn("designer CLI operation failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.String("database_id", databaseID),
			zap.Error(err),
		)
		d.timeline.Record(context.Background(), msg.OperationID, eventBase+".failed", events.MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"error":       errorMessage,
			"duration_ms": duration.Milliseconds(),
		}, events.WorkflowMetadataFromMessage(msg)))
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      errorMessage,
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
	if logOutput != "" {
		data["log_output"] = logOutput
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

func formatCliError(err error, res *cli.ExecutionResult, logOutput string) string {
	if err == nil {
		return ""
	}
	if res == nil {
		return err.Error()
	}

	details := strings.TrimSpace(res.Stderr)
	if details == "" {
		details = strings.TrimSpace(res.Stdout)
	}
	if details == "" {
		details = strings.TrimSpace(logOutput)
	}
	if len(details) > 2000 {
		details = details[:2000] + "...(truncated)"
	}
	if details == "" {
		return err.Error()
	}
	if logOutput != "" && details != strings.TrimSpace(logOutput) {
		logText := strings.TrimSpace(logOutput)
		if len(logText) > 2000 {
			logText = logText[:2000] + "...(truncated)"
		}
		return fmt.Sprintf("%s: %s\n--- 1C log ---\n%s", err.Error(), details, logText)
	}
	return fmt.Sprintf("%s: %s", err.Error(), details)
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

func extractStringOption(data map[string]interface{}, key string) string {
	if data == nil {
		return ""
	}
	raw, ok := data[key]
	if !ok || raw == nil {
		return ""
	}
	switch value := raw.(type) {
	case string:
		return value
	default:
		return fmt.Sprintf("%v", value)
	}
}

func prepareCliLogPath(operationID, databaseID, customPath string) (string, string, func(), error) {
	baseDir := resolveArtifactBaseDir()
	tempDir := filepath.Join(baseDir, operationID, databaseID)

	path := strings.TrimSpace(customPath)
	if path == "" {
		path = filepath.Join(tempDir, "designer-cli.log")
	} else if !filepath.IsAbs(path) && !isWindowsPath(path) {
		path = filepath.Join(tempDir, path)
	}

	localPath := path
	if isWindowsPath(path) {
		localPath = fromWindowsPath(path)
	}

	if err := os.MkdirAll(filepath.Dir(localPath), 0o755); err != nil {
		return "", "", nil, fmt.Errorf("failed to create log dir: %w", err)
	}

	file, err := os.Create(localPath)
	if err != nil {
		return "", "", nil, fmt.Errorf("failed to create log file: %w", err)
	}
	if err := file.Close(); err != nil {
		return "", "", nil, fmt.Errorf("failed to close log file: %w", err)
	}

	cleanup := func() {
		if strings.HasPrefix(localPath, tempDir) {
			_ = os.RemoveAll(tempDir)
		}
	}

	cliPath := localPath
	if isWindowsInterop() {
		cliPath = toWindowsPath(localPath)
	}
	if isWindowsPath(path) {
		cliPath = path
	}

	return localPath, cliPath, cleanup, nil
}

func isWindowsPath(path string) bool {
	return len(path) > 2 && path[1] == ':' && (path[2] == '\\' || path[2] == '/')
}

func readCliLog(path string) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	content := strings.TrimSpace(string(raw))
	if len(content) > 8000 {
		return content[:8000] + "...(truncated)"
	}
	return content
}
