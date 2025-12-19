package workflows

import (
	"fmt"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// Workflow IDs - unique identifiers for each workflow type.
const (
	// WorkflowExtensionInstall installs a .cfe extension to multiple databases.
	WorkflowExtensionInstall = "extension_install"

	// WorkflowExtensionRemove removes an extension from multiple databases.
	WorkflowExtensionRemove = "extension_remove"

	// WorkflowLockScheduledJobs blocks scheduled jobs for databases.
	WorkflowLockScheduledJobs = "lock_scheduled_jobs"

	// WorkflowUnlockScheduledJobs unblocks scheduled jobs for databases.
	WorkflowUnlockScheduledJobs = "unlock_scheduled_jobs"

	// WorkflowTerminateSessions terminates all sessions for databases.
	WorkflowTerminateSessions = "terminate_sessions"

	// WorkflowBlockConnections denies new connections to databases.
	WorkflowBlockConnections = "block_connections"

	// WorkflowUnblockConnections allows new connections to databases.
	WorkflowUnblockConnections = "unblock_connections"

	// WorkflowODataBatch executes OData batch operations.
	WorkflowODataBatch = "odata_batch"

	// WorkflowConfigUpdate updates database configuration (UpdateDBCfg).
	WorkflowConfigUpdate = "config_update"

	// WorkflowConfigLoad loads a new configuration from .cf file.
	WorkflowConfigLoad = "config_load"
)

// WorkflowRegistry manages registration of all workflow definitions.
type WorkflowRegistry struct {
	orchestrator saga.SagaOrchestrator
	rm           resourcemanager.ResourceManager
	deps         *WorkflowDependencies
	logger       *zap.Logger
}

// NewWorkflowRegistry creates a new workflow registry.
func NewWorkflowRegistry(
	orchestrator saga.SagaOrchestrator,
	rm resourcemanager.ResourceManager,
	rasClient RASClient,
	odataClient ODataClient,
	designerClient DesignerClient,
	config *WorkflowConfig,
	logger *zap.Logger,
) (*WorkflowRegistry, error) {
	if config == nil {
		config = DefaultWorkflowConfig()
	}
	if logger == nil {
		logger = zap.NewNop()
	}
	if odataClient == nil {
		return nil, fmt.Errorf("odata client is required for workflow registry")
	}

	return &WorkflowRegistry{
		orchestrator: orchestrator,
		rm:           rm,
		deps: &WorkflowDependencies{
			RASClient:      rasClient,
			DesignerClient: designerClient,
			ODataClient:    odataClient,
			Config:         config,
		},
		logger: logger,
	}, nil
}

// RegisterAll registers all workflow definitions with the orchestrator.
// Returns the first error encountered during registration.
func (r *WorkflowRegistry) RegisterAll() error {
	workflows := []struct {
		name string
		def  *saga.SagaDefinition
	}{
		// Extension workflows
		{WorkflowExtensionInstall, NewExtensionInstallWorkflow(r.rm, r.deps)},
		{WorkflowExtensionRemove, NewExtensionRemoveWorkflow(r.rm, r.deps)},

		// Simple RAS workflows
		{WorkflowLockScheduledJobs, NewLockScheduledJobsWorkflow(r.rm, r.deps)},
		{WorkflowUnlockScheduledJobs, NewUnlockScheduledJobsWorkflow(r.rm, r.deps)},
		{WorkflowTerminateSessions, NewTerminateSessionsWorkflow(r.rm, r.deps)},
		{WorkflowBlockConnections, NewBlockConnectionsWorkflow(r.rm, r.deps)},
		{WorkflowUnblockConnections, NewUnblockConnectionsWorkflow(r.rm, r.deps)},

		// OData workflow
		{WorkflowODataBatch, NewODataBatchWorkflow(r.rm, r.deps)},

		// Config workflows
		{WorkflowConfigUpdate, NewConfigUpdateWorkflow(r.rm, r.deps)},
		{WorkflowConfigLoad, NewConfigLoadWorkflow(r.rm, r.deps)},
	}

	registered := 0
	for _, w := range workflows {
		if err := r.orchestrator.RegisterSaga(w.def); err != nil {
			r.logger.Error("failed to register workflow",
				zap.String("workflow", w.name),
				zap.Error(err),
			)
			return fmt.Errorf("failed to register workflow %s: %w", w.name, err)
		}

		r.logger.Info("workflow registered",
			zap.String("workflow", w.name),
			zap.Int("steps", len(w.def.Steps)),
		)
		registered++
	}

	r.logger.Info("all workflows registered",
		zap.Int("total", registered),
	)

	return nil
}

// RegisterSubset registers only specified workflows.
// Useful for testing or when not all dependencies are available.
func (r *WorkflowRegistry) RegisterSubset(workflowIDs ...string) error {
	workflowMap := map[string]func() *saga.SagaDefinition{
		WorkflowExtensionInstall:    func() *saga.SagaDefinition { return NewExtensionInstallWorkflow(r.rm, r.deps) },
		WorkflowExtensionRemove:     func() *saga.SagaDefinition { return NewExtensionRemoveWorkflow(r.rm, r.deps) },
		WorkflowLockScheduledJobs:   func() *saga.SagaDefinition { return NewLockScheduledJobsWorkflow(r.rm, r.deps) },
		WorkflowUnlockScheduledJobs: func() *saga.SagaDefinition { return NewUnlockScheduledJobsWorkflow(r.rm, r.deps) },
		WorkflowTerminateSessions:   func() *saga.SagaDefinition { return NewTerminateSessionsWorkflow(r.rm, r.deps) },
		WorkflowBlockConnections:    func() *saga.SagaDefinition { return NewBlockConnectionsWorkflow(r.rm, r.deps) },
		WorkflowUnblockConnections:  func() *saga.SagaDefinition { return NewUnblockConnectionsWorkflow(r.rm, r.deps) },
		WorkflowODataBatch:          func() *saga.SagaDefinition { return NewODataBatchWorkflow(r.rm, r.deps) },
		WorkflowConfigUpdate:        func() *saga.SagaDefinition { return NewConfigUpdateWorkflow(r.rm, r.deps) },
		WorkflowConfigLoad:          func() *saga.SagaDefinition { return NewConfigLoadWorkflow(r.rm, r.deps) },
	}

	for _, id := range workflowIDs {
		createFn, ok := workflowMap[id]
		if !ok {
			return fmt.Errorf("unknown workflow ID: %s", id)
		}

		def := createFn()
		if err := r.orchestrator.RegisterSaga(def); err != nil {
			return fmt.Errorf("failed to register workflow %s: %w", id, err)
		}

		r.logger.Info("workflow registered",
			zap.String("workflow", id),
			zap.Int("steps", len(def.Steps)),
		)
	}

	return nil
}

// ListRegisteredWorkflows returns a list of all workflow IDs that can be registered.
func ListRegisteredWorkflows() []string {
	return []string{
		WorkflowExtensionInstall,
		WorkflowExtensionRemove,
		WorkflowLockScheduledJobs,
		WorkflowUnlockScheduledJobs,
		WorkflowTerminateSessions,
		WorkflowBlockConnections,
		WorkflowUnblockConnections,
		WorkflowODataBatch,
		WorkflowConfigUpdate,
		WorkflowConfigLoad,
	}
}

// WorkflowDescription provides metadata about a workflow.
type WorkflowDescription struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Steps       []string `json:"steps"`
	Category    string   `json:"category"`
}

// GetWorkflowDescriptions returns descriptions of all available workflows.
func GetWorkflowDescriptions() []WorkflowDescription {
	return []WorkflowDescription{
		{
			ID:          WorkflowExtensionInstall,
			Name:        "Install Extension",
			Description: "Installs a .cfe extension to one or more 1C databases with proper locking and session management",
			Steps:       []string{"acquire_locks", "lock_scheduled_jobs", "block_connections", "terminate_sessions", "wait_sessions_closed", "install_extension", "unblock_connections", "unlock_scheduled_jobs", "release_locks"},
			Category:    "extensions",
		},
		{
			ID:          WorkflowExtensionRemove,
			Name:        "Remove Extension",
			Description: "Removes an extension from one or more 1C databases",
			Steps:       []string{"acquire_locks", "lock_scheduled_jobs", "block_connections", "terminate_sessions", "wait_sessions_closed", "remove_extension", "unblock_connections", "unlock_scheduled_jobs", "release_locks"},
			Category:    "extensions",
		},
		{
			ID:          WorkflowLockScheduledJobs,
			Name:        "Lock Scheduled Jobs",
			Description: "Blocks scheduled jobs (reglamentnye zadaniya) for databases",
			Steps:       []string{"acquire_locks", "lock_scheduled_jobs", "release_locks"},
			Category:    "ras",
		},
		{
			ID:          WorkflowUnlockScheduledJobs,
			Name:        "Unlock Scheduled Jobs",
			Description: "Unblocks scheduled jobs for databases",
			Steps:       []string{"acquire_locks", "unlock_scheduled_jobs", "release_locks"},
			Category:    "ras",
		},
		{
			ID:          WorkflowTerminateSessions,
			Name:        "Terminate Sessions",
			Description: "Forcefully terminates all active sessions for databases",
			Steps:       []string{"acquire_locks", "terminate_sessions", "release_locks"},
			Category:    "ras",
		},
		{
			ID:          WorkflowBlockConnections,
			Name:        "Block Connections",
			Description: "Denies new connections to databases",
			Steps:       []string{"acquire_locks", "block_connections", "release_locks"},
			Category:    "ras",
		},
		{
			ID:          WorkflowUnblockConnections,
			Name:        "Unblock Connections",
			Description: "Allows new connections to databases",
			Steps:       []string{"acquire_locks", "unblock_connections", "release_locks"},
			Category:    "ras",
		},
		{
			ID:          WorkflowODataBatch,
			Name:        "OData Batch",
			Description: "Executes OData batch operations (create/update/delete) with compensation support",
			Steps:       []string{"acquire_lock", "execute_batch", "release_lock"},
			Category:    "odata",
		},
		{
			ID:          WorkflowConfigUpdate,
			Name:        "Update Database Configuration",
			Description: "Applies configuration changes to database (UpdateDBCfg). Long-running operation up to 4 hours",
			Steps:       []string{"acquire_lock", "lock_scheduled_jobs", "block_connections", "terminate_sessions", "wait_sessions_closed", "backup_config", "update_db_cfg", "unblock_connections", "unlock_scheduled_jobs", "release_lock"},
			Category:    "config",
		},
		{
			ID:          WorkflowConfigLoad,
			Name:        "Load Configuration",
			Description: "Loads a new configuration from .cf file and applies it to database",
			Steps:       []string{"acquire_lock", "lock_scheduled_jobs", "block_connections", "terminate_sessions", "wait_sessions_closed", "backup_config", "load_config", "update_db_cfg", "unblock_connections", "unlock_scheduled_jobs", "release_lock"},
			Category:    "config",
		},
	}
}
