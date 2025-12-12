package workflows

import (
	"context"
	"errors"
	"fmt"
	"path/filepath"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// Config update workflow errors.
var (
	ErrMissingInfobasePath   = errors.New("infobase_path is required")
	ErrBackupFailed          = errors.New("configuration backup failed")
	ErrConfigUpdateFailed    = errors.New("configuration update failed")
	ErrConfigLoadFailed      = errors.New("configuration load failed")
	ErrRestoreFromBackupFail = errors.New("failed to restore from backup")
)

// ConfigUpdateInput defines input parameters for config update workflow.
type ConfigUpdateInput struct {
	// DatabaseID is the internal CommandCenter database ID.
	DatabaseID string `json:"database_id"`

	// ClusterID is the 1C RAS cluster UUID.
	ClusterID string `json:"cluster_id"`

	// InfobaseID is the 1C RAS infobase UUID.
	InfobaseID string `json:"infobase_id"`

	// SSHHost is the hostname for SSH connection.
	SSHHost string `json:"ssh_host"`

	// SSHCredentials contains SSH connection parameters.
	SSHCredentials SSHCredentials `json:"ssh_credentials"`

	// InfobasePath is the path to the infobase on the 1C server.
	InfobasePath string `json:"infobase_path"`

	// ConfigFile is the path to .cf configuration file (optional).
	// If provided, this configuration will be loaded before UpdateDBCfg.
	ConfigFile string `json:"config_file,omitempty"`

	// BackupDir is the directory for configuration backup.
	// Default: /tmp/cc1c_backups
	BackupDir string `json:"backup_dir,omitempty"`

	// SkipBackup skips configuration backup (not recommended).
	SkipBackup bool `json:"skip_backup,omitempty"`
}

// NewConfigUpdateWorkflow creates a saga for updating database configuration.
//
// Input variables:
//   - database_id: string - internal database ID
//   - cluster_id: string - 1C RAS cluster UUID
//   - infobase_id: string - 1C RAS infobase UUID
//   - ssh_host: string - SSH host for designer-agent
//   - ssh_credentials: map - SSH credentials
//   - infobase_path: string - path to the infobase
//   - config_file: string - (optional) path to .cf file to load
//   - backup_dir: string - (optional) backup directory
//   - skip_backup: bool - (optional) skip backup
//
// Steps:
// 1. acquire_lock - acquire distributed lock (TTL = 4 hours!)
// 2. lock_scheduled_jobs - block scheduled jobs via RAS
// 3. block_connections - deny new connections via RAS
// 4. terminate_sessions - terminate active sessions via RAS
// 5. wait_sessions_closed - wait for all sessions to close
// 6. backup_config - dump current configuration for compensation
// 7. load_config - (optional) load new configuration from .cf file
// 8. update_db_cfg - apply configuration changes (UpdateDBCfg)
// 9. unblock_connections - allow connections via RAS
// 10. unlock_scheduled_jobs - unblock scheduled jobs via RAS
// 11. release_lock - release distributed lock
//
// Compensation for update_db_cfg:
//   - Load backup configuration
//   - Apply UpdateDBCfg again
func NewConfigUpdateWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	longTimeout := deps.Config.LongOperationLockTTL // 4 hours

	return &saga.SagaDefinition{
		ID:             WorkflowConfigUpdate,
		Name:           "Configuration Update",
		Description:    "Applies configuration changes to database (UpdateDBCfg). Long-running operation up to 4 hours.",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_lock",
				Name:       "Acquire Database Lock",
				Execute:    acquireLongOperationLockStep(rm, deps),
				Compensate: releaseSingleLockCompensation(rm),
				Timeout:    5 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 1 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "lock_scheduled_jobs",
				Name:       "Lock Scheduled Jobs",
				Execute:    lockSingleDBScheduledJobsStep(deps),
				Compensate: unlockSingleDBScheduledJobsCompensation(deps),
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
				Execute:    blockSingleDBConnectionsStep(deps),
				Compensate: unblockSingleDBConnectionsCompensation(deps),
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
				Execute: terminateSingleDBSessionsStep(deps),
				Timeout: deps.Config.DefaultStepTimeout,
			},
			{
				ID:         "wait_sessions_closed",
				Name:       "Wait for Sessions to Close",
				Execute:    waitSingleDBSessionsClosedStep(deps),
				Timeout:    deps.Config.SessionWaitTimeout + 30*time.Second,
				Idempotent: true,
			},
			{
				ID:         "backup_config",
				Name:       "Backup Current Configuration",
				Execute:    backupConfigStep(deps),
				Timeout:    30 * time.Minute, // Backup can take time
				Idempotent: true,
			},
			{
				ID:         "update_db_cfg",
				Name:       "Update Database Configuration",
				Execute:    updateDBCfgStep(deps),
				Compensate: restoreConfigCompensation(deps),
				Timeout:    longTimeout, // Up to 4 hours
			},
			{
				ID:         "unblock_connections",
				Name:       "Unblock Connections",
				Execute:    unblockSingleDBConnectionsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "unlock_scheduled_jobs",
				Name:       "Unlock Scheduled Jobs",
				Execute:    unlockSingleDBScheduledJobsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "release_lock",
				Name:       "Release Database Lock",
				Execute:    releaseSingleLockStep(rm),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// NewConfigLoadWorkflow creates a saga for loading a new configuration from .cf file.
// Similar to ConfigUpdate but includes explicit config load step.
func NewConfigLoadWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	longTimeout := deps.Config.LongOperationLockTTL // 4 hours

	return &saga.SagaDefinition{
		ID:             WorkflowConfigLoad,
		Name:           "Configuration Load",
		Description:    "Loads a new configuration from .cf file and applies it to database",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_lock",
				Name:       "Acquire Database Lock",
				Execute:    acquireLongOperationLockStep(rm, deps),
				Compensate: releaseSingleLockCompensation(rm),
				Timeout:    5 * time.Minute,
				Idempotent: true,
			},
			{
				ID:         "lock_scheduled_jobs",
				Name:       "Lock Scheduled Jobs",
				Execute:    lockSingleDBScheduledJobsStep(deps),
				Compensate: unlockSingleDBScheduledJobsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
			},
			{
				ID:         "block_connections",
				Name:       "Block New Connections",
				Execute:    blockSingleDBConnectionsStep(deps),
				Compensate: unblockSingleDBConnectionsCompensation(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
			},
			{
				ID:      "terminate_sessions",
				Name:    "Terminate Active Sessions",
				Execute: terminateSingleDBSessionsStep(deps),
				Timeout: deps.Config.DefaultStepTimeout,
			},
			{
				ID:         "wait_sessions_closed",
				Name:       "Wait for Sessions to Close",
				Execute:    waitSingleDBSessionsClosedStep(deps),
				Timeout:    deps.Config.SessionWaitTimeout + 30*time.Second,
				Idempotent: true,
			},
			{
				ID:         "backup_config",
				Name:       "Backup Current Configuration",
				Execute:    backupConfigStep(deps),
				Timeout:    30 * time.Minute,
				Idempotent: true,
			},
			{
				ID:         "load_config",
				Name:       "Load New Configuration",
				Execute:    loadConfigStep(deps),
				Compensate: restoreConfigCompensation(deps),
				Timeout:    longTimeout, // Config load can take hours
			},
			{
				ID:         "update_db_cfg",
				Name:       "Update Database Configuration",
				Execute:    updateDBCfgStep(deps),
				Compensate: restoreConfigCompensation(deps),
				Timeout:    longTimeout,
			},
			{
				ID:         "unblock_connections",
				Name:       "Unblock Connections",
				Execute:    unblockSingleDBConnectionsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "unlock_scheduled_jobs",
				Name:       "Unlock Scheduled Jobs",
				Execute:    unlockSingleDBScheduledJobsStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "release_lock",
				Name:       "Release Database Lock",
				Execute:    releaseSingleLockStep(rm),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// Step implementations for config workflows

func acquireLongOperationLockStep(rm resourcemanager.ResourceManager, deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		databaseID := sagaCtx.GetString("database_id")
		if databaseID == "" {
			return ErrMissingDatabaseID
		}

		req := &resourcemanager.LockRequest{
			DatabaseID:    databaseID,
			OwnerID:       sagaCtx.ExecutionID,
			Operation:     sagaCtx.SagaID,
			CorrelationID: sagaCtx.CorrelationID,
			TTL:           deps.Config.LongOperationLockTTL, // 4 hours
			WaitTimeout:   5 * time.Minute,
		}

		result, err := rm.AcquireLock(ctx, req)
		if err != nil {
			return fmt.Errorf("failed to acquire lock for database %s: %w", databaseID, err)
		}

		if !result.Acquired {
			return fmt.Errorf("could not acquire lock for database %s: lock held by %s",
				databaseID, result.LockInfo.OwnerID)
		}

		sagaCtx.Set("lock_acquired", true)
		sagaCtx.DatabaseIDs = []string{databaseID}

		// Start heartbeat goroutine for long operation
		// (This should be managed by the caller in production)
		sagaCtx.Set("lock_ttl", deps.Config.LongOperationLockTTL)

		return nil
	}
}

func lockSingleDBScheduledJobsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return fmt.Errorf("cluster_id and infobase_id are required")
		}

		if err := deps.RASClient.LockScheduledJobs(ctx, clusterID, infobaseID); err != nil {
			return fmt.Errorf("failed to lock scheduled jobs: %w", err)
		}

		sagaCtx.Set("jobs_locked", true)
		return nil
	}
}

func unlockSingleDBScheduledJobsCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		if !sagaCtx.GetBool("jobs_locked") {
			return nil
		}

		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		return deps.RASClient.UnlockScheduledJobs(ctx, clusterID, infobaseID)
	}
}

func unlockSingleDBScheduledJobsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return nil
		}

		err := deps.RASClient.UnlockScheduledJobs(ctx, clusterID, infobaseID)
		sagaCtx.Set("jobs_locked", false)
		return err
	}
}

func blockSingleDBConnectionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return fmt.Errorf("cluster_id and infobase_id are required")
		}

		if err := deps.RASClient.BlockConnections(ctx, clusterID, infobaseID); err != nil {
			return fmt.Errorf("failed to block connections: %w", err)
		}

		sagaCtx.Set("connections_blocked", true)
		return nil
	}
}

func unblockSingleDBConnectionsCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		if !sagaCtx.GetBool("connections_blocked") {
			return nil
		}

		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		return deps.RASClient.UnblockConnections(ctx, clusterID, infobaseID)
	}
}

func unblockSingleDBConnectionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return nil
		}

		err := deps.RASClient.UnblockConnections(ctx, clusterID, infobaseID)
		sagaCtx.Set("connections_blocked", false)
		return err
	}
}

func terminateSingleDBSessionsStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return fmt.Errorf("cluster_id and infobase_id are required")
		}

		return deps.RASClient.TerminateSessions(ctx, clusterID, infobaseID)
	}
}

func waitSingleDBSessionsClosedStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		clusterID := sagaCtx.GetString("cluster_id")
		infobaseID := sagaCtx.GetString("infobase_id")

		if clusterID == "" || infobaseID == "" {
			return fmt.Errorf("cluster_id and infobase_id are required")
		}

		timeout := deps.Config.SessionWaitTimeout
		checkInterval := deps.Config.SessionCheckInterval
		deadline := time.Now().Add(timeout)

		for {
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			count, err := deps.RASClient.GetSessionCount(ctx, clusterID, infobaseID)
			if err == nil && count == 0 {
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

func backupConfigStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		skipBackup := sagaCtx.GetBool("skip_backup")
		if skipBackup {
			return nil
		}

		infobasePath := sagaCtx.GetString("infobase_path")
		if infobasePath == "" {
			return ErrMissingInfobasePath
		}

		sshCreds := getSSHCredentials(sagaCtx)
		if sshCreds.Host == "" {
			sshCreds.Host = sagaCtx.GetString("ssh_host")
		}

		// Generate backup path
		backupDir := sagaCtx.GetString("backup_dir")
		if backupDir == "" {
			backupDir = "/tmp/cc1c_backups"
		}

		databaseID := sagaCtx.GetString("database_id")
		timestamp := time.Now().Format("20060102_150405")
		backupPath := filepath.Join(backupDir, fmt.Sprintf("%s_%s.cf", databaseID, timestamp))

		// Dump current configuration
		if err := deps.DesignerClient.DumpConfig(ctx, sshCreds, infobasePath, backupPath); err != nil {
			return fmt.Errorf("%w: %v", ErrBackupFailed, err)
		}

		sagaCtx.Set("backup_path", backupPath)
		return nil
	}
}

func loadConfigStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		configFile := sagaCtx.GetString("config_file")
		if configFile == "" {
			// No config file specified, skip this step
			return nil
		}

		infobasePath := sagaCtx.GetString("infobase_path")
		if infobasePath == "" {
			return ErrMissingInfobasePath
		}

		sshCreds := getSSHCredentials(sagaCtx)
		if sshCreds.Host == "" {
			sshCreds.Host = sagaCtx.GetString("ssh_host")
		}

		if err := deps.DesignerClient.LoadConfig(ctx, sshCreds, infobasePath, configFile); err != nil {
			return fmt.Errorf("%w: %v", ErrConfigLoadFailed, err)
		}

		sagaCtx.Set("config_loaded", true)
		return nil
	}
}

func updateDBCfgStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		infobasePath := sagaCtx.GetString("infobase_path")
		if infobasePath == "" {
			return ErrMissingInfobasePath
		}

		sshCreds := getSSHCredentials(sagaCtx)
		if sshCreds.Host == "" {
			sshCreds.Host = sagaCtx.GetString("ssh_host")
		}

		if err := deps.DesignerClient.UpdateDBCfg(ctx, sshCreds, infobasePath); err != nil {
			return fmt.Errorf("%w: %v", ErrConfigUpdateFailed, err)
		}

		sagaCtx.Set("db_cfg_updated", true)
		return nil
	}
}

func restoreConfigCompensation(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		backupPath := sagaCtx.GetString("backup_path")
		if backupPath == "" {
			// No backup available, cannot compensate
			sagaCtx.Set("compensation_warning", "No backup available, cannot restore configuration")
			return nil
		}

		infobasePath := sagaCtx.GetString("infobase_path")
		if infobasePath == "" {
			return ErrMissingInfobasePath
		}

		sshCreds := getSSHCredentials(sagaCtx)
		if sshCreds.Host == "" {
			sshCreds.Host = sagaCtx.GetString("ssh_host")
		}

		// Load backup configuration
		if err := deps.DesignerClient.LoadConfig(ctx, sshCreds, infobasePath, backupPath); err != nil {
			return fmt.Errorf("%w: %v", ErrRestoreFromBackupFail, err)
		}

		// Apply restored configuration
		if err := deps.DesignerClient.UpdateDBCfg(ctx, sshCreds, infobasePath); err != nil {
			return fmt.Errorf("failed to apply restored configuration: %w", err)
		}

		return nil
	}
}
