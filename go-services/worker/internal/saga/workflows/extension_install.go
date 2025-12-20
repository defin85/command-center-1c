package workflows

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// Extension workflow errors.
var (
	ErrMissingExtensionFile = errors.New("extension_file is required")
	ErrMissingExtensionName = errors.New("extension_name is required")
	ErrMissingDatabaseIDs   = errors.New("database_ids is required")
	ErrMissingClusterID     = errors.New("cluster_id is required")
	ErrMissingSSHHost       = errors.New("ssh_host is required")
	ErrSessionsNotClosed    = errors.New("sessions did not close in time")
)

// ExtensionInstallInput defines input parameters for extension install workflow.
// These should be passed via saga input variables.
type ExtensionInstallInput struct {
	// DatabaseIDs is the list of database IDs to install the extension to.
	DatabaseIDs []string `json:"database_ids"`

	// ClusterID is the 1C RAS cluster UUID.
	ClusterID string `json:"cluster_id"`

	// InfobaseIDs is the map of database_id -> infobase_id.
	InfobaseIDs map[string]string `json:"infobase_ids"`

	// ExtensionFile is the path to the .cfe extension file.
	ExtensionFile string `json:"extension_file"`

	// ExtensionName is the name of the extension.
	ExtensionName string `json:"extension_name"`

	// SSHHost is the hostname for SSH connection.
	SSHHost string `json:"ssh_host"`

	// SSHCredentials contains SSH connection parameters.
	SSHCredentials SSHCredentials `json:"ssh_credentials"`

	// InfobasePaths is the map of database_id -> infobase_path.
	InfobasePaths map[string]string `json:"infobase_paths"`
}

// NewExtensionInstallWorkflow creates a saga for installing an extension.
//
// Input variables:
//   - database_ids: []string - list of database IDs
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_ids: map[string]string - database_id -> infobase_id mapping
//   - extension_file: string - path to .cfe file
//   - extension_name: string - name of the extension
//   - ssh_host: string - SSH host for remote Designer access (optional)
//   - ssh_credentials: map[string]string - SSH credentials (username, password, key_file)
//   - infobase_paths: map[string]string - database_id -> infobase_path mapping
//
// Steps:
// 1. acquire_locks - acquire distributed locks on all databases
// 2. lock_scheduled_jobs - block scheduled jobs via RAS
// 3. block_connections - deny new connections via RAS
// 4. terminate_sessions - terminate active sessions via RAS
// 5. wait_sessions_closed - wait for all sessions to close
// 6. install_extension - install extension via Designer CLI
// 7. unblock_connections - allow connections via RAS
// 8. unlock_scheduled_jobs - unblock scheduled jobs via RAS
// 9. release_locks - release distributed locks
func NewExtensionInstallWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowExtensionInstall,
		Name:           "Extension Install",
		Description:    "Installs a .cfe extension to one or more 1C databases with proper locking and session management",
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
				ID:         "block_connections",
				Name:       "Block New Connections",
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
				ID:      "terminate_sessions",
				Name:    "Terminate Active Sessions",
				Execute: terminateSessionsStep(deps),
				// No compensation - sessions can't be "restored"
				Timeout: deps.Config.DefaultStepTimeout,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     2,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
			},
			{
				ID:      "wait_sessions_closed",
				Name:    "Wait for Sessions to Close",
				Execute: waitSessionsClosedStep(deps),
				// No compensation - just a wait operation
				Timeout:    deps.Config.SessionWaitTimeout + 30*time.Second,
				Idempotent: true,
			},
			{
				ID:         "install_extension",
				Name:       "Install Extension",
				Execute:    installExtensionStep(deps),
				Compensate: removeExtensionCompensation(deps),
				Timeout:    10 * time.Minute, // Extension install can take time
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     1,
					InitialBackoff: 5 * time.Second,
					MaxBackoff:     30 * time.Second,
					BackoffFactor:  2.0,
				},
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
				ID:      "release_locks",
				Name:    "Release Database Locks",
				Execute: releaseLocksStep(rm, deps),
				// No compensation - releasing is always safe
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewExtensionRemoveWorkflow creates a saga for removing an extension.
// Similar to install but removes the extension instead.
func NewExtensionRemoveWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowExtensionRemove,
		Name:           "Extension Remove",
		Description:    "Removes an extension from one or more 1C databases",
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
			{
				ID:   "remove_extension",
				Name: "Remove Extension",
				Execute: func(ctx context.Context, sagaCtx *saga.SagaContext) error {
					return removeExtensionStep(deps)(ctx, sagaCtx)
				},
				// No easy compensation for remove - would need to reinstall
				Timeout: 10 * time.Minute,
			},
			{
				ID:      "unblock_connections",
				Name:    "Unblock Connections",
				Execute: unblockConnectionsStep(deps),
				Timeout: deps.Config.DefaultStepTimeout,
			},
			{
				ID:      "unlock_scheduled_jobs",
				Name:    "Unlock Scheduled Jobs",
				Execute: unlockScheduledJobsStep(deps),
				Timeout: deps.Config.DefaultStepTimeout,
			},
			{
				ID:      "release_locks",
				Name:    "Release Database Locks",
				Execute: releaseLocksStep(rm, deps),
				Timeout: 1 * time.Minute,
			},
		},
	}
}

// Step implementations

func acquireLocksStep(rm resourcemanager.ResourceManager, deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		databaseIDs := sagaCtx.GetStringSlice("database_ids")
		if len(databaseIDs) == 0 {
			return ErrMissingDatabaseIDs
		}

		acquiredLocks := make([]string, 0, len(databaseIDs))

		for _, dbID := range databaseIDs {
			req := &resourcemanager.LockRequest{
				DatabaseID:    dbID,
				OwnerID:       sagaCtx.ExecutionID,
				Operation:     sagaCtx.SagaID,
				CorrelationID: sagaCtx.CorrelationID,
				TTL:           deps.Config.LockTTL,
				WaitTimeout:   2 * time.Minute,
			}

			result, err := rm.AcquireLock(ctx, req)
			if err != nil {
				// Release already acquired locks on failure
				for _, lockID := range acquiredLocks {
					rm.ReleaseLock(ctx, lockID, sagaCtx.ExecutionID)
				}
				return fmt.Errorf("failed to acquire lock for database %s: %w", dbID, err)
			}

			if !result.Acquired {
				// Release already acquired locks on failure
				for _, lockID := range acquiredLocks {
					rm.ReleaseLock(ctx, lockID, sagaCtx.ExecutionID)
				}
				return fmt.Errorf("could not acquire lock for database %s: lock held by %s",
					dbID, result.LockInfo.OwnerID)
			}

			acquiredLocks = append(acquiredLocks, dbID)
		}

		// Store acquired locks in context for compensation
		sagaCtx.Set("acquired_locks", acquiredLocks)
		sagaCtx.DatabaseIDs = acquiredLocks

		return nil
	}
}

func releaseLocksCompensation(rm resourcemanager.ResourceManager, _ *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		acquiredLocks := sagaCtx.GetStringSlice("acquired_locks")
		if len(acquiredLocks) == 0 {
			return nil
		}

		var lastErr error
		for _, dbID := range acquiredLocks {
			if err := rm.ReleaseLock(ctx, dbID, sagaCtx.ExecutionID); err != nil {
				lastErr = err
				// Continue releasing other locks even if one fails
			}
		}

		return lastErr
	}
}

func releaseLocksStep(rm resourcemanager.ResourceManager, _ *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		acquiredLocks := sagaCtx.GetStringSlice("acquired_locks")
		if len(acquiredLocks) == 0 {
			databaseIDs := sagaCtx.GetStringSlice("database_ids")
			acquiredLocks = databaseIDs
		}

		var lastErr error
		for _, dbID := range acquiredLocks {
			if err := rm.ReleaseLock(ctx, dbID, sagaCtx.ExecutionID); err != nil {
				lastErr = err
				// Continue releasing other locks
			}
		}

		// Clear acquired locks from context
		sagaCtx.Set("acquired_locks", []string{})

		return lastErr
	}
}

func lockScheduledJobsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		if clusterID == "" {
			return ErrMissingClusterID
		}

		infobaseIDsRaw, ok := sagaCtx.Get("infobase_ids")
		if !ok {
			return fmt.Errorf("infobase_ids is required")
		}

		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")
		lockedDBs := make([]string, 0, len(databaseIDs))

		for _, dbID := range databaseIDs {
			infobaseID, ok := infobaseIDs[dbID]
			if !ok {
				continue
			}

			if err := deps.RASClient.LockScheduledJobs(ctx, clusterID, infobaseID); err != nil {
				// Unlock already locked DBs on failure
				for _, lockedDB := range lockedDBs {
					if iid, ok := infobaseIDs[lockedDB]; ok {
						deps.RASClient.UnlockScheduledJobs(ctx, clusterID, iid)
					}
				}
				return fmt.Errorf("failed to lock scheduled jobs for %s: %w", dbID, err)
			}

			lockedDBs = append(lockedDBs, dbID)
		}

		sagaCtx.Set("jobs_locked_dbs", lockedDBs)
		return nil
	}
}

func unlockScheduledJobsCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		lockedDBs := sagaCtx.GetStringSlice("jobs_locked_dbs")

		var lastErr error
		for _, dbID := range lockedDBs {
			if infobaseID, ok := infobaseIDs[dbID]; ok {
				if err := deps.RASClient.UnlockScheduledJobs(ctx, clusterID, infobaseID); err != nil {
					lastErr = err
				}
			}
		}

		return lastErr
	}
}

func unlockScheduledJobsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		var lastErr error
		for _, dbID := range databaseIDs {
			if infobaseID, ok := infobaseIDs[dbID]; ok {
				if err := deps.RASClient.UnlockScheduledJobs(ctx, clusterID, infobaseID); err != nil {
					lastErr = err
				}
			}
		}

		sagaCtx.Set("jobs_locked_dbs", []string{})
		return lastErr
	}
}

func blockConnectionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		blockedDBs := make([]string, 0, len(databaseIDs))

		for _, dbID := range databaseIDs {
			infobaseID, ok := infobaseIDs[dbID]
			if !ok {
				continue
			}

			if err := deps.RASClient.BlockConnections(ctx, clusterID, infobaseID); err != nil {
				// Unblock already blocked DBs on failure
				for _, blockedDB := range blockedDBs {
					if iid, ok := infobaseIDs[blockedDB]; ok {
						deps.RASClient.UnblockConnections(ctx, clusterID, iid)
					}
				}
				return fmt.Errorf("failed to block connections for %s: %w", dbID, err)
			}

			blockedDBs = append(blockedDBs, dbID)
		}

		sagaCtx.Set("connections_blocked_dbs", blockedDBs)
		return nil
	}
}

func unblockConnectionsCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		blockedDBs := sagaCtx.GetStringSlice("connections_blocked_dbs")

		var lastErr error
		for _, dbID := range blockedDBs {
			if infobaseID, ok := infobaseIDs[dbID]; ok {
				if err := deps.RASClient.UnblockConnections(ctx, clusterID, infobaseID); err != nil {
					lastErr = err
				}
			}
		}

		return lastErr
	}
}

func unblockConnectionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		var lastErr error
		for _, dbID := range databaseIDs {
			if infobaseID, ok := infobaseIDs[dbID]; ok {
				if err := deps.RASClient.UnblockConnections(ctx, clusterID, infobaseID); err != nil {
					lastErr = err
				}
			}
		}

		sagaCtx.Set("connections_blocked_dbs", []string{})
		return lastErr
	}
}

func terminateSessionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		var lastErr error
		for _, dbID := range databaseIDs {
			if infobaseID, ok := infobaseIDs[dbID]; ok {
				if err := deps.RASClient.TerminateSessions(ctx, clusterID, infobaseID); err != nil {
					lastErr = err
					// Continue terminating other DBs even on failure
				}
			}
		}

		return lastErr
	}
}

func waitSessionsClosedStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseIDsRaw, _ := sagaCtx.Get("infobase_ids")
		infobaseIDs := parseStringMap(infobaseIDsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		timeout := deps.Config.SessionWaitTimeout
		checkInterval := deps.Config.SessionCheckInterval
		deadline := time.Now().Add(timeout)

		for {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			allClosed := true
			for _, dbID := range databaseIDs {
				infobaseID, ok := infobaseIDs[dbID]
				if !ok {
					continue
				}

				count, err := deps.RASClient.GetSessionCount(ctx, clusterID, infobaseID)
				if err != nil {
					// Ignore errors during wait, just try again
					allClosed = false
					continue
				}

				if count > 0 {
					allClosed = false
					break
				}
			}

			if allClosed {
				return nil
			}

			if time.Now().After(deadline) {
				return ErrSessionsNotClosed
			}

			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(checkInterval):
			}
		}
	}
}

func installExtensionStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		extensionFile := sagaCtx.GetString("extension_file")
		if extensionFile == "" {
			return ErrMissingExtensionFile
		}

		extensionName := sagaCtx.GetString("extension_name")
		if extensionName == "" {
			return ErrMissingExtensionName
		}

		sshHost := sagaCtx.GetString("ssh_host")
		if sshHost == "" {
			return ErrMissingSSHHost
		}

		sshCreds := getSSHCredentials(sagaCtx)
		infobasePathsRaw, _ := sagaCtx.Get("infobase_paths")
		infobasePaths := parseStringMap(infobasePathsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		installedDBs := make([]string, 0, len(databaseIDs))

		for _, dbID := range databaseIDs {
			dbPath, ok := infobasePaths[dbID]
			if !ok {
				continue
			}

			if err := deps.DesignerClient.InstallExtension(ctx, sshCreds, dbPath, extensionFile, extensionName); err != nil {
				// Store which DBs got the extension for compensation
				sagaCtx.Set("extension_installed_dbs", installedDBs)
				return fmt.Errorf("failed to install extension to %s: %w", dbID, err)
			}

			installedDBs = append(installedDBs, dbID)
		}

		sagaCtx.Set("extension_installed_dbs", installedDBs)
		return nil
	}
}

func removeExtensionCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		extensionName := sagaCtx.GetString("extension_name")
		if extensionName == "" {
			return nil // Nothing to remove
		}

		sshCreds := getSSHCredentials(sagaCtx)
		infobasePathsRaw, _ := sagaCtx.Get("infobase_paths")
		infobasePaths := parseStringMap(infobasePathsRaw)
		installedDBs := sagaCtx.GetStringSlice("extension_installed_dbs")

		var lastErr error
		for _, dbID := range installedDBs {
			if dbPath, ok := infobasePaths[dbID]; ok {
				if err := deps.DesignerClient.RemoveExtension(ctx, sshCreds, dbPath, extensionName); err != nil {
					lastErr = err
				}
			}
		}

		return lastErr
	}
}

func removeExtensionStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		extensionName := sagaCtx.GetString("extension_name")
		if extensionName == "" {
			return ErrMissingExtensionName
		}

		sshCreds := getSSHCredentials(sagaCtx)
		infobasePathsRaw, _ := sagaCtx.Get("infobase_paths")
		infobasePaths := parseStringMap(infobasePathsRaw)
		databaseIDs := sagaCtx.GetStringSlice("database_ids")

		var lastErr error
		for _, dbID := range databaseIDs {
			if dbPath, ok := infobasePaths[dbID]; ok {
				if err := deps.DesignerClient.RemoveExtension(ctx, sshCreds, dbPath, extensionName); err != nil {
					lastErr = err
				}
			}
		}

		return lastErr
	}
}

// Helper functions

func getSSHCredentials(sagaCtx *saga.SagaContext) SSHCredentials {
	sshCredsRaw, _ := sagaCtx.Get("ssh_credentials")
	creds := SSHCredentials{
		Host: sagaCtx.GetString("ssh_host"),
		Port: 22,
	}

	if sshMap, ok := sshCredsRaw.(map[string]interface{}); ok {
		if username, ok := sshMap["username"].(string); ok {
			creds.Username = username
		}
		if password, ok := sshMap["password"].(string); ok {
			creds.Password = password
		}
		if keyFile, ok := sshMap["key_file"].(string); ok {
			creds.KeyFile = keyFile
		}
		if port, ok := sshMap["port"].(float64); ok {
			creds.Port = int(port)
		}
	}

	return creds
}

func parseStringMap(raw interface{}) map[string]string {
	result := make(map[string]string)

	switch v := raw.(type) {
	case map[string]string:
		return v
	case map[string]interface{}:
		for k, val := range v {
			if str, ok := val.(string); ok {
				result[k] = str
			}
		}
	case string:
		// Try to parse as JSON
		var m map[string]string
		if err := json.Unmarshal([]byte(v), &m); err == nil {
			return m
		}
	}

	return result
}
