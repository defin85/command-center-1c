package rollback

import (
	"fmt"
	"time"

	"github.com/command-center-1c/batch-service/internal/models"
	"go.uber.org/zap"
)

// RollbackManager handles rollback operations
type RollbackManager struct {
	backupManager *BackupManager
	logger        *zap.Logger
}

// NewRollbackManager creates a new RollbackManager instance
func NewRollbackManager(backupManager *BackupManager, logger *zap.Logger) *RollbackManager {
	return &RollbackManager{
		backupManager: backupManager,
		logger:        logger,
	}
}

// Rollback performs a rollback to a specific backup
func (m *RollbackManager) Rollback(req models.RollbackRequest) (*models.RollbackResponse, error) {
	startTime := time.Now()

	m.logger.Info("rollback started",
		zap.String("extension_name", req.ExtensionName),
		zap.String("database_id", req.DatabaseID),
		zap.String("backup_timestamp", req.BackupTimestamp))

	// 1. Find backup to restore
	var backup *models.ExtensionBackup
	var err error

	if req.BackupTimestamp == "" {
		// Use latest backup
		m.logger.Info("no backup timestamp specified, using latest backup")
		backup, err = m.backupManager.GetLatestBackup(req.DatabaseID, req.ExtensionName)
		if err != nil {
			return nil, fmt.Errorf("failed to find latest backup: %w", err)
		}
	} else {
		// Use specific backup by timestamp
		backup, err = m.backupManager.GetBackup(req.DatabaseID, req.ExtensionName, req.BackupTimestamp)
		if err != nil {
			return nil, fmt.Errorf("failed to find backup with timestamp %s: %w", req.BackupTimestamp, err)
		}
	}

	m.logger.Info("found backup to restore",
		zap.String("backup_id", backup.BackupID),
		zap.Time("backup_timestamp", backup.Timestamp),
		zap.String("backup_path", backup.BackupPath))

	// 2. Create pre-rollback backup (safety net)
	// This allows us to undo the rollback if something goes wrong
	m.logger.Info("creating pre-rollback safety backup")
	preRollbackBackup, err := m.backupManager.CreatePreInstallBackup(
		req.DatabaseID, req.Server, req.InfobaseName, req.Username, req.Password, req.ExtensionName,
	)

	if err != nil {
		m.logger.Warn("failed to create pre-rollback backup, continuing anyway",
			zap.Error(err))
		// Continue anyway - the rollback might still succeed
		// The user explicitly requested this rollback
	} else if preRollbackBackup != nil {
		m.logger.Info("pre-rollback backup created",
			zap.String("backup_id", preRollbackBackup.BackupID))
	}

	// 3. Perform restore from selected backup
	m.logger.Info("restoring extension from backup")
	err = m.backupManager.RestoreFromBackup(backup, req.Server, req.InfobaseName, req.Username, req.Password)

	if err != nil {
		// Restore failed - attempt recovery from pre-rollback backup
		m.logger.Error("rollback failed, attempting recovery from pre-rollback backup",
			zap.Error(err))

		if preRollbackBackup != nil {
			m.logger.Info("attempting to restore from pre-rollback backup")
			recoveryErr := m.backupManager.RestoreFromBackup(
				preRollbackBackup, req.Server, req.InfobaseName, req.Username, req.Password,
			)

			if recoveryErr != nil {
				m.logger.Error("recovery from pre-rollback backup also failed",
					zap.Error(recoveryErr))
				return nil, fmt.Errorf("rollback failed: %w, and recovery failed: %v", err, recoveryErr)
			}

			m.logger.Info("successfully recovered from pre-rollback backup")
			return nil, fmt.Errorf("rollback failed but recovered to previous state: %w", err)
		}

		return nil, fmt.Errorf("rollback failed and no pre-rollback backup available: %w", err)
	}

	// 4. Success - clean up pre-rollback backup (no longer needed)
	if preRollbackBackup != nil {
		m.logger.Info("cleaning up pre-rollback backup")
		if err := m.backupManager.DeleteBackup(req.DatabaseID, preRollbackBackup.BackupID); err != nil {
			m.logger.Warn("failed to delete pre-rollback backup (non-critical)",
				zap.String("backup_id", preRollbackBackup.BackupID),
				zap.Error(err))
		}
	}

	duration := time.Since(startTime).Seconds()

	m.logger.Info("rollback completed successfully",
		zap.Float64("duration_seconds", duration))

	return &models.RollbackResponse{
		Success:      true,
		Message:      fmt.Sprintf("Extension '%s' successfully rolled back to backup from %s", req.ExtensionName, backup.Timestamp.Format("2006-01-02 15:04:05")),
		BackupUsed:   backup.BackupPath,
		RolledBackAt: time.Now(),
		Duration:     duration,
	}, nil
}

// ValidateRollbackRequest validates a rollback request
func (m *RollbackManager) ValidateRollbackRequest(req models.RollbackRequest) error {
	// Check if backup exists
	if req.BackupTimestamp != "" {
		_, err := m.backupManager.GetBackup(req.DatabaseID, req.ExtensionName, req.BackupTimestamp)
		if err != nil {
			return fmt.Errorf("backup not found: %w", err)
		}
	} else {
		// Check if there are any backups at all
		_, err := m.backupManager.GetLatestBackup(req.DatabaseID, req.ExtensionName)
		if err != nil {
			return fmt.Errorf("no backups available: %w", err)
		}
	}

	return nil
}

// GetRollbackHistory returns list of available backups for rollback
func (m *RollbackManager) GetRollbackHistory(databaseID, extensionName string) ([]models.ExtensionBackup, error) {
	return m.backupManager.ListBackups(databaseID, extensionName)
}
