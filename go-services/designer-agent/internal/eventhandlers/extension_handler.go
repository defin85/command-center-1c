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
	// ExtensionDefaultTimeout is the default timeout for extension operations.
	ExtensionDefaultTimeout = 30 * time.Minute

	// Event types for extension operations.
	ExtensionInstallCompletedEvent = "designer.extension.install.completed"
	ExtensionInstallFailedEvent    = "designer.extension.install.failed"
	ExtensionRemoveCompletedEvent  = "designer.extension.remove.completed"
	ExtensionRemoveFailedEvent     = "designer.extension.remove.failed"
)

// ExtensionHandler handles extension install/remove commands from the event bus.
type ExtensionHandler struct {
	sshPool     SSHExecutor
	publisher   EventPublisher
	redisClient RedisClient
	metrics     MetricsRecorder
	timeline    TimelineRecorder
	logger      *zap.Logger
}

// NewExtensionHandler creates a new ExtensionHandler instance.
func NewExtensionHandler(pool SSHExecutor, pub EventPublisher, redisClient RedisClient, metrics MetricsRecorder, timeline TimelineRecorder, logger *zap.Logger) *ExtensionHandler {
	return &ExtensionHandler{
		sshPool:     pool,
		publisher:   pub,
		redisClient: redisClient,
		metrics:     metrics,
		timeline:    timeline,
		logger:      logger.With(zap.String("handler", "extension")),
	}
}

// recordMetric records a metric if MetricsRecorder is available.
func (h *ExtensionHandler) recordMetric(operation, status string, duration time.Duration) {
	if h.metrics != nil {
		h.metrics.RecordCommand(operation, status, duration.Seconds())
	}
}

// HandleInstallCommand handles extension install command from the event bus.
func (h *ExtensionHandler) HandleInstallCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse extension install command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start), true)
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid extension install command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start), true)
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeExtensionInstall {
		h.logger.Error("wrong command type for extension install handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeExtensionInstall),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeExtensionInstall, cmd.CommandType),
			"", time.Since(start), true)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "extension-install", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate extension install command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("extension_name", cmd.Params.ExtensionName))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0)
	}

	h.logger.Info("handling extension install command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("extension_name", cmd.Params.ExtensionName))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.received", map[string]interface{}{
			"command_type":   cmd.CommandType,
			"extension_name": cmd.Params.ExtensionName,
		})
	}

	// Publish progress: started
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting extension installation")

	// Get timeout
	timeout := ExtensionDefaultTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeInstallCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute extension install",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("extension_name", cmd.Params.ExtensionName),
			zap.Error(err))
		// Record metrics for failed operation
		h.recordMetric("extension_install", "error", duration)
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration, true)
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("extension install failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("extension_name", cmd.Params.ExtensionName),
			zap.Int("exit_code", result.ExitCode),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		h.recordMetric("extension_install", "error", duration)
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration, true)
	}

	// Record metrics for successful operation
	h.recordMetric("extension_install", "success", duration)
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]interface{}{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("extension installed successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("extension_name", cmd.Params.ExtensionName),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration)
}

// HandleRemoveCommand handles extension remove command from the event bus.
func (h *ExtensionHandler) HandleRemoveCommand(ctx context.Context, envelope *events.Envelope) error {
	start := time.Now()

	// Parse payload as DesignerCommand
	var cmd designer.DesignerCommand
	if err := json.Unmarshal(envelope.Payload, &cmd); err != nil {
		h.logger.Error("failed to parse extension remove command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, fmt.Errorf("invalid payload: %w", err), "", time.Since(start), false)
	}

	// Validate command
	if err := cmd.Validate(); err != nil {
		h.logger.Error("invalid extension remove command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, "", time.Since(start), false)
	}

	// Validate command type
	if cmd.CommandType != designer.CommandTypeExtensionRemove {
		h.logger.Error("wrong command type for extension remove handler",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("expected", designer.CommandTypeExtensionRemove),
			zap.String("actual", cmd.CommandType))
		return h.publishError(ctx, envelope.CorrelationID, &cmd,
			fmt.Errorf("expected command type '%s', got '%s'", designer.CommandTypeExtensionRemove, cmd.CommandType),
			"", time.Since(start), false)
	}

	// CHECK IDEMPOTENCY
	isFirst, err := CheckIdempotency(ctx, h.redisClient, envelope.CorrelationID, "extension-remove", h.logger)
	if err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if !isFirst {
		h.logger.Info("duplicate extension remove command detected, skipping operation (idempotent)",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("operation_id", cmd.OperationID),
			zap.String("extension_name", cmd.Params.ExtensionName))
		return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, "", 0)
	}

	h.logger.Info("handling extension remove command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("operation_id", cmd.OperationID),
		zap.String("database_id", cmd.DatabaseID),
		zap.String("extension_name", cmd.Params.ExtensionName))

	// Record timeline: command received
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.received", map[string]interface{}{
			"command_type":   cmd.CommandType,
			"extension_name": cmd.Params.ExtensionName,
		})
	}

	// Publish progress: started
	h.publishProgress(ctx, envelope.CorrelationID, &cmd, designer.ProgressStatusStarted, 0, "Starting extension removal")

	// Get timeout
	timeout := ExtensionDefaultTimeout
	if cmd.TimeoutSeconds > 0 {
		timeout = time.Duration(cmd.TimeoutSeconds) * time.Second
	}

	// Create timeout context
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute SSH command
	result, output, err := h.executeRemoveCommand(execCtx, &cmd, envelope.CorrelationID)
	duration := time.Since(start)

	if err != nil {
		h.logger.Error("failed to execute extension remove",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("extension_name", cmd.Params.ExtensionName),
			zap.Error(err))
		// Record metrics for failed operation
		h.recordMetric("extension_remove", "error", duration)
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        err.Error(),
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, err, output, duration, false)
	}

	if result.ExitCode != 0 || ContainsError(result.Output) {
		errMsg := ExtractError(result.Output)
		h.logger.Error("extension remove failed",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("extension_name", cmd.Params.ExtensionName),
			zap.Int("exit_code", result.ExitCode),
			zap.String("error", errMsg))
		// Record metrics for failed operation
		h.recordMetric("extension_remove", "error", duration)
		// Record timeline: command failed
		if h.timeline != nil {
			h.timeline.Record(ctx, cmd.OperationID, "designer.command.failed", map[string]interface{}{
				"command_type": cmd.CommandType,
				"error":        errMsg,
			})
		}
		return h.publishError(ctx, envelope.CorrelationID, &cmd, errors.New(errMsg), result.Output, duration, false)
	}

	// Record metrics for successful operation
	h.recordMetric("extension_remove", "success", duration)
	// Record timeline: command completed
	if h.timeline != nil {
		h.timeline.Record(ctx, cmd.OperationID, "designer.command.completed", map[string]interface{}{
			"command_type": cmd.CommandType,
			"duration_ms":  fmt.Sprintf("%d", duration.Milliseconds()),
		})
	}

	h.logger.Info("extension removed successfully",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("extension_name", cmd.Params.ExtensionName),
		zap.Duration("duration", duration))

	return h.publishSuccess(ctx, envelope.CorrelationID, &cmd, result.Output, duration)
}

// executeInstallCommand executes the extension install command via SSH.
func (h *ExtensionHandler) executeInstallCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
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

	// Extension install command
	designerCmd := builder.ExtensionInstallCmd(cmd.Params.ExtensionFile, cmd.Params.ExtensionName)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 10, "Connecting to server and executing command")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		h.sshPool.RemoveClient(client)
		return nil, "", err
	}

	return result, result.Output, nil
}

// executeRemoveCommand executes the extension remove command via SSH.
func (h *ExtensionHandler) executeRemoveCommand(ctx context.Context, cmd *designer.DesignerCommand, correlationID string) (*ssh.CommandResult, string, error) {
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

	// Extension remove command
	designerCmd := builder.ExtensionRemoveCmd(cmd.Params.ExtensionName)

	// Create progress channel
	progressCh := make(chan ssh.ProgressInfo, 100)
	defer close(progressCh)

	// Start progress monitoring
	go h.monitorProgress(ctx, progressCh, cmd, correlationID)

	// Publish progress: in_progress
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusInProgress, 10, "Connecting to server and executing command")

	// Execute command
	result, err := client.ExecuteCommandWithProgress(ctx, designerCmd.String(), progressCh)
	if err != nil {
		h.sshPool.RemoveClient(client)
		return nil, "", err
	}

	return result, result.Output, nil
}

// monitorProgress monitors SSH output and publishes progress events.
func (h *ExtensionHandler) monitorProgress(ctx context.Context, progressCh <-chan ssh.ProgressInfo, cmd *designer.DesignerCommand, correlationID string) {
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
func (h *ExtensionHandler) publishProgress(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message string) {
	h.publishProgressWithPhase(ctx, correlationID, cmd, status, percentage, message, "")
}

// publishProgressWithPhase publishes a progress event with phase information.
func (h *ExtensionHandler) publishProgressWithPhase(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, status string, percentage int, message, phase string) {
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
func (h *ExtensionHandler) publishSuccess(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, output string, duration time.Duration) error {
	// Publish progress: completed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusCompleted, 100, "Operation completed successfully")

	result := designer.NewDesignerResult(cmd.OperationID, cmd.DatabaseID, cmd.CommandType, nil, output, duration)

	eventType := ExtensionInstallCompletedEvent
	if cmd.CommandType == designer.CommandTypeExtensionRemove {
		eventType = ExtensionRemoveCompletedEvent
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
func (h *ExtensionHandler) publishError(ctx context.Context, correlationID string, cmd *designer.DesignerCommand, err error, output string, duration time.Duration, isInstall bool) error {
	// Publish progress: failed
	h.publishProgress(ctx, correlationID, cmd, designer.ProgressStatusFailed, 0, err.Error())

	// Handle nil or incomplete command
	operationID := ""
	databaseID := ""
	commandType := designer.CommandTypeExtensionInstall
	if !isInstall {
		commandType = designer.CommandTypeExtensionRemove
	}

	if cmd != nil {
		operationID = cmd.OperationID
		databaseID = cmd.DatabaseID
		if cmd.CommandType != "" {
			commandType = cmd.CommandType
		}
	}

	result := designer.NewDesignerErrorResult(operationID, databaseID, commandType, err.Error(), "", output, 1, duration)

	eventType := ExtensionInstallFailedEvent
	if !isInstall {
		eventType = ExtensionRemoveFailedEvent
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
