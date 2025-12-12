package workflows

import (
	"context"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// NewLockScheduledJobsWorkflow creates a saga for locking scheduled jobs.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//
// This is a simple workflow with compensation support.
// Compensation will unlock the jobs if the workflow fails.
func NewLockScheduledJobsWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowLockScheduledJobs,
		Name:           "Lock Scheduled Jobs",
		Description:    "Blocks scheduled jobs (reglamentnye zadaniya) for one or more databases",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "lock_scheduled_jobs",
				Name:       "Lock Scheduled Jobs",
				Execute:    lockScheduledJobsStep(deps),
				Compensate: unlockScheduledJobsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     2,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewUnlockScheduledJobsWorkflow creates a saga for unlocking scheduled jobs.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//
// This workflow has no compensation because unlocking is always safe.
func NewUnlockScheduledJobsWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowUnlockScheduledJobs,
		Name:           "Unlock Scheduled Jobs",
		Description:    "Unblocks scheduled jobs for one or more databases",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:      "unlock_scheduled_jobs",
				Name:    "Unlock Scheduled Jobs",
				Execute: unlockScheduledJobsStep(deps),
				// No compensation - unlocking is always safe
				Timeout: deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewTerminateSessionsWorkflow creates a saga for terminating sessions.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//
// This workflow has NO compensation because terminated sessions
// cannot be restored.
func NewTerminateSessionsWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowTerminateSessions,
		Name:           "Terminate Sessions",
		Description:    "Forcefully terminates all active sessions for databases",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:      "terminate_sessions",
				Name:    "Terminate Sessions",
				Execute: terminateSessionsStep(deps),
				// No compensation - sessions cannot be "restored"
				Timeout: deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     2,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewBlockConnectionsWorkflow creates a saga for blocking new connections.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//
// Compensation will unblock connections if the workflow fails.
func NewBlockConnectionsWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowBlockConnections,
		Name:           "Block Connections",
		Description:    "Denies new connections to one or more databases",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "block_connections",
				Name:       "Block Connections",
				Execute:    blockConnectionsStep(deps),
				Compensate: unblockConnectionsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     2,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewUnblockConnectionsWorkflow creates a saga for unblocking connections.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//
// This workflow has no compensation because unblocking is always safe.
func NewUnblockConnectionsWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowUnblockConnections,
		Name:           "Unblock Connections",
		Description:    "Allows new connections to one or more databases",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:      "unblock_connections",
				Name:    "Unblock Connections",
				Execute: unblockConnectionsStep(deps),
				// No compensation - unblocking is always safe
				Timeout: deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewFullPrepareWorkflow creates a composite workflow that locks jobs,
// blocks connections, terminates sessions, and waits for them to close.
// This is useful as a prerequisite for configuration operations.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
func NewFullPrepareWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             "full_prepare",
		Name:           "Full Database Prepare",
		Description:    "Locks jobs, blocks connections, and terminates sessions",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				Idempotent: true,
			},
			{
				ID:         "lock_scheduled_jobs",
				Name:       "Lock Scheduled Jobs",
				Execute:    lockScheduledJobsStep(deps),
				Compensate: unlockScheduledJobsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
			},
			{
				ID:         "block_connections",
				Name:       "Block New Connections",
				Execute:    blockConnectionsStep(deps),
				Compensate: unblockConnectionsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
			},
			{
				ID:      "terminate_sessions",
				Name:    "Terminate Active Sessions",
				Execute: terminateSessionsStep(deps),
				Timeout: deps.Config.DefaultStepTimeout,
			},
			{
				ID:      "wait_sessions_closed",
				Name:    "Wait for Sessions to Close",
				Execute: waitSessionsClosedStep(deps),
				Timeout: deps.Config.SessionWaitTimeout + 30*time.Second,
			},
		},
	}
}

// NewFullRestoreWorkflow creates a composite workflow that unblocks
// connections and unlocks scheduled jobs.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
func NewFullRestoreWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             "full_restore",
		Name:           "Full Database Restore",
		Description:    "Unblocks connections and unlocks scheduled jobs",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_locks",
				Name:       "Acquire Database Locks",
				Execute:    acquireLocksStep(rm, deps),
				Compensate: releaseLocksCompensation(rm, deps),
				Timeout:    2 * time.Minute,
				Idempotent: true,
			},
			{
				ID:         "unblock_connections",
				Name:       "Unblock Connections",
				Execute:    unblockConnectionsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "unlock_scheduled_jobs",
				Name:       "Unlock Scheduled Jobs",
				Execute:    unlockScheduledJobsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "release_locks",
				Name:       "Release Database Locks",
				Execute:    releaseLocksStep(rm, deps),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// Helper step for single database RAS operations
func singleDatabaseRASStep(
	deps *WorkflowDependencies,
	operation string,
) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		databaseID := sagaCtx.GetString("database_id")
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return fmt.Errorf("cluster_id and infobase_id are required")
		}

		var err error
		switch operation {
		case "lock_jobs":
			err = deps.RASClient.LockScheduledJobs(ctx, clusterID, infobaseID)
		case "unlock_jobs":
			err = deps.RASClient.UnlockScheduledJobs(ctx, clusterID, infobaseID)
		case "block_connections":
			err = deps.RASClient.BlockConnections(ctx, clusterID, infobaseID)
		case "unblock_connections":
			err = deps.RASClient.UnblockConnections(ctx, clusterID, infobaseID)
		case "terminate_sessions":
			err = deps.RASClient.TerminateSessions(ctx, clusterID, infobaseID)
		default:
			return fmt.Errorf("unknown operation: %s", operation)
		}

		if err != nil {
			return fmt.Errorf("%s failed for database %s: %w", operation, databaseID, err)
		}

		return nil
	}
}
