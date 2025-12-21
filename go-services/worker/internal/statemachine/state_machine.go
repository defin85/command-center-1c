package statemachine

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
	"github.com/redis/go-redis/v9"
)

// ExtensionInstallStateMachine orchestrates extension installation workflow
type ExtensionInstallStateMachine struct {
	// Identity
	ID            string
	OperationID   string
	DatabaseID    string
	CorrelationID string

	// State
	State        InstallState
	mu           sync.RWMutex
	lastActivity time.Time

	// Workflow data
	ClusterID     string
	InfobaseID    string
	ExtensionPath string
	ExtensionName string
	ServerAddress string
	ServerPort    int
	InfobaseName  string
	Username      string
	Password      string
	RASServer     string
	ClusterUser   string
	ClusterPwd    string

	// Event integration
	publisher EventPublisher

	// Dependencies
	redisClient *redis.Client
	config      *Config

	// Compensation
	compensationStack    []CompensationAction
	compensationExecutor *CompensationExecutor

	// Deduplication
	ctx    context.Context
	cancel context.CancelFunc

	// Control
	closeOnce sync.Once

	// Timeline for operation tracing
	timeline tracing.TimelineRecorder

	// Optional direct installer (CLI)
	extensionInstaller ExtensionInstaller

	// Optional credentials provider (re-init without persisted secrets)
	credentialsProvider DesignerCredentialsProvider

	// Optional cluster info provider (re-init without persisted secrets)
	clusterInfoProvider ClusterInfoProvider
}

// CompensationAction represents a compensation action
type CompensationAction struct {
	Name   string
	Action func(context.Context) error
}

// StateMachineOption is a functional option for configuring StateMachine
type StateMachineOption func(*ExtensionInstallStateMachine)

// WithCompensationExecutor sets the compensation executor for the state machine
func WithCompensationExecutor(executor *CompensationExecutor) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.compensationExecutor = executor
	}
}

// WithCompensationConfig creates and sets a compensation executor with the given config
func WithCompensationConfig(config *CompensationConfig, auditLogger AuditLogger, metrics MetricsRecorder) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.compensationExecutor = NewCompensationExecutor(config, auditLogger, metrics)
	}
}

// WithTimeline sets the timeline recorder for the state machine
func WithTimeline(timeline tracing.TimelineRecorder) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.timeline = timeline
	}
}

// WithExtensionInstaller sets a direct installer to avoid legacy batch pipeline.
func WithExtensionInstaller(installer ExtensionInstaller) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.extensionInstaller = installer
	}
}

// WithDesignerCredentialsProvider sets a provider for rehydrating credentials on resume.
func WithDesignerCredentialsProvider(provider DesignerCredentialsProvider) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.credentialsProvider = provider
	}
}

// WithClusterInfoProvider sets a provider for rehydrating cluster info on resume.
func WithClusterInfoProvider(provider ClusterInfoProvider) StateMachineOption {
	return func(sm *ExtensionInstallStateMachine) {
		sm.clusterInfoProvider = provider
	}
}

// NewStateMachine creates new state machine instance
func NewStateMachine(
	ctx context.Context,
	operationID, databaseID, correlationID string,
	publisher EventPublisher,
	redisClient *redis.Client,
	config *Config,
	opts ...StateMachineOption,
) (*ExtensionInstallStateMachine, error) {

	if publisher == nil {
		return nil, fmt.Errorf("publisher is required")
	}
	// redisClient is optional (for unit tests without persistence)
	if config == nil {
		config = DefaultConfig()
	}

	smCtx, cancel := context.WithCancel(ctx)

	sm := &ExtensionInstallStateMachine{
		ID:                fmt.Sprintf("sm-%s", correlationID),
		OperationID:       operationID,
		DatabaseID:        databaseID,
		CorrelationID:     correlationID,
		State:             StateInit,
		lastActivity:      time.Now(),
		publisher:         publisher,
		redisClient:       redisClient,
		config:            config,
		compensationStack: make([]CompensationAction, 0),
		ctx:               smCtx,
		cancel:            cancel,
	}

	// Apply options
	for _, opt := range opts {
		opt(sm)
	}

	// Initialize noop timeline if not provided via options
	if sm.timeline == nil {
		sm.timeline = tracing.NewNoopTimeline()
	}

	return sm, nil
}

// Run executes the state machine main loop
func (sm *ExtensionInstallStateMachine) Run(ctx context.Context) error {
	defer sm.cancel()
	defer sm.Close()

	// Record saga start in timeline
	sm.timeline.Record(ctx, sm.OperationID, "saga.started", map[string]interface{}{
		"correlation_id": sm.CorrelationID,
		"database_id":    sm.DatabaseID,
		"extension_name": sm.ExtensionName,
	})

	// Load state if exists (for recovery)
	if err := sm.loadState(ctx); err != nil {
		// Ignore error, start from Init
	}

	if err := sm.ensureClusterInfo(ctx); err != nil {
		return err
	}

	if err := sm.ensureDesignerCredentials(ctx); err != nil {
		return err
	}

	// Main state loop
	for !sm.State.IsFinal() {
		fmt.Printf("[StateMachine] Loop iteration, current state: %s (correlation_id=%s)\n", sm.State, sm.CorrelationID)

		select {
		case <-ctx.Done():
			fmt.Printf("[StateMachine] Context cancelled, saving state...\n")
			sm.saveState(ctx)
			return ctx.Err()
		default:
		}

		var err error
		switch sm.State {
		case StateInit:
			err = sm.handleInit(ctx)
		case StateJobsLocked:
			err = sm.handleJobsLocked(ctx)
		case StateSessionsClosed:
			err = sm.handleSessionsClosed(ctx)
		case StateExtensionInstalled:
			err = sm.handleExtensionInstalled(ctx)
		case StateCompensating:
			err = sm.executeCompensations(ctx)
		default:
			return fmt.Errorf("unknown state: %s", sm.State)
		}

		if err != nil {
			fmt.Printf("[StateMachine] Handler returned error: %v\n", err)

			// Decide next state based on current state and compensation stack
			nextState := StateFailed
			if len(sm.compensationStack) > 0 && CanTransition(sm.State, StateCompensating) {
				nextState = StateCompensating
			}

			fmt.Printf("[StateMachine] Transitioning to %s\n", nextState)
			sm.transitionTo(nextState)
		} else {
			fmt.Printf("[StateMachine] Handler completed successfully\n")
		}

		// Check if we reached final state (handler may have transitioned internally)
		if sm.State.IsFinal() {
			fmt.Printf("[StateMachine] Reached final state: %s\n", sm.State)
			break
		}
	}

	fmt.Printf("[StateMachine] Exited main loop, final state: %s\n", sm.State)

	// Record saga completion in timeline
	if sm.State == StateCompleted {
		sm.timeline.Record(sm.ctx, sm.OperationID, "saga.completed", map[string]interface{}{
			"correlation_id": sm.CorrelationID,
			"final_state":    string(sm.State),
		})
	} else {
		sm.timeline.Record(sm.ctx, sm.OperationID, "saga.failed", map[string]interface{}{
			"correlation_id": sm.CorrelationID,
			"final_state":    string(sm.State),
		})
	}

	return nil
}

func (sm *ExtensionInstallStateMachine) ensureDesignerCredentials(ctx context.Context) error {
	if sm.extensionInstaller == nil {
		return nil
	}
	if sm.ServerAddress != "" && sm.InfobaseName != "" && sm.Username != "" {
		return nil
	}
	if sm.credentialsProvider == nil {
		metrics.RecordDesignerCredentialsRehydrate(false)
		sm.timeline.Record(ctx, sm.OperationID, "designer.credentials.rehydrate.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       "credentials provider not configured",
		})
		return fmt.Errorf("designer credentials provider not configured")
	}

	fmt.Printf("[StateMachine] Rehydrating designer credentials from provider (no persistence): database_id=%s\n", sm.DatabaseID)

	creds, err := sm.credentialsProvider.Fetch(ctx, sm.DatabaseID)
	if err != nil {
		metrics.RecordDesignerCredentialsRehydrate(false)
		sm.timeline.Record(ctx, sm.OperationID, "designer.credentials.rehydrate.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
		})
		return fmt.Errorf("failed to fetch designer credentials: %w", err)
	}
	if creds == nil || creds.ServerAddress == "" || creds.InfobaseName == "" || creds.Username == "" {
		metrics.RecordDesignerCredentialsRehydrate(false)
		sm.timeline.Record(ctx, sm.OperationID, "designer.credentials.rehydrate.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       "designer credentials are incomplete",
		})
		return fmt.Errorf("designer credentials are incomplete")
	}

	sm.ServerAddress = creds.ServerAddress
	sm.ServerPort = creds.ServerPort
	sm.InfobaseName = creds.InfobaseName
	sm.Username = creds.Username
	sm.Password = creds.Password
	metrics.RecordDesignerCredentialsRehydrate(true)
	sm.timeline.Record(ctx, sm.OperationID, "designer.credentials.rehydrated", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"source":      "provider",
	})
	fmt.Printf("[StateMachine] Designer credentials rehydrated: database_id=%s\n", sm.DatabaseID)
	return nil
}

func (sm *ExtensionInstallStateMachine) clearDesignerCredentials() {
	sm.Password = ""
}

func (sm *ExtensionInstallStateMachine) ensureClusterInfo(ctx context.Context) error {
	if sm.ClusterID == "" || sm.InfobaseID == "" {
		if sm.clusterInfoProvider == nil {
			return fmt.Errorf("cluster info provider not configured")
		}
	}

	if sm.clusterInfoProvider == nil {
		return nil
	}

	if sm.RASServer != "" && sm.ClusterID != "" && sm.InfobaseID != "" {
		return nil
	}

	sm.timeline.Record(ctx, sm.OperationID, "clusterinfo.rehydrate.started", map[string]interface{}{
		"database_id": sm.DatabaseID,
	})

	info, err := sm.clusterInfoProvider.Fetch(ctx, sm.DatabaseID)
	if err != nil {
		sm.timeline.Record(ctx, sm.OperationID, "clusterinfo.rehydrate.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       err.Error(),
		})
		return fmt.Errorf("failed to fetch cluster info: %w", err)
	}
	if info == nil || info.ClusterID == "" || info.InfobaseID == "" {
		sm.timeline.Record(ctx, sm.OperationID, "clusterinfo.rehydrate.failed", map[string]interface{}{
			"database_id": sm.DatabaseID,
			"error":       "cluster info is incomplete",
		})
		return fmt.Errorf("cluster info is incomplete")
	}

	sm.ClusterID = info.ClusterID
	sm.InfobaseID = info.InfobaseID
	sm.RASServer = info.RASServer
	sm.ClusterUser = info.ClusterUser
	sm.ClusterPwd = info.ClusterPwd

	sm.timeline.Record(ctx, sm.OperationID, "clusterinfo.rehydrated", map[string]interface{}{
		"database_id": sm.DatabaseID,
		"source":      "provider",
	})
	return nil
}

// transitionTo transitions to new state
func (sm *ExtensionInstallStateMachine) transitionTo(newState InstallState) error {
	fmt.Printf("[StateMachine] transitionTo() called: %s -> %s\n", sm.State, newState)

	sm.mu.Lock()
	defer sm.mu.Unlock()

	if !CanTransition(sm.State, newState) {
		return fmt.Errorf("invalid transition from %s to %s", sm.State, newState)
	}

	oldState := sm.State
	sm.State = newState
	sm.lastActivity = time.Now()

	// Record state transition in timeline
	sm.timeline.Record(sm.ctx, sm.OperationID, "saga.transition", map[string]interface{}{
		"from_state":     string(oldState),
		"to_state":       string(newState),
		"correlation_id": sm.CorrelationID,
	})

	// Log transition
	fmt.Printf("[StateMachine] Transition: %s -> %s (correlation_id=%s)\n",
		oldState, newState, sm.CorrelationID)

	// Save state (use Unsafe version - we already hold lock!)
	fmt.Printf("[StateMachine] Calling saveStateUnsafe()...\n")
	if err := sm.saveStateUnsafe(sm.ctx); err != nil {
		fmt.Printf("[StateMachine] Failed to save state: %v\n", err)
	}
	fmt.Printf("[StateMachine] saveStateUnsafe() completed\n")

	fmt.Printf("[StateMachine] transitionTo() returning nil\n")
	return nil
}

// Close closes state machine and releases resources
// Critical #3 Fix: Uses sync.Once to ensure safe single close
func (sm *ExtensionInstallStateMachine) Close() error {
	sm.closeOnce.Do(func() {
		// Cancel context
		sm.cancel()
	})

	return nil
}

// ClosePublisher closes the publisher associated with this state machine
// Critical #2 Fix: Allows external cleanup of per-SM publisher
func (sm *ExtensionInstallStateMachine) ClosePublisher() error {
	if sm.publisher != nil {
		return sm.publisher.Close()
	}
	return nil
}
