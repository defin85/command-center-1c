package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/rasdirect"
)

type rasClient interface {
	UnlockScheduledJobs(ctx context.Context, clusterID, infobaseID, clusterUser, clusterPwd string) error
	Close() error
}

type rasClientFactory func(server string) (rasClient, error)

// WatchdogConfig holds configuration for the watchdog
type WatchdogConfig struct {
	CheckInterval    time.Duration // How often to check for stuck workflows (default: 5 min)
	StuckThreshold   time.Duration // How long before a workflow is considered stuck (default: 30 min)
	MaxRecoveryBatch int           // Maximum workflows to recover per check (default: 10)
}

// DefaultWatchdogConfig returns default watchdog configuration
func DefaultWatchdogConfig() *WatchdogConfig {
	return &WatchdogConfig{
		CheckInterval:    5 * time.Minute,
		StuckThreshold:   30 * time.Minute,
		MaxRecoveryBatch: 10,
	}
}

// Watchdog monitors and recovers stuck workflows
type Watchdog struct {
	redisClient     *redis.Client
	config          *WatchdogConfig
	publisher       EventPublisher
	orchestratorURL string
	smConfig        *Config
	clusterInfo     ClusterInfoProvider
	rasFactory      rasClientFactory
}

// NewWatchdog creates a new Watchdog instance
func NewWatchdog(
	redisClient *redis.Client,
	publisher EventPublisher,
	orchestratorURL string,
	smConfig *Config,
	config *WatchdogConfig,
	clusterInfo ClusterInfoProvider,
	rasFactory rasClientFactory,
) *Watchdog {
	if config == nil {
		config = DefaultWatchdogConfig()
	}
	if smConfig == nil {
		smConfig = DefaultConfig()
	}
	if rasFactory == nil {
		rasFactory = func(server string) (rasClient, error) {
			return rasdirect.NewClient(server)
		}
	}

	return &Watchdog{
		redisClient:     redisClient,
		config:          config,
		publisher:       publisher,
		orchestratorURL: orchestratorURL,
		smConfig:        smConfig,
		clusterInfo:     clusterInfo,
		rasFactory:      rasFactory,
	}
}

// Run starts the watchdog background goroutine
func (w *Watchdog) Run(ctx context.Context) {
	fmt.Printf("[Watchdog] Starting with interval=%v, threshold=%v, maxBatch=%d\n",
		w.config.CheckInterval, w.config.StuckThreshold, w.config.MaxRecoveryBatch)

	ticker := time.NewTicker(w.config.CheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			fmt.Printf("[Watchdog] Shutting down: %v\n", ctx.Err())
			return
		case <-ticker.C:
			w.checkStuckWorkflows(ctx)
		}
	}
}

// checkStuckWorkflows scans Redis for stuck workflows and recovers them
func (w *Watchdog) checkStuckWorkflows(ctx context.Context) {
	fmt.Printf("[Watchdog] Checking for stuck workflows...\n")

	// Scan Redis keys matching pattern workflow:*:state
	var cursor uint64
	var recoveredCount int
	pattern := "workflow:*:state"

	for {
		if recoveredCount >= w.config.MaxRecoveryBatch {
			fmt.Printf("[Watchdog] Reached max recovery batch limit (%d)\n", w.config.MaxRecoveryBatch)
			break
		}

		keys, nextCursor, err := w.redisClient.Scan(ctx, cursor, pattern, 100).Result()
		if err != nil {
			fmt.Printf("[Watchdog] Error scanning Redis keys: %v\n", err)
			return
		}

		for _, key := range keys {
			if recoveredCount >= w.config.MaxRecoveryBatch {
				break
			}

			state, err := w.loadStateFromKey(ctx, key)
			if err != nil {
				fmt.Printf("[Watchdog] Error loading state from %s: %v\n", key, err)
				continue
			}

			// Check if workflow is stuck
			if w.isStuck(state) {
				fmt.Printf("[Watchdog] Found stuck workflow: correlation_id=%s, state=%s, last_activity=%v\n",
					state.CorrelationID, state.State, state.LastActivity)

				if err := w.recoverWorkflow(ctx, state, key); err != nil {
					fmt.Printf("[Watchdog] Error recovering workflow %s: %v\n", state.CorrelationID, err)
				} else {
					recoveredCount++
				}
			}
		}

		cursor = nextCursor
		if cursor == 0 {
			break // Scan complete
		}
	}

	if recoveredCount > 0 {
		fmt.Printf("[Watchdog] Recovered %d stuck workflows\n", recoveredCount)
	} else {
		fmt.Printf("[Watchdog] No stuck workflows found\n")
	}
}

// loadStateFromKey loads stateData from a Redis key
func (w *Watchdog) loadStateFromKey(ctx context.Context, key string) (*stateData, error) {
	bytes, err := w.redisClient.Get(ctx, key).Bytes()
	if err != nil {
		return nil, fmt.Errorf("failed to get key %s: %w", key, err)
	}

	var state stateData
	if err := json.Unmarshal(bytes, &state); err != nil {
		return nil, fmt.Errorf("failed to unmarshal state: %w", err)
	}

	return &state, nil
}

// isStuck checks if a workflow is stuck based on threshold
func (w *Watchdog) isStuck(state *stateData) bool {
	// Final states are never stuck
	if state.State.IsFinal() {
		return false
	}

	// Check if last activity exceeds threshold
	return time.Since(state.LastActivity) > w.config.StuckThreshold
}

// recoverWorkflow recovers a stuck workflow by executing compensations
func (w *Watchdog) recoverWorkflow(ctx context.Context, state *stateData, redisKey string) error {
	fmt.Printf("[Watchdog] Recovering workflow: correlation_id=%s, state=%s\n",
		state.CorrelationID, state.State)

	// Build compensation stack based on current state
	compensations := w.buildCompensationStackFromState(state)

	// Execute compensations
	var compensationErrors []string
	for i := len(compensations) - 1; i >= 0; i-- {
		comp := compensations[i]
		fmt.Printf("[Watchdog] Executing compensation: %s\n", comp.Name)

		if err := comp.Action(ctx); err != nil {
			errMsg := fmt.Sprintf("%s: %v", comp.Name, err)
			compensationErrors = append(compensationErrors, errMsg)
			fmt.Printf("[Watchdog] Compensation %s failed: %v\n", comp.Name, err)
			// Continue with other compensations
		} else {
			fmt.Printf("[Watchdog] Compensation %s succeeded\n", comp.Name)
		}
	}

	// Delete workflow state from Redis
	if err := w.redisClient.Del(ctx, redisKey).Err(); err != nil {
		fmt.Printf("[Watchdog] Warning: Failed to delete Redis key %s: %v\n", redisKey, err)
	} else {
		fmt.Printf("[Watchdog] Deleted Redis key: %s\n", redisKey)
	}

	// Publish recovery event
	w.publishRecoveryEvent(ctx, state, compensationErrors)

	// Record metrics
	RecordStuckWorkflowRecovered()

	fmt.Printf("[Watchdog] Workflow recovery completed: correlation_id=%s\n", state.CorrelationID)

	return nil
}

// buildCompensationStackFromState builds compensation actions based on workflow state
func (w *Watchdog) buildCompensationStackFromState(state *stateData) []CompensationAction {
	var compensations []CompensationAction

	// Determine which compensations are needed based on state
	// States that require unlock: JobsLocked, SessionsClosed, ExtensionInstalled, Compensating
	switch state.State {
	case StateInit:
		// No compensations needed - nothing was done yet
		return compensations

	case StateJobsLocked, StateSessionsClosed, StateExtensionInstalled, StateCompensating:
		// Need to unlock infobase
		compensations = append(compensations, CompensationAction{
			Name: "unlock_infobase",
			Action: func(ctx context.Context) error {
				return w.unlockInfobase(ctx, state)
			},
		})
	}

	return compensations
}

// unlockInfobase sends unlock command for the infobase
func (w *Watchdog) unlockInfobase(ctx context.Context, state *stateData) error {
	if w.clusterInfo == nil {
		return fmt.Errorf("cluster info provider is required for unlock compensation")
	}

	info, err := w.clusterInfo.Fetch(ctx, state.DatabaseID)
	if err != nil {
		return fmt.Errorf("failed to resolve cluster info: %w", err)
	}
	if info == nil || info.RASServer == "" || info.ClusterID == "" || info.InfobaseID == "" {
		return fmt.Errorf("cluster info is incomplete for database %s", state.DatabaseID)
	}

	client, err := w.rasFactory(info.RASServer)
	if err != nil {
		return fmt.Errorf("failed to create ras client: %w", err)
	}
	defer func() {
		_ = client.Close()
	}()

	if err := client.UnlockScheduledJobs(ctx, info.ClusterID, info.InfobaseID, info.ClusterUser, info.ClusterPwd); err != nil {
		return fmt.Errorf("failed to unlock scheduled jobs: %w", err)
	}

	fmt.Printf("[Watchdog] Unlock completed for infobase: cluster_id=%s, infobase_id=%s\n",
		info.ClusterID, info.InfobaseID)

	return nil
}

// publishRecoveryEvent publishes workflow recovery event to Orchestrator
func (w *Watchdog) publishRecoveryEvent(ctx context.Context, state *stateData, compensationErrors []string) {
	allSucceeded := len(compensationErrors) == 0

	payload := map[string]interface{}{
		"operation_id":         state.OperationID,
		"database_id":          state.DatabaseID,
		"correlation_id":       state.CorrelationID,
		"cluster_id":           state.ClusterID,
		"infobase_id":          state.InfobaseID,
		"recovered_from_state": state.State.String(),
		"last_activity":        state.LastActivity.Format(time.RFC3339),
		"stuck_duration":       time.Since(state.LastActivity).String(),
		"compensations_run":    true,
		"all_succeeded":        allSucceeded,
		"recovered_at":         time.Now().Format(time.RFC3339),
	}

	if !allSucceeded {
		payload["compensation_errors"] = strings.Join(compensationErrors, "; ")
	}

	err := w.publisher.Publish(ctx,
		"events:orchestrator:workflow:recovered",
		"orchestrator.workflow.recovered",
		payload,
		state.CorrelationID,
	)
	if err != nil {
		fmt.Printf("[Watchdog] Failed to publish recovery event: %v\n", err)
	} else {
		fmt.Printf("[Watchdog] Recovery event published for workflow: correlation_id=%s\n",
			state.CorrelationID)
	}
}
