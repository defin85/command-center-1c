// go-services/worker/internal/drivers/extensionops/driver.go
package extensionops

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	sharedEvents "github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/clusterinfo"
	"github.com/commandcenter1c/commandcenter/worker/internal/config"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/cli"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/commandcenter1c/commandcenter/worker/internal/statemachine"
)

// ExecutionMode represents execution mode (Event-Driven only since Phase 3).
type ExecutionMode string

const (
	ModeEventDriven ExecutionMode = "event_driven"
)

// InstallDriver executes install_extension operations via state machine.
type InstallDriver struct {
	featureFlags    *config.FeatureFlags
	smConfig        *statemachine.Config
	clusterResolver clusterinfo.Resolver
	credsClient     credentials.Fetcher
	redisClient     *redis.Client
	eventSubscriber *sharedEvents.Subscriber
	timeline        tracing.TimelineRecorder
}

// NewInstallDriver creates a new driver for install_extension.
func NewInstallDriver(
	featureFlags *config.FeatureFlags,
	clusterResolver clusterinfo.Resolver,
	credsClient credentials.Fetcher,
	redisClient *redis.Client,
	eventSubscriber *sharedEvents.Subscriber,
	timeline tracing.TimelineRecorder,
) *InstallDriver {
	if featureFlags == nil {
		featureFlags = config.NewFeatureFlags()
	}
	if clusterResolver == nil {
		clusterResolver = &clusterinfo.NullResolver{}
	}
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}

	smConfig := statemachine.LoadFromEnv(nil)

	return &InstallDriver{
		featureFlags:    featureFlags,
		smConfig:        smConfig,
		clusterResolver: clusterResolver,
		credsClient:     credsClient,
		redisClient:     redisClient,
		eventSubscriber: eventSubscriber,
		timeline:        timeline,
	}
}

func (d *InstallDriver) Name() string { return "extension-install" }

func (d *InstallDriver) OperationTypes() []string { return []string{"install_extension"} }

func (d *InstallDriver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	res := d.ProcessExtensionInstall(ctx, msg, databaseID)
	res.DatabaseID = databaseID
	return res, nil
}

// ProcessExtensionInstall processes extension installation via Event-Driven State Machine.
// HTTP Sync mode has been removed in Phase 3 cleanup.
func (d *InstallDriver) ProcessExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	start := time.Now()
	log := logger.GetLogger()

	mode := ModeEventDriven

	log.Infof("processing extension install: operation_id=%s, database_id=%s, mode=%s",
		msg.OperationID, databaseID, string(mode))

	// Record decision metrics (if metrics enabled)
	metrics.ExecutionMode.WithLabelValues(string(mode)).Inc()

	// Execute via Event-Driven State Machine (only mode since Phase 3)
	result, err := d.processEventDriven(ctx, msg, databaseID)

	// Record metrics
	duration := time.Since(start)
	durationSeconds := duration.Seconds()
	metrics.ExecutionDuration.WithLabelValues(string(mode)).Observe(durationSeconds)

	if err != nil {
		metrics.ExecutionFailure.WithLabelValues(string(mode)).Inc()
		log.Errorf("execution failed: mode=%s, error=%v, duration=%v",
			string(mode), err, duration)

		// Return error result
		result = models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("%s mode failed: %v", mode, err),
			ErrorCode:  "EXECUTION_ERROR",
			Duration:   duration.Seconds(),
		}
	} else {
		metrics.ExecutionSuccess.WithLabelValues(string(mode)).Inc()
		log.Infof("execution completed: mode=%s, success=%v, duration=%v",
			string(mode), result.Success, duration)
	}

	return result
}

// validateExtensionInstallParams validates extension installation parameters.
func validateExtensionInstallParams(data map[string]interface{}) (extensionName, extensionPath, databaseID string, err error) {
	// Validate extension_name
	extensionName, ok := data["extension_name"].(string)
	if !ok || extensionName == "" {
		return "", "", "", fmt.Errorf("extension_name is required")
	}

	// Length validation
	if len(extensionName) > 255 {
		return "", "", "", fmt.Errorf("extension_name too long (max 255 chars): %d", len(extensionName))
	}

	// Format validation (allow Unicode letters, digits, underscore/dash/space)
	// Allow Cyrillic and other Unicode characters for extension names
	validNamePattern := regexp.MustCompile(`^[\p{L}\p{N}_\- ]+$`)
	if !validNamePattern.MatchString(extensionName) {
		return "", "", "", fmt.Errorf("extension_name contains invalid characters: %s", extensionName)
	}

	// Validate extension_path
	extensionPath, ok = data["extension_path"].(string)
	if !ok || extensionPath == "" {
		return "", "", "", fmt.Errorf("extension_path is required")
	}

	// Path traversal protection
	cleanPath := filepath.Clean(extensionPath)
	if strings.Contains(cleanPath, "..") {
		return "", "", "", fmt.Errorf("path traversal detected in extension_path: %s", extensionPath)
	}

	// Length validation
	if len(extensionPath) > 1024 {
		return "", "", "", fmt.Errorf("extension_path too long (max 1024 chars): %d", len(extensionPath))
	}

	// Validate database_id (if present in data, for processEventDriven it comes from msg)
	if dbID, ok := data["database_id"].(string); ok {
		if dbID == "" {
			return "", "", "", fmt.Errorf("database_id cannot be empty")
		}
		databaseID = dbID
	}

	return extensionName, extensionPath, databaseID, nil
}

// processEventDriven executes through Event-Driven State Machine.
// This is the REAL implementation - NO fallback to HTTP Sync!
func (d *InstallDriver) processEventDriven(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	log := logger.GetLogger()
	start := time.Now()

	log.Infof("[Event-Driven] Starting State Machine execution: operation_id=%s, database_id=%s",
		msg.OperationID, databaseID)

	// Step 1: Validate parameters
	extensionName, extensionPath, _, err := validateExtensionInstallParams(msg.Payload.Data)
	if err != nil {
		log.Errorf("[Event-Driven] Parameter validation failed: %v", err)
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("parameter validation failed: %v", err),
			ErrorCode:  "VALIDATION_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, err
	}

	log.Infof("[Event-Driven] Parameters validated: extension_name=%s, extension_path=%s",
		extensionName, extensionPath)

	// Step 2: Generate correlation ID for this workflow
	correlationID := fmt.Sprintf("%s-%s-%d", msg.OperationID, databaseID, time.Now().UnixNano())

	log.Infof("[Event-Driven] Generated correlation_id=%s", correlationID)

	// Step 3: Resolve cluster info from Orchestrator (NO fallback!)
	resolveStart := time.Now()
	clusterInfo, err := d.clusterResolver.Resolve(ctx, databaseID)
	resolveDuration := time.Since(resolveStart)
	metrics.RecordClusterResolveDuration(resolveDuration.Seconds())

	if err != nil {
		log.Errorf("[Event-Driven] Failed to resolve cluster info: database_id=%s, error=%v, duration=%v",
			databaseID, err, resolveDuration)
		// NO fallback - return error directly
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to resolve cluster info: %v", err),
			ErrorCode:  "CLUSTER_RESOLVE_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, fmt.Errorf("failed to resolve cluster info for database %s: %w", databaseID, err)
	}

	log.Infof("[Event-Driven] Cluster info resolved: database_id=%s, cluster_id=%s, infobase_id=%s, duration=%v",
		databaseID, clusterInfo.ClusterID, clusterInfo.InfobaseID, resolveDuration)

	// Step 4: Create State Machine
	useDirectCLI := os.Getenv("USE_DIRECT_CLI") != "false"
	installer, installerErr := cli.NewExtensionInstallerFromEnv()
	if installerErr != nil {
		log.Warnf("[Event-Driven] CLI installer not configured: %v (fallback to batch-service)", installerErr)
	}

	var (
		creds    *credentials.DatabaseCredentials
		adapter  statemachine.ExtensionInstaller
		credsErr error
	)
	if useDirectCLI && installerErr == nil && installer != nil {
		creds, credsErr = d.fetchDesignerCredentials(ctx, databaseID)
		if credsErr != nil {
			log.Errorf("[Event-Driven] Failed to fetch designer credentials: database_id=%s, error=%v",
				databaseID, credsErr)
			return models.DatabaseResultV2{
				DatabaseID: databaseID,
				Success:    false,
				Error:      fmt.Sprintf("failed to fetch designer credentials: %v", credsErr),
				ErrorCode:  "CREDENTIALS_ERROR",
				Duration:   time.Since(start).Seconds(),
			}, fmt.Errorf("failed to fetch designer credentials for database %s: %w", databaseID, credsErr)
		}
		adapter = &cliInstallerAdapter{installer: installer}
	}

	credsProvider := &designerCredsProvider{fetcher: d.credsClient}
	clusterInfoProvider := &clusterInfoProvider{resolver: d.clusterResolver}

	sm, err := d.createStateMachine(
		ctx,
		msg.OperationID,
		databaseID,
		correlationID,
		clusterInfo,
		extensionName,
		extensionPath,
		adapter,
		creds,
		credsProvider,
		clusterInfoProvider,
	)
	if err != nil {
		metrics.RecordStateMachineCreated(false)
		log.Errorf("[Event-Driven] Failed to create State Machine: operation_id=%s, error=%v",
			msg.OperationID, err)
		// NO fallback - return error directly
		return models.DatabaseResultV2{
			DatabaseID: databaseID,
			Success:    false,
			Error:      fmt.Sprintf("failed to create state machine: %v", err),
			ErrorCode:  "STATE_MACHINE_CREATE_ERROR",
			Duration:   time.Since(start).Seconds(),
		}, fmt.Errorf("failed to create state machine: %w", err)
	}

	metrics.RecordStateMachineCreated(true)
	log.Infof("[Event-Driven] State Machine created: sm_id=%s, correlation_id=%s",
		sm.ID, correlationID)

	// Step 5: Run State Machine
	log.Infof("[Event-Driven] Running State Machine: sm_id=%s", sm.ID)
	runErr := sm.Run(ctx)

	// Critical #2 Fix: Ensure publisher is closed after SM completes (success or failure)
	// Publisher is created per-SM in createStateMachine, so we must clean it up here
	defer func() {
		if closeErr := sm.ClosePublisher(); closeErr != nil {
			log.Warnf("[Event-Driven] Failed to close publisher for SM %s: %v", sm.ID, closeErr)
		}
	}()

	// Get final state BEFORE closing (important!)
	finalState := sm.State
	smDuration := time.Since(start)

	log.Infof("[Event-Driven] State Machine finished: sm_id=%s, final_state=%s, duration=%v, error=%v",
		sm.ID, finalState, smDuration, runErr)

	// Record State Machine final state metric
	metrics.RecordStateMachineFinalState(string(finalState))

	// Step 6: Build result based on final state
	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
		Duration:   smDuration.Seconds(),
	}

	// Check final state to determine success/failure
	if finalState == statemachine.StateCompleted {
		result.Success = true
		result.Data = map[string]interface{}{
			"extension_name": extensionName,
			"extension_path": extensionPath,
			"mode":           "event_driven",
			"correlation_id": correlationID,
			"cluster_id":     clusterInfo.ClusterID,
			"infobase_id":    clusterInfo.InfobaseID,
			"final_state":    string(finalState),
		}
		log.Infof("[Event-Driven] Operation completed successfully: operation_id=%s, database_id=%s",
			msg.OperationID, databaseID)
	} else {
		result.Success = false
		result.ErrorCode = "STATE_MACHINE_ERROR"

		// Build error message based on state and run error
		if runErr != nil {
			result.Error = fmt.Sprintf("state machine failed in state '%s': %v", finalState, runErr)
		} else {
			result.Error = fmt.Sprintf("state machine ended in unexpected state: %s", finalState)
		}

		// Add additional context to Data for debugging
		result.Data = map[string]interface{}{
			"mode":           "event_driven",
			"correlation_id": correlationID,
			"final_state":    string(finalState),
		}

		log.Errorf("[Event-Driven] Operation failed: operation_id=%s, database_id=%s, final_state=%s, error=%s",
			msg.OperationID, databaseID, finalState, result.Error)

		// If SM reached Compensating state, compensation was executed
		if finalState == statemachine.StateFailed {
			log.Infof("[Event-Driven] State Machine executed compensation actions before failing")
		}
	}

	// Note: Metrics for Event-Driven execution are recorded in ProcessExtensionInstall()
	// Additional SM-specific metrics can be added here if needed

	return result, runErr
}

// GetFeatureFlags returns current feature flags configuration.
func (d *InstallDriver) GetFeatureFlags() map[string]interface{} {
	if d.featureFlags == nil {
		return map[string]interface{}{}
	}
	return d.featureFlags.GetConfig()
}

// ReloadFeatureFlags hot-reloads feature flags from environment.
func (d *InstallDriver) ReloadFeatureFlags() error {
	log := logger.GetLogger()
	log.Infof("reloading feature flags from environment")
	if d.featureFlags == nil {
		return fmt.Errorf("feature flags not configured")
	}
	return d.featureFlags.Reload()
}

// GetClusterResolver returns the ClusterInfoResolver instance.
func (d *InstallDriver) GetClusterResolver() clusterinfo.Resolver {
	return d.clusterResolver
}

// SetClusterResolver sets a custom ClusterInfoResolver (useful for testing).
func (d *InstallDriver) SetClusterResolver(resolver clusterinfo.Resolver) {
	d.clusterResolver = resolver
}

// ResolveClusterInfo resolves cluster info for a database ID.
// This is a convenience method that wraps clusterResolver.Resolve.
func (d *InstallDriver) ResolveClusterInfo(ctx context.Context, databaseID string) (*clusterinfo.ClusterInfo, error) {
	if d.clusterResolver == nil {
		return nil, fmt.Errorf("ClusterInfoResolver not configured")
	}
	return d.clusterResolver.Resolve(ctx, databaseID)
}

// --- State Machine Factory ---

// publisherWrapper wraps shared/events.Publisher to implement statemachine.EventPublisher.
type publisherWrapper struct {
	publisher *sharedEvents.Publisher
}

// Publish implements statemachine.EventPublisher.
func (pw *publisherWrapper) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	return pw.publisher.Publish(ctx, channel, eventType, payload, correlationID)
}

// Close implements statemachine.EventPublisher.
func (pw *publisherWrapper) Close() error {
	return pw.publisher.Close()
}

// subscriberWrapper wraps shared/events.Subscriber to implement statemachine.EventSubscriber.
// IMPORTANT: This wrapper does NOT close the underlying subscriber because it's shared
// across multiple State Machines and managed by TaskProcessor.
type subscriberWrapper struct {
	subscriber *sharedEvents.Subscriber
}

// Subscribe implements statemachine.EventSubscriber.
func (sw *subscriberWrapper) Subscribe(channel string, handler sharedEvents.HandlerFunc) error {
	return sw.subscriber.Subscribe(channel, handler)
}

// Close implements statemachine.EventSubscriber.
// DO NOT close shared subscriber - it's managed by TaskProcessor.
func (sw *subscriberWrapper) Close() error {
	// Critical #1 Fix: shared subscriber lifecycle is managed by TaskProcessor,
	// not by individual State Machines. Closing here would break all other SMs.
	return nil
}

// createStateMachine creates a new ExtensionInstallStateMachine instance.
// Returns error if required dependencies are not available.
func (d *InstallDriver) createStateMachine(
	ctx context.Context,
	operationID string,
	databaseID string,
	correlationID string,
	clusterInfo *clusterinfo.ClusterInfo,
	extensionName string,
	extensionPath string,
	installer statemachine.ExtensionInstaller,
	creds *credentials.DatabaseCredentials,
	credsProvider statemachine.DesignerCredentialsProvider,
	clusterInfoProvider statemachine.ClusterInfoProvider,
) (*statemachine.ExtensionInstallStateMachine, error) {
	log := logger.GetLogger()

	if d.redisClient == nil {
		return nil, fmt.Errorf("redis client not configured for State Machine")
	}

	// Check subscriber availability (graceful degradation)
	if d.eventSubscriber == nil {
		log.Warnf("event subscriber not available, State Machine cannot be created: operation_id=%s, database_id=%s",
			operationID, databaseID)
		return nil, fmt.Errorf("event subscriber not available for State Machine")
	}

	// Create publisher for State Machine
	// Note: We create a new publisher instance for each State Machine
	// to ensure proper isolation and cleanup
	publisher, err := sharedEvents.NewPublisher(d.redisClient, "worker-state-machine", nil)
	if err != nil {
		log.Errorf("failed to create event publisher for State Machine: %v", err)
		return nil, fmt.Errorf("failed to create event publisher: %w", err)
	}

	// Wrap publisher and subscriber to implement statemachine interfaces
	pubWrapper := &publisherWrapper{publisher: publisher}
	subWrapper := &subscriberWrapper{subscriber: d.eventSubscriber}

	// Create State Machine with timeline
	sm, err := statemachine.NewStateMachine(
		ctx,
		operationID,
		databaseID,
		correlationID,
		pubWrapper,
		subWrapper,
		d.redisClient,
		d.smConfig,
		statemachine.WithTimeline(d.timeline),
		statemachine.WithExtensionInstaller(installer),
		statemachine.WithDesignerCredentialsProvider(credsProvider),
		statemachine.WithClusterInfoProvider(clusterInfoProvider),
	)
	if err != nil {
		// Clean up publisher on error
		publisher.Close()
		log.Errorf("failed to create State Machine: %v", err)
		return nil, fmt.Errorf("failed to create State Machine: %w", err)
	}

	// Set workflow data from ClusterInfo
	if clusterInfo != nil {
		sm.ClusterID = clusterInfo.ClusterID
		sm.InfobaseID = clusterInfo.InfobaseID
	}
	sm.ExtensionName = extensionName
	sm.ExtensionPath = extensionPath
	if creds != nil {
		sm.ServerAddress = creds.ServerAddress
		sm.ServerPort = creds.ServerPort
		sm.InfobaseName = creds.InfobaseName
		sm.Username = creds.Username
		sm.Password = creds.Password
	}
	if clusterInfo != nil {
		sm.RASServer = clusterInfo.RASServer
		sm.ClusterUser = clusterInfo.ClusterUser
		sm.ClusterPwd = clusterInfo.ClusterPwd
	}

	log.Infof("State Machine created: id=%s, operation_id=%s, database_id=%s, correlation_id=%s",
		sm.ID, operationID, databaseID, correlationID)

	return sm, nil
}

func (d *InstallDriver) fetchDesignerCredentials(ctx context.Context, databaseID string) (*credentials.DatabaseCredentials, error) {
	if d.credsClient == nil {
		return nil, fmt.Errorf("credentials client not configured")
	}

	creds, err := d.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		return nil, err
	}

	if creds.ServerAddress == "" || creds.InfobaseName == "" || creds.Username == "" {
		return nil, fmt.Errorf("designer credentials are incomplete for database %s", databaseID)
	}

	return creds, nil
}

type cliInstallerAdapter struct {
	installer *cli.ExtensionInstaller
}

func (a *cliInstallerAdapter) InstallExtension(ctx context.Context, req statemachine.ExtensionInstallRequest) (*statemachine.ExtensionInstallResult, error) {
	if a == nil || a.installer == nil {
		return nil, fmt.Errorf("cli installer not configured")
	}

	res, err := a.installer.InstallExtension(ctx, cli.InstallRequest{
		Server:        req.Server,
		InfobaseName:  req.InfobaseName,
		Username:      req.Username,
		Password:      req.Password,
		ExtensionName: req.ExtensionName,
		ExtensionPath: req.ExtensionPath,
	})
	if res == nil {
		return nil, err
	}
	return &statemachine.ExtensionInstallResult{
		Duration: res.Duration,
		Output:   res.Output,
	}, err
}

type designerCredsProvider struct {
	fetcher credentials.Fetcher
}

func (p *designerCredsProvider) Fetch(ctx context.Context, databaseID string) (*statemachine.DesignerCredentials, error) {
	if p == nil || p.fetcher == nil {
		return nil, fmt.Errorf("credentials provider not configured")
	}

	creds, err := p.fetcher.Fetch(ctx, databaseID)
	if err != nil {
		return nil, err
	}

	if creds.ServerAddress == "" || creds.InfobaseName == "" || creds.Username == "" {
		return nil, fmt.Errorf("designer credentials are incomplete for database %s", databaseID)
	}

	return &statemachine.DesignerCredentials{
		ServerAddress: creds.ServerAddress,
		ServerPort:    creds.ServerPort,
		InfobaseName:  creds.InfobaseName,
		Username:      creds.Username,
		Password:      creds.Password,
	}, nil
}

type clusterInfoProvider struct {
	resolver clusterinfo.Resolver
}

func (p *clusterInfoProvider) Fetch(ctx context.Context, databaseID string) (*statemachine.ClusterInfo, error) {
	if p == nil || p.resolver == nil {
		return nil, fmt.Errorf("cluster info provider not configured")
	}

	info, err := p.resolver.Resolve(ctx, databaseID)
	if err != nil {
		return nil, err
	}
	if info == nil || info.ClusterID == "" || info.InfobaseID == "" {
		return nil, fmt.Errorf("cluster info is incomplete for database %s", databaseID)
	}

	return &statemachine.ClusterInfo{
		ClusterID:   info.ClusterID,
		InfobaseID:  info.InfobaseID,
		RASServer:   info.RASServer,
		ClusterUser: info.ClusterUser,
		ClusterPwd:  info.ClusterPwd,
	}, nil
}
