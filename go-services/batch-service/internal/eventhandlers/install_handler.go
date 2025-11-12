package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"go.uber.org/zap"
)

const (
	// Channel names
	InstallCommandChannel   = "commands:batch-service:extension:install"
	InstallStartedChannel   = "events:batch-service:extension:install-started"
	InstalledEventChannel   = "events:batch-service:extension:installed"
	InstallFailedChannel    = "events:batch-service:extension:install-failed"

	// Event types
	ExtensionInstallStartedEvent = "batch.extension.install.started"
	ExtensionInstalledEvent      = "batch.extension.installed"
	ExtensionInstallFailedEvent  = "batch.extension.install.failed"
)

// ExtensionInstaller is the interface for extension installation
type ExtensionInstaller interface {
	InstallExtension(ctx context.Context, req *models.InstallExtensionRequest) (*models.InstallExtensionResponse, error)
}

// EventPublisher is the interface for publishing events
type EventPublisher interface {
	Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error
}

// InstallHandler handles install extension commands from the event bus
type InstallHandler struct {
	installer ExtensionInstaller
	publisher EventPublisher
	logger    *zap.Logger
}

// NewInstallHandler creates a new InstallHandler instance
func NewInstallHandler(installer ExtensionInstaller, pub EventPublisher, logger *zap.Logger) *InstallHandler {
	return &InstallHandler{
		installer: installer,
		publisher: pub,
		logger:    logger,
	}
}

// HandleInstallCommand handles install extension command from the event bus
func (h *InstallHandler) HandleInstallCommand(ctx context.Context, envelope *events.Envelope) error {
	// Parse payload
	var payload InstallCommandPayload
	if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
		h.logger.Error("failed to parse install command payload",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		return h.publishError(ctx, envelope.CorrelationID, payload, fmt.Errorf("invalid payload: %w", err))
	}

	// Validate required fields
	if payload.DatabaseID == "" || payload.Server == "" || payload.InfobaseName == "" {
		h.logger.Error("missing required fields in install command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("database_id", payload.DatabaseID),
			zap.String("server", payload.Server),
			zap.String("infobase_name", payload.InfobaseName))
		return h.publishError(ctx, envelope.CorrelationID, payload,
			fmt.Errorf("database_id, server, and infobase_name are required"))
	}

	if payload.ExtensionPath == "" || payload.ExtensionName == "" {
		h.logger.Error("missing extension details in install command",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.String("extension_path", payload.ExtensionPath),
			zap.String("extension_name", payload.ExtensionName))
		return h.publishError(ctx, envelope.CorrelationID, payload,
			fmt.Errorf("extension_path and extension_name are required"))
	}

	h.logger.Info("handling install command",
		zap.String("correlation_id", envelope.CorrelationID),
		zap.String("database_id", payload.DatabaseID),
		zap.String("infobase_name", payload.InfobaseName),
		zap.String("extension_name", payload.ExtensionName))

	// Publish "started" event immediately
	if err := h.publishStarted(ctx, envelope.CorrelationID, payload); err != nil {
		h.logger.Error("failed to publish started event",
			zap.String("correlation_id", envelope.CorrelationID),
			zap.Error(err))
		// Don't fail the handler, continue with installation
	}

	// Start async installation
	go h.executeInstallation(context.Background(), envelope.CorrelationID, payload)

	// Return nil to ACK the command message
	return nil
}

// executeInstallation performs the actual installation asynchronously
func (h *InstallHandler) executeInstallation(ctx context.Context, correlationID string, payload InstallCommandPayload) {
	// Panic recovery
	defer func() {
		if r := recover(); r != nil {
			h.logger.Error("installation panic",
				zap.String("correlation_id", correlationID),
				zap.Any("panic", r))
			h.publishError(ctx, correlationID, payload, fmt.Errorf("panic: %v", r))
		}
	}()

	startTime := time.Now()

	h.logger.Info("starting installation execution",
		zap.String("correlation_id", correlationID),
		zap.String("database_id", payload.DatabaseID),
		zap.String("infobase_name", payload.InfobaseName))

	// Build installation request
	installReq := &models.InstallExtensionRequest{
		Server:        payload.Server,
		InfobaseName:  payload.InfobaseName,
		Username:      payload.Username,
		Password:      payload.Password,
		ExtensionName: payload.ExtensionName,
		ExtensionPath: payload.ExtensionPath,
	}

	// Execute installation through v8executor
	resp, err := h.installer.InstallExtension(ctx, installReq)
	duration := time.Since(startTime).Seconds()

	if err != nil {
		h.logger.Error("installation failed",
			zap.String("correlation_id", correlationID),
			zap.String("database_id", payload.DatabaseID),
			zap.String("infobase_name", payload.InfobaseName),
			zap.Float64("duration_seconds", duration),
			zap.Error(err))
		h.publishError(ctx, correlationID, payload, err)
		return
	}

	// Publish success event
	h.logger.Info("installation completed successfully",
		zap.String("correlation_id", correlationID),
		zap.String("database_id", payload.DatabaseID),
		zap.String("infobase_name", payload.InfobaseName),
		zap.Float64("duration_seconds", duration))

	h.publishSuccess(ctx, correlationID, payload, resp.DurationSeconds)
}

// publishStarted publishes a "started" event to the event bus
func (h *InstallHandler) publishStarted(ctx context.Context, correlationID string, payload InstallCommandPayload) error {
	startedPayload := InstallStartedPayload{
		DatabaseID:    payload.DatabaseID,
		InfobaseName:  payload.InfobaseName,
		ExtensionName: payload.ExtensionName,
		Message:       fmt.Sprintf("Extension installation started for '%s' on '%s'", payload.ExtensionName, payload.InfobaseName),
	}

	err := h.publisher.Publish(ctx,
		InstallStartedChannel,
		ExtensionInstallStartedEvent,
		startedPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish started event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", InstallStartedChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish started event: %w", err)
	}

	h.logger.Info("started event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", InstallStartedChannel),
		zap.String("event_type", ExtensionInstallStartedEvent))

	return nil
}

// publishSuccess publishes a success event to the event bus
func (h *InstallHandler) publishSuccess(ctx context.Context, correlationID string, payload InstallCommandPayload, durationSeconds float64) error {
	successPayload := InstallSuccessPayload{
		DatabaseID:      payload.DatabaseID,
		InfobaseName:    payload.InfobaseName,
		ExtensionName:   payload.ExtensionName,
		DurationSeconds: durationSeconds,
		Message:         fmt.Sprintf("Extension '%s' installed successfully on '%s'", payload.ExtensionName, payload.InfobaseName),
	}

	err := h.publisher.Publish(ctx,
		InstalledEventChannel,
		ExtensionInstalledEvent,
		successPayload,
		correlationID)

	if err != nil {
		h.logger.Error("failed to publish success event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", InstalledEventChannel),
			zap.Error(err))
		return fmt.Errorf("failed to publish success event: %w", err)
	}

	h.logger.Info("success event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", InstalledEventChannel),
		zap.String("event_type", ExtensionInstalledEvent))

	return nil
}

// publishError publishes an error event to the event bus
func (h *InstallHandler) publishError(ctx context.Context, correlationID string, payload InstallCommandPayload, err error) error {
	errorPayload := ErrorPayload{
		DatabaseID:   payload.DatabaseID,
		InfobaseName: payload.InfobaseName,
		Error:        err.Error(),
		Message:      fmt.Sprintf("Failed to install extension on '%s'", payload.InfobaseName),
	}

	pubErr := h.publisher.Publish(ctx,
		InstallFailedChannel,
		ExtensionInstallFailedEvent,
		errorPayload,
		correlationID)

	if pubErr != nil {
		h.logger.Error("failed to publish error event",
			zap.String("correlation_id", correlationID),
			zap.String("channel", InstallFailedChannel),
			zap.Error(pubErr))
		// Return original error, not publish error
		return err
	}

	h.logger.Info("error event published",
		zap.String("correlation_id", correlationID),
		zap.String("channel", InstallFailedChannel),
		zap.String("event_type", ExtensionInstallFailedEvent))

	// Return original error so Watermill can handle retry logic
	return err
}
