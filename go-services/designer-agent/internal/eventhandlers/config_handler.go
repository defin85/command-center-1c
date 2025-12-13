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
	// ConfigUpdateTimeout is the default timeout for config update (UpdateDBCfg) operations.
	// This is a very long operation - up to 4 hours for large databases.
	ConfigUpdateTimeout = 4 * time.Hour

	// ConfigLoadTimeout is the default timeout for config load operations.
	ConfigLoadTimeout = 2 * time.Hour

	// ConfigDumpTimeout is the default timeout for config dump operations.
	ConfigDumpTimeout = 1 * time.Hour

	// Event types for config operations.
	ConfigUpdateCompletedEvent = "designer.config.update.completed"
	ConfigUpdateFailedEvent    = "designer.config.update.failed"
	ConfigLoadCompletedEvent   = "designer.config.load.completed"
	ConfigLoadFailedEvent      = "designer.config.load.failed"
	ConfigDumpCompletedEvent   = "designer.config.dump.completed"
	ConfigDumpFailedEvent      = "designer.config.dump.failed"
)

// ConfigHandler handles configuration commands from the event bus.
type ConfigHandler struct {
	sshPool     SSHExecutor
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	logger      *zap.Logger
}

// NewConfigHandler creates a new ConfigHandler instance.
func NewConfigHandler(pool SSHExecutor, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, logger *zap.Logger) *ConfigHandler {
	return &ConfigHandler{
		sshPool:     pool,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		logger:      logger.With(zap.String("handler", "config")),
	}
}

// HandleUpdateCommand handles config update (UpdateDBCfg) command from the event bus.
// WARNING: This is a VERY LONG operation - up to 4 hours for large databases!
func (h *ConfigHandler) HandleUpdateCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse config update command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start), "update")
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid config update command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start), "update")
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeConfigUpdate {
		h.logger.Error("wrong command type for config update handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeConfigUpdate),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeConfigUpdate, cmd.CommandType),
			"", time.Since(start), "update")
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "config-update", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate config update command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0, "update")
	}

	h.logger.Info("handling config update command (WARNING: this may take up to 4 hours)",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.received", map[string]string{
			"command_type": cmd.CommandType,
		})
	}

	// Publish progress: started
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting database configuration update (this may take up to 4 hours)")

	// Get timeout
	timeout := ConfigUpdateTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeUpdateCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute config update",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Duration("duration", duration),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_update", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_update", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration, "update")
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("config update failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Int("exit_code", result.ExitCode),
			zap.Duration("duration", duration),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_update", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_update", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration, "update")
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("config_update", "success", duration.Seconds())
		h.metrics.RecordSSHCommand("config_update", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]string{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("config update completed successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration, "update")
}

// HandleLoadCommand handles config load command from the event bus.
func (h *ConfigHandler) HandleLoadCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse config load command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start), "load")
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid config load command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start), "load")
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeConfigLoad {
		h.logger.Error("wrong command type for config load handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeConfigLoad),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeConfigLoad, cmd.CommandType),
			"", time.Since(start), "load")
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "config-load", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate config load command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0, "load")
	}

	h.logger.Info("handling config load command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("source_path", cmd.Params.SourcePath))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.received", map[string]string{
			"command_type": cmd.CommandType,
		})
	}

	// Publish progress: started
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting configuration load")

	// Get timeout
	timeout := ConfigLoadTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeLoadCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute config load",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("source_path", cmd.Params.SourcePath),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_load", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_load", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration, "load")
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("config load failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("source_path", cmd.Params.SourcePath),
			zap.Int("exit_code", result.ExitCode),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_load", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_load", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration, "load")
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("config_load", "success", duration.Seconds())
		h.metrics.RecordSSHCommand("config_load", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]string{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("config loaded successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("source_path", cmd.Params.SourcePath),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration, "load")
}

// HandleDumpCommand handles config dump command from the event bus.
func (h *ConfigHandler) HandleDumpCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse config dump command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start), "dump")
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid config dump command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start), "dump")
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeConfigDump {
		h.logger.Error("wrong command type for config dump handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeConfigDump),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeConfigDump, cmd.CommandType),
			"", time.Since(start), "dump")
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "config-dump", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate config dump command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0, "dump")
	}

	h.logger.Info("handling config dump command",
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
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting configuration dump")

	// Get timeout
	timeout := ConfigDumpTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeDumpCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute config dump",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("target_path", cmd.Params.TargetPath),
			zap.Error(err))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_dump", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_dump", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration, "dump")
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("config dump failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("target_path", cmd.Params.TargetPath),
			zap.Int("exit_code", result.ExitCode),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		if h.metrics != nil {
			h.metrics.RecordCommand("config_dump", "error", duration.Seconds())
			h.metrics.RecordSSHCommand("config_dump", duration.Seconds())
		}
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]string{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration, "dump")
	}

	// Record metrics for successful operation
	if h.metrics != nil {
		h.metrics.RecordCommand("config_dump", "success", duration.Seconds())
		h.metrics.RecordSSHCommand("config_dump", duration.Seconds())
	}
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]string{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("config dumped successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("target_path", cmd.Params.TargetPath),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration, "dump")
}

// executeUpdateCommand executes the config update command via SSH.
func (h *ConfigHandler) executeUpdateCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
	client, cleanup, err := h.getSSHClient(ctx, cmd)
	if err != nil {
		return nil, "", err
	}
	defer cleanup(false)

	// Build command
	builder := h.buildCommandBuilder(cmd)

	// UpdateDBCfg command with options
	options := ssh.ConfigUpdateDBOptions{
		Server:         cmd.Params.Server,
		DynamicUpdate:  false, // Dynamic update is risky for large configs
		BackgroundUpdate: false,
		WarningAsError: true,
	}
	designerCmd := builder.ConfigUpdateDBCmd(options)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 5, "Updating database configuration...")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		cleanup(true) // Remove client on error
		return nil, "", err
	}

	return result, result.Output, nil
}

// executeLoadCommand executes the config load command via SSH.
func (h *ConfigHandler) executeLoadCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
	client, cleanup, err := h.getSSHClient(ctx, cmd)
	if err != nil {
		return nil, "", err
	}
	defer cleanup(false)

	// Build command
	builder := h.buildCommandBuilder(cmd)

	// ConfigLoad command
	designerCmd := builder.ConfigLoadCmd(cmd.Params.SourcePath)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 5, "Loading configuration from file...")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		cleanup(true) // Remove client on error
		return nil, "", err
	}

	return result, result.Output, nil
}

// executeDumpCommand executes the config dump command via SSH.
func (h *ConfigHandler) executeDumpCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
	client, cleanup, err := h.getSSHClient(ctx, cmd)
	if err != nil {
		return nil, "", err
	}
	defer cleanup(false)

	// Build command
	builder := h.buildCommandBuilder(cmd)

	// ConfigDump command
	designerCmd := builder.ConfigDumpCmd(cmd.Params.TargetPath)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 5, "Dumping configuration to file...")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		cleanup(true) // Remove client on error
		return nil, "", err
	}

	return result, result.Output, nil
}

// getSSHClient gets SSH client from pool and returns cleanup function.
func (h *ConfigHandler) getSSHClient(ctx context.Context, cmd *designer.DesignerCommand) (*ssh.Client, func(bool), error) {
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
		return nil, nil, fmt.Errorf("failed to get SSH client: %w", err)
	}

	// Cleanup function
	cleanup := func(remove bool) {
		if remove {
			h.sshPool.RemoveClient(client)
		} else {
			h.sshPool.ReleaseClient(client)
		}
	}

	return client, cleanup, nil
}

// buildCommandBuilder creates command builder with connection parameters.
func (h *ConfigHandler) buildCommandBuilder(cmd *designer.DesignerCommand) *ssh.CommandBuilder {
	builder := ssh.NewCommandBuilder()
	if cmd.Params.Server && cmd.Params.ClusterHost != "" {
		builder.WithConnection(cmd.Params.ClusterHost, cmd.Params.InfobasePath, cmd.Infobase.User, cmd.Infobase.Password)
	} else {
		builder.WithConnection("", cmd.Params.InfobasePath, cmd.Infobase.User, cmd.Infobase.Password)
	}
	return builder
}

// monitorProgress monitors SSH output and publishes progress events.
func (h *ConfigHandler) monitorProgress(ctx context.Context, progressCh <-chan ssh.ProgressInfo, cmd *designer.DesignerCommand, correlationID string) {
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
					phase = "processing"
				}
				h.publishProgressWithPhase(ctx, correlationID, cmd, designer.ProgressStatusInProgress, percent, info.Line, phase)
			}
		}
	}
}

// publishProgress publishes a progress event.
func (h *ConfigHandler) publishProgress(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message string) {
	h.publishProgressWithPhase(ctx, correlationID, cmd, status, percentage, message, "")
}

// publishProgressWithPhase publishes a progress event with phase information.
func (h *ConfigHandler) publishProgressWithPhase(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message, phase string) {
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
func (h *ConfigHandler) publishSuccess(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, output string, duration time.Duration, operation string) error {
	// Publish progress: completed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusCompleted, 100, "Operation completed successfully")

	result := designer.NewDesignerResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, nil, output, duration)

	var eventType string
	switch operation {
	case "update":
		eventType = ConfigUpdateCompletedEvent
	case "load":
		eventType = ConfigLoadCompletedEvent
	case "dump":
		eventType = ConfigDumpCompletedEvent
	default:
		eventType = ConfigUpdateCompletedEvent
	}

	err := h.publisher.Publish(ctx,
		designer.StreamEventsCompleted,
		eventType,
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
		zap.String("event_type", eventType))

	return nil
}

// publishError publishes an error event to the event bus.
func (h *ConfigHandler) publishError(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, err error, output string, duration time.Duration, operation string) error {
	// Publish progress: failed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusFailed, 0, err.Error())

	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := designer.CommandTypeConfigUpdate

	switch operation {
	case "load":
		commandType = designer.CommandTypeConfigLoad
	case "dump":
		commandType = designer.CommandTypeConfigDump
	}

	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := designer.NewDesignerErrorResult(operationID, databaseID, commandType, err.Error(), "", output, 1, duration)

	var eventType string
	switch operation {
	case "update":
		eventType = ConfigUpdateFailedEvent
	case "load":
		eventType = ConfigLoadFailedEvent
	case "dump":
		eventType = ConfigDumpFailedEvent
	default:
		eventType = ConfigUpdateFailedEvent
	}

	pubErr := h.publisher.Publish(ctx,
		designer.StreamEventsFailed,
		eventType,
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
		zap.String("event_type", eventType))

	return err
}
