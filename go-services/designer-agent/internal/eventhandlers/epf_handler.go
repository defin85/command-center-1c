package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/designer-agent/internal/ssh"
	"github.com/commandcenter1c/commandcenter/shared/designer"
	"github.com/commandcenter1c/commandcenter/shared/events"
)

const (
	// EpfExportTimeout is the default timeout for EPF/ERF export operations.
	EpfExportTimeout = 30 * time.Minute

	// Event types for EPF operations.
	EpfExportCompletedEvent = "designer.epf.export.completed"
	EpfExportFailedEvent    = "designer.epf.export.failed"
)

// EpfHandler handles EPF/ERF export commands from the event bus.
type EpfHandler struct {
	sshPool     SSHExecutor
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	logger      *zap.Logger
}

// NewEpfHandler creates a new EpfHandler instance.
func NewEpfHandler(pool SSHExecutor, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, logger *zap.Logger) *EpfHandler {
	return &EpfHandler{
		sshPool:     pool,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		logger:      logger.With(zap.String("handler", "epf")),
	}
}

// HandleExportCommand handles EPF/ERF export command from the event bus.
// This exports external data processors (.epf) or external reports (.erf) to files.
func (h *EpfHandler) HandleExportCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse epf export command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start))
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid epf export command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start))
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeEpfExport {
		h.logger.Error("wrong command type for epf export handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeEpfExport),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeEpfExport, cmd.CommandType),
			"", time.Since(start))
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "epf-export", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate epf export command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0)
	}

	h.logger.Info("handling epf export command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("target_path", cmd.Params.TargetPath))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.received", map[string]string{
			"command_type": cmd.CommandType,
		})
	}

	// Publish progress: started
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting EPF/ERF export")

	// Get timeout
	timeout := EpfExportTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeExportCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute epf export",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("target_path", cmd.Params.TargetPath),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("epf_export", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("epf_export", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration)
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("epf export failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("target_path", cmd.Params.TargetPath),
			zap.Int("exit_code", result.ExitCode),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("epf_export", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("epf_export", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration)
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("epf_export", "success", duration.Seconds())
		h.metrics.RecordSSHCommand("epf_export", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]string{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("epf exported successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("target_path", cmd.Params.TargetPath),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration)
}

// executeExportCommand executes the EPF/ERF export command via SSH.
func (h *EpfHandler) executeExportCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
	// Build SSH client config
	clientCfg := ssh.ClientConfig{
		Host:     cmd.SSH.Host,
		Port:     cmd.SSH.Port,
		User:     cmd.SSH.User,
		Password: cmd.SSH.Password,
	}

	if cmd.SSH.Port == 0 {
		clientCfg.Port = 22
	}

	if cmd.SSH.PrivateKey != "" {
		clientCfg.PrivateKey = []byte(cmd.SSH.PrivateKey)
		clientCfg.PrivateKeyPassphrase = cmd.SSH.PrivateKeyPassphrase
	}

	// Get SSH client from pool
	client, err := h.sshPool.GetClient(ctx, clientCfg)
	if err != nil {
		return nil, "", fmt.Errorf("failed to get SSH client: %w", err)
	}
	defer h.sshPool.ReleaseClient(client)

	// Build command
	builder := ssh.NewCommandBuilder()
	if cmd.Params.Server && cmd.Params.ClusterHost != "" {
		builder.WithConnection(cmd.Params.ClusterHost, cmd.Params.InfobasePath, cmd.Infobase.User, cmd.Infobase.Password)
	} else {
		builder.WithConnection("", cmd.Params.InfobasePath, cmd.Infobase.User, cmd.Infobase.Password)
	}

	// DumpExtFiles command - exports EPF/ERF to files
	// Uses ExtensionFile as source (the EPF/ERF file path in the database)
	// Uses TargetPath as output directory
	designerCmd := builder.DumpExtFilesCmd(cmd.Params.ExtensionFile, cmd.Params.TargetPath)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 10, "Connecting to server and exporting EPF/ERF...")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		h.sshPool.RemoveClient(client)
		return nil, "", err
	}

	return result, result.Output, nil
}

// monitorProgress monitors SSH output and publishes progress events.
func (h *EpfHandler) monitorProgress(ctx context.Context, progressCh <-chan ssh.ProgressInfo, cmd *designer.DesignerCommand, correlationID string) {
	lastPercent := 0

	for {
		select {
		case <-ctx.Done():
			return
		case info, ok := <-progressCh:
			if !ok {
				return
			}

			// Try to parse percentage from output
			percent := ParseProgressPercent(info.Line)
			if percent >= 0 && percent > lastPercent {
				lastPercent = percent
				phase := ParsePhase(info.Line)
				if phase == "" {
					phase = "exporting"
				}
				h.publishProgressWithPhase(ctx, correlationID, cmd, designer.ProgressStatusInProgress, percent, info.Line, phase)
			}
		}
	}
}

// publishProgress publishes a progress event.
func (h *EpfHandler) publishProgress(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message string) {
	h.publishProgressWithPhase(ctx, correlationID, cmd, status, percentage, message, "")
}

// publishProgressWithPhase publishes a progress event with phase information.
func (h *EpfHandler) publishProgressWithPhase(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message, phase string) {
	progress := designer.NewDesignerProgress(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, status, percentage, message)
	if phase != "" {
		progress.Phase = phase
	}

	err := h.publisher.Publish(ctx,
		designer.StreamEventsProgress,
		"designer.progress",
		progress,
		correlationID)

	if err != nil {
		h.logger.Warn("failed to publish progress event",
			zap.String("correlation_id", correlationID),
			zap.Error(err))
	}
}

// publishSuccess publishes a success event to the event bus.
func (h *EpfHandler) publishSuccess(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, output string, duration time.Duration) error {
	// Publish progress: completed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusCompleted, 100, "EPF/ERF export completed successfully")

	result := designer.NewDesignerResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, map[string]interface{}{
		"target_path": cmd.Params.TargetPath,
	}, output, duration)

	err := h.publisher.Publish(ctx,
		designer.StreamEventsCompleted,
		EpfExportCompletedEvent,
		result,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", designer.StreamEventsCompleted),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Debug("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", designer.StreamEventsCompleted),
		zap.String("event_type", EpfExportCompletedEvent))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *EpfHandler) publishError(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, err error, output string, duration time.Duration) error {
	// Publish progress: failed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusFailed, 0, err.Error())

	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := designer.CommandTypeEpfExport

	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := designer.NewDesignerErrorResult(operationID, databaseID, commandType, err.Error(), "", output, 1, duration)

	pubErr := h.publisher.Publish(ctx,
		designer.StreamEventsFailed,
		EpfExportFailedEvent,
		result,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", designer.StreamEventsFailed),
			zap.Error(pubErr))
		return err
	}

	h.logger.Debug("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", designer.StreamEventsFailed),
		zap.String("event_type", EpfExportFailedEvent))

	return err
}
