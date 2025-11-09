package rollback

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/command-center-1c/batch-service/internal/infrastructure/filesystem"
	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/google/uuid"
	"go.uber.org/zap"
)

// BackupManager handles backup creation and restoration operations
type BackupManager struct {
	v8executor    *v8executor.V8Executor
	backupStorage *filesystem.BackupStorage
	logger        *zap.Logger
}

// NewBackupManager creates a new BackupManager instance
func NewBackupManager(
	v8executor *v8executor.V8Executor,
	backupStorage *filesystem.BackupStorage,
	logger *zap.Logger,
) *BackupManager {
	return &BackupManager{
		v8executor:    v8executor,
		backupStorage: backupStorage,
		logger:        logger,
	}
}

// CreatePreInstallBackup creates a backup of the current extension before installation
// Returns nil if extension doesn't exist (first installation)
func (m *BackupManager) CreatePreInstallBackup(
	databaseID, server, infobaseName, username, password, extensionName string,
) (*models.ExtensionBackup, error) {
	m.logger.Info("creating pre-install backup",
		zap.String("extension_name", extensionName),
		zap.String("database_id", databaseID))

	// 1. Create temporary file for dump
	timestamp := time.Now().Format("2006-01-02_15-04-05")
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("%s_%s.cfe", extensionName, timestamp))
	defer os.Remove(tmpFile) // cleanup temp file after we're done

	// 2. Dump current extension from database
	dbPath := fmt.Sprintf("%s\\%s", server, infobaseName)
	err := m.v8executor.DumpExtension(dbPath, username, password, extensionName, tmpFile)
	if err != nil {
		// Extension might not exist - this is OK for first installation
		m.logger.Info("extension does not exist, skipping backup (first installation)",
			zap.String("extension_name", extensionName),
			zap.Error(err))
		return nil, nil
	}

	// 3. Get file size
	fileInfo, err := os.Stat(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to stat backup file: %w", err)
	}

	// 4. Create backup record
	backup := &models.ExtensionBackup{
		BackupID:      uuid.New().String(),
		DatabaseID:    databaseID,
		ExtensionName: extensionName,
		Timestamp:     time.Now(),
		Reason:        "pre_install",
		SizeBytes:     fileInfo.Size(),
	}

	// 5. Save backup file to storage
	file, err := os.Open(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to open temp backup file: %w", err)
	}
	defer file.Close()

	err = m.backupStorage.SaveBackup(databaseID, backup, file)
	if err != nil {
		return nil, fmt.Errorf("failed to save backup: %w", err)
	}

	m.logger.Info("backup created successfully",
		zap.String("backup_id", backup.BackupID),
		zap.Int64("size_bytes", backup.SizeBytes),
		zap.String("backup_path", backup.BackupPath))

	return backup, nil
}

// CreateManualBackup creates a manual backup of an extension
func (m *BackupManager) CreateManualBackup(
	databaseID, server, infobaseName, username, password, extensionName, createdBy string,
) (*models.ExtensionBackup, error) {
	m.logger.Info("creating manual backup",
		zap.String("extension_name", extensionName),
		zap.String("created_by", createdBy))

	// 1. Create temporary file for dump
	timestamp := time.Now().Format("2006-01-02_15-04-05")
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("%s_%s_manual.cfe", extensionName, timestamp))
	defer os.Remove(tmpFile)

	// 2. Dump extension
	dbPath := fmt.Sprintf("%s\\%s", server, infobaseName)
	err := m.v8executor.DumpExtension(dbPath, username, password, extensionName, tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to dump extension: %w", err)
	}

	// 3. Get file size
	fileInfo, err := os.Stat(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to stat backup file: %w", err)
	}

	// 4. Create backup record
	backup := &models.ExtensionBackup{
		BackupID:      uuid.New().String(),
		DatabaseID:    databaseID,
		ExtensionName: extensionName,
		Timestamp:     time.Now(),
		Reason:        "manual",
		SizeBytes:     fileInfo.Size(),
		CreatedBy:     createdBy,
	}

	// 5. Save backup file to storage
	file, err := os.Open(tmpFile)
	if err != nil {
		return nil, fmt.Errorf("failed to open temp backup file: %w", err)
	}
	defer file.Close()

	err = m.backupStorage.SaveBackup(databaseID, backup, file)
	if err != nil {
		return nil, fmt.Errorf("failed to save backup: %w", err)
	}

	m.logger.Info("manual backup created successfully",
		zap.String("backup_id", backup.BackupID))

	return backup, nil
}

// RestoreFromBackup restores an extension from a backup
func (m *BackupManager) RestoreFromBackup(
	backup *models.ExtensionBackup,
	server, infobaseName, username, password string,
) error {
	m.logger.Info("restoring from backup",
		zap.String("backup_id", backup.BackupID),
		zap.String("extension_name", backup.ExtensionName),
		zap.String("backup_path", backup.BackupPath))

	// 1. Validate backup file exists
	if err := m.backupStorage.ValidateBackupFile(backup.BackupPath); err != nil {
		return fmt.Errorf("backup file validation failed: %w", err)
	}

	// 2. Load extension from backup file
	dbPath := fmt.Sprintf("%s\\%s", server, infobaseName)
	err := m.v8executor.LoadExtensionFromFile(dbPath, username, password, backup.ExtensionName, backup.BackupPath)
	if err != nil {
		return fmt.Errorf("failed to load extension from backup: %w", err)
	}

	// 3. Update DB config
	err = m.v8executor.UpdateExtensionDBConfig(dbPath, username, password, backup.ExtensionName)
	if err != nil {
		return fmt.Errorf("failed to update DB config after restore: %w", err)
	}

	m.logger.Info("restore completed successfully",
		zap.String("extension_name", backup.ExtensionName))

	return nil
}

// ApplyRetentionPolicy applies retention policy to backups
func (m *BackupManager) ApplyRetentionPolicy(databaseID, extensionName string, keepCount int) error {
	return m.backupStorage.ApplyRetentionPolicy(databaseID, extensionName, keepCount)
}

// ListBackups returns list of backups for a database/extension
func (m *BackupManager) ListBackups(databaseID, extensionName string) ([]models.ExtensionBackup, error) {
	return m.backupStorage.ListBackups(databaseID, extensionName)
}

// GetLatestBackup returns the most recent backup
func (m *BackupManager) GetLatestBackup(databaseID, extensionName string) (*models.ExtensionBackup, error) {
	return m.backupStorage.GetLatestBackup(databaseID, extensionName)
}

// GetBackup returns a specific backup by timestamp
func (m *BackupManager) GetBackup(databaseID, extensionName, timestamp string) (*models.ExtensionBackup, error) {
	return m.backupStorage.GetBackup(databaseID, extensionName, timestamp)
}

// DeleteBackup deletes a backup
func (m *BackupManager) DeleteBackup(databaseID, backupID string) error {
	return m.backupStorage.DeleteBackup(databaseID, backupID)
}
