// go-services/worker/internal/drivers/ibcmdops/driver.go
package ibcmdops

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibcmd"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/ibsrv"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
)

// Driver executes ibcmd operations via direct CLI.
type Driver struct {
	credsClient credentials.Fetcher
	timeline    tracing.TimelineRecorder
}

// NewDriver creates a new ibcmd driver.
func NewDriver(credsClient credentials.Fetcher, timeline tracing.TimelineRecorder) *Driver {
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}
	return &Driver{credsClient: credsClient, timeline: timeline}
}

func (d *Driver) Name() string { return "ibcmd" }

func (d *Driver) OperationTypes() []string {
	return []string{
		"ibcmd_cli",
	}
}

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	log := logger.GetLogger()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)

	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)
	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
	}, workflowMetadata))

	if os.Getenv("USE_DIRECT_IBCMD") == "false" {
		return d.failResult(msg, databaseID, start, "direct ibcmd disabled (USE_DIRECT_IBCMD=false)", "IBCMD_DISABLED"), nil
	}

	if useIbsrv := extractBool(msg.Payload.Data, "use_ibsrv"); useIbsrv {
		if err := validateIbsrvAllowed(); err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_DISABLED"), nil
		}
	}

	exec, err := ibcmd.NewExecutorFromEnv()
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("ibcmd executor not configured: %v", err), "IBCMD_NOT_CONFIGURED"), nil
	}

	credsCtx := credentials.WithRequestedBy(ctx, strings.TrimSpace(msg.Metadata.CreatedBy))
	if msg.OperationType == "ibcmd_cli" {
		credsCtx = credentials.WithIbAuthStrategy(credsCtx, extractIbcmdIbAuthStrategy(msg.Payload.Data))
		credsCtx = credentials.WithDbmsAuthStrategy(credsCtx, extractIbcmdDbmsAuthStrategy(msg.Payload.Data))
	}
	creds, err := d.fetchCredentials(credsCtx, databaseID)
	if err != nil {
		return d.failResult(msg, databaseID, start, fmt.Sprintf("failed to fetch credentials: %v", err), "CREDENTIALS_ERROR"), nil
	}

	var agent *ibsrv.AgentProcess
	if extractBool(msg.Payload.Data, "use_ibsrv") {
		agentCfg, err := buildAgentConfig(msg.Payload.Data, creds)
		if err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_CONFIG_ERROR"), nil
		}
		agent, err = ibsrv.StartAgent(ctx, agentCfg)
		if err != nil {
			return d.failResult(msg, databaseID, start, err.Error(), "IBSRV_START_ERROR"), nil
		}
		defer func() {
			if err := agent.Stop(ctx, agentCfg.ShutdownTimeout); err != nil {
				log.Warn("failed to stop ibsrv agent", zap.Error(err))
			}
		}()
	}

	store, err := newStorageFromEnv()
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "STORAGE_ERROR"), nil
	}

	request, err := buildRequest(ctx, msg, databaseID, creds, store)
	if err != nil {
		return d.failResult(msg, databaseID, start, err.Error(), "VALIDATION_ERROR"), nil
	}

	cmdCtx := ctx
	if msg.ExecConfig.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		cmdCtx, cancel = context.WithTimeout(ctx, time.Duration(msg.ExecConfig.TimeoutSeconds)*time.Second)
		defer cancel()
	}

	externalStart := time.Now()
	d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.started", events.MergeMetadata(map[string]interface{}{
		"database_id":    databaseID,
		"operation_type": msg.OperationType,
	}, workflowMetadata))

	if request.inputCleanup != nil {
		defer request.inputCleanup()
	}
	if request.outputCleanup != nil {
		defer request.outputCleanup()
	}

	res, err := exec.Execute(cmdCtx, request.Args, request.Stdin)
	if err == nil && request.outputFinalize != nil {
		if finalizeErr := request.outputFinalize(cmdCtx); finalizeErr != nil {
			err = finalizeErr
		}
	}

	externalDuration := time.Since(externalStart)
	if err != nil {
		log.Warn("ibcmd operation failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("operation_type", msg.OperationType),
			zap.String("database_id", databaseID),
			zap.Error(err),
		)
		d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.failed", events.MergeMetadata(map[string]interface{}{
			"database_id":    databaseID,
			"operation_type": msg.OperationType,
			"duration_ms":    externalDuration.Milliseconds(),
			"error":          err.Error(),
		}, workflowMetadata))
		return d.failResultWithExecution(msg, databaseID, start, err.Error(), "IBCMD_ERROR", res, request.RuntimeBindings, request.ArtifactPath), nil
	}

	result := d.buildResult(msg, databaseID, start, res, request.RuntimeBindings, request.ArtifactPath)

	d.timeline.Record(ctx, msg.OperationID, "external.ibcmd.finished", events.MergeMetadata(map[string]interface{}{
		"database_id":    databaseID,
		"operation_type": msg.OperationType,
		"duration_ms":    externalDuration.Milliseconds(),
		"exit_code":      result.Data["exit_code"],
	}, workflowMetadata))

	return result, nil
}

func (d *Driver) buildResult(
	msg *models.OperationMessage,
	databaseID string,
	start time.Time,
	res *ibcmd.ExecutionResult,
	runtimeBindings []map[string]interface{},
	artifactPath string,
) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)

	data := map[string]interface{}{
		"duration_ms": duration.Milliseconds(),
	}
	if len(runtimeBindings) > 0 {
		data["runtime_bindings"] = runtimeBindings
	}
	if res != nil {
		data["exit_code"] = res.ExitCode
		data["stdout"] = res.Stdout
		data["stderr"] = res.Stderr
		data["stdout_truncated"] = res.StdoutTruncated
		data["stderr_truncated"] = res.StderrTruncated
		data["wait_delay_hit"] = res.WaitDelayHit
	}
	if artifactPath != "" {
		data["artifact_path"] = artifactPath
	}

	d.timeline.Record(context.Background(), msg.OperationID, eventBase+".completed", events.MergeMetadata(map[string]interface{}{
		"database_id": databaseID,
		"duration_ms": duration.Milliseconds(),
	}, events.WorkflowMetadataFromMessage(msg)))

	return models.DatabaseResultV2{
		DatabaseID: databaseID,
		Success:    true,
		Duration:   duration.Seconds(),
		Data:       data,
	}
}

func (d *Driver) failResult(msg *models.OperationMessage, databaseID string, start time.Time, message, code string) models.DatabaseResultV2 {
	duration := time.Since(start)
	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)
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

func (d *Driver) failResultWithExecution(
	msg *models.OperationMessage,
	databaseID string,
	start time.Time,
	message string,
	code string,
	res *ibcmd.ExecutionResult,
	runtimeBindings []map[string]interface{},
	artifactPath string,
) models.DatabaseResultV2 {
	duration := time.Since(start)

	data := map[string]interface{}{
		"duration_ms": duration.Milliseconds(),
	}
	if len(runtimeBindings) > 0 {
		data["runtime_bindings"] = runtimeBindings
	}
	if res != nil {
		data["exit_code"] = res.ExitCode
		data["stdout"] = res.Stdout
		data["stderr"] = res.Stderr
		data["stdout_truncated"] = res.StdoutTruncated
		data["stderr_truncated"] = res.StderrTruncated
		data["wait_delay_hit"] = res.WaitDelayHit
	}
	if artifactPath != "" {
		data["artifact_path"] = artifactPath
	}

	eventBase := fmt.Sprintf("ibcmd.%s", msg.OperationType)
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
		Data:       data,
	}
}

func (d *Driver) fetchCredentials(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	if d.credsClient == nil {
		return nil, fmt.Errorf("credentials client not configured")
	}
	return d.credsClient.Fetch(ctx, databaseID)
}
