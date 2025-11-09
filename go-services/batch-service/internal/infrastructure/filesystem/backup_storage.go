package filesystem

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/command-center-1c/batch-service/internal/models"
	"go.uber.org/zap"
)

const (
	metadataFileName = "metadata.json"
)

// BackupMetadata represents the metadata file structure
type BackupMetadata struct {
	Backups []models.ExtensionBackup `json:"backups"`
}

// BackupStorage handles backup file storage and metadata management
type BackupStorage struct {
	basePath string // Base path for backups (e.g., "./backups")
	logger   *zap.Logger
}

// NewBackupStorage creates a new BackupStorage instance
func NewBackupStorage(basePath string, logger *zap.Logger) *BackupStorage {
	return &BackupStorage{
		basePath: basePath,
		logger:   logger,
	}
}

// SaveBackup saves a backup file and updates metadata
func (s *BackupStorage) SaveBackup(databaseID string, backup *models.ExtensionBackup, file io.Reader) error {
	s.logger.Info("saving backup",
		zap.String("database_id", databaseID),
		zap.String("extension_name", backup.ExtensionName),
		zap.String("backup_id", backup.BackupID))

	// 1. Ensure backup directory exists
	backupDir := s.getBackupDir(databaseID)
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return fmt.Errorf("failed to create backup directory: %w", err)
	}

	// 2. Generate backup file path
	timestamp := backup.Timestamp.Format("2006-01-02_15-04-05")
	fileName := fmt.Sprintf("%s_%s.cfe", backup.ExtensionName, timestamp)
	backupPath := filepath.Join(backupDir, fileName)

	// 3. Save backup file
	outFile, err := os.Create(backupPath)
	if err != nil {
		return fmt.Errorf("failed to create backup file: %w", err)
	}
	defer outFile.Close()

	written, err := io.Copy(outFile, file)
	if err != nil {
		return fmt.Errorf("failed to write backup file: %w", err)
	}

	backup.BackupPath = backupPath
	backup.SizeBytes = written

	s.logger.Info("backup file saved",
		zap.String("path", backupPath),
		zap.Int64("size_bytes", written))

	// 4. Update metadata
	if err := s.addBackupToMetadata(databaseID, backup); err != nil {
		return fmt.Errorf("failed to update metadata: %w", err)
	}

	return nil
}

// ListBackups returns list of backups for a database
// If extensionName is provided, filters by extension name
func (s *BackupStorage) ListBackups(databaseID string, extensionName string) ([]models.ExtensionBackup, error) {
	backups, err := s.loadMetadata(databaseID)
	if err != nil {
		if os.IsNotExist(err) {
			return []models.ExtensionBackup{}, nil
		}
		return nil, err
	}

	// Filter by extension name if provided
	if extensionName != "" {
		filtered := make([]models.ExtensionBackup, 0)
		for _, backup := range backups {
			if backup.ExtensionName == extensionName {
				filtered = append(filtered, backup)
			}
		}
		return filtered, nil
	}

	return backups, nil
}

// GetBackup returns a specific backup by timestamp
func (s *BackupStorage) GetBackup(databaseID, extensionName, timestamp string) (*models.ExtensionBackup, error) {
	backups, err := s.ListBackups(databaseID, extensionName)
	if err != nil {
		return nil, err
	}

	for _, backup := range backups {
		backupTimestamp := backup.Timestamp.Format("2006-01-02_15-04-05")
		if backupTimestamp == timestamp {
			return &backup, nil
		}
	}

	return nil, fmt.Errorf("backup not found: %s/%s/%s", databaseID, extensionName, timestamp)
}

// GetLatestBackup returns the most recent backup for an extension
func (s *BackupStorage) GetLatestBackup(databaseID, extensionName string) (*models.ExtensionBackup, error) {
	backups, err := s.ListBackups(databaseID, extensionName)
	if err != nil {
		return nil, err
	}

	if len(backups) == 0 {
		return nil, fmt.Errorf("no backups found for extension: %s/%s", databaseID, extensionName)
	}

	// Sort by timestamp descending
	sort.Slice(backups, func(i, j int) bool {
		return backups[i].Timestamp.After(backups[j].Timestamp)
	})

	return &backups[0], nil
}

// DeleteBackup removes a backup file and updates metadata
func (s *BackupStorage) DeleteBackup(databaseID, backupID string) error {
	s.logger.Info("deleting backup",
		zap.String("database_id", databaseID),
		zap.String("backup_id", backupID))

	// 1. Load metadata
	backups, err := s.loadMetadata(databaseID)
	if err != nil {
		return err
	}

	// 2. Find backup to delete
	var backupToDelete *models.ExtensionBackup
	filteredBackups := make([]models.ExtensionBackup, 0)

	for _, backup := range backups {
		if backup.BackupID == backupID {
			backupToDelete = &backup
		} else {
			filteredBackups = append(filteredBackups, backup)
		}
	}

	if backupToDelete == nil {
		return fmt.Errorf("backup not found: %s", backupID)
	}

	// 3. Delete physical file
	if err := os.Remove(backupToDelete.BackupPath); err != nil {
		s.logger.Warn("failed to delete backup file",
			zap.String("path", backupToDelete.BackupPath),
			zap.Error(err))
		// Continue anyway - metadata cleanup is more important
	}

	// 4. Update metadata
	if err := s.saveMetadata(databaseID, filteredBackups); err != nil {
		return fmt.Errorf("failed to update metadata after deletion: %w", err)
	}

	s.logger.Info("backup deleted successfully",
		zap.String("backup_id", backupID))

	return nil
}

// ApplyRetentionPolicy keeps only the last N backups for an extension
func (s *BackupStorage) ApplyRetentionPolicy(databaseID, extensionName string, keepCount int) error {
	s.logger.Info("applying retention policy",
		zap.String("database_id", databaseID),
		zap.String("extension_name", extensionName),
		zap.Int("keep_count", keepCount))

	backups, err := s.ListBackups(databaseID, extensionName)
	if err != nil {
		return err
	}

	if len(backups) <= keepCount {
		s.logger.Debug("no backups to clean up",
			zap.Int("current_count", len(backups)),
			zap.Int("keep_count", keepCount))
		return nil
	}

	// Sort by timestamp descending (newest first)
	sort.Slice(backups, func(i, j int) bool {
		return backups[i].Timestamp.After(backups[j].Timestamp)
	})

	// Delete old backups
	for i := keepCount; i < len(backups); i++ {
		if err := s.DeleteBackup(databaseID, backups[i].BackupID); err != nil {
			s.logger.Warn("failed to delete old backup during retention policy",
				zap.String("backup_id", backups[i].BackupID),
				zap.Error(err))
			// Continue with other backups
		}
	}

	s.logger.Info("retention policy applied",
		zap.Int("deleted_count", len(backups)-keepCount))

	return nil
}

// getBackupDir returns the backup directory path for a database
func (s *BackupStorage) getBackupDir(databaseID string) string {
	return filepath.Join(s.basePath, databaseID)
}

// loadMetadata loads backup metadata for a database
func (s *BackupStorage) loadMetadata(databaseID string) ([]models.ExtensionBackup, error) {
	metadataPath := filepath.Join(s.getBackupDir(databaseID), metadataFileName)

	data, err := os.ReadFile(metadataPath)
	if err != nil {
		return nil, err
	}

	var metadata BackupMetadata
	if err := json.Unmarshal(data, &metadata); err != nil {
		return nil, fmt.Errorf("failed to parse metadata: %w", err)
	}

	return metadata.Backups, nil
}

// saveMetadata saves backup metadata for a database
func (s *BackupStorage) saveMetadata(databaseID string, backups []models.ExtensionBackup) error {
	backupDir := s.getBackupDir(databaseID)
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return fmt.Errorf("failed to create backup directory: %w", err)
	}

	metadata := BackupMetadata{
		Backups: backups,
	}

	data, err := json.MarshalIndent(metadata, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	metadataPath := filepath.Join(backupDir, metadataFileName)
	if err := os.WriteFile(metadataPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write metadata: %w", err)
	}

	return nil
}

// addBackupToMetadata adds a new backup to metadata
func (s *BackupStorage) addBackupToMetadata(databaseID string, backup *models.ExtensionBackup) error {
	backups, err := s.loadMetadata(databaseID)
	if err != nil {
		if !os.IsNotExist(err) {
			return err
		}
		// Metadata doesn't exist yet - start with empty list
		backups = []models.ExtensionBackup{}
	}

	backups = append(backups, *backup)
	return s.saveMetadata(databaseID, backups)
}

// ValidateBackupFile checks if a backup file exists and is readable
func (s *BackupStorage) ValidateBackupFile(backupPath string) error {
	info, err := os.Stat(backupPath)
	if err != nil {
		return fmt.Errorf("backup file not accessible: %w", err)
	}

	if info.IsDir() {
		return fmt.Errorf("backup path is a directory, not a file")
	}

	if info.Size() == 0 {
		return fmt.Errorf("backup file is empty")
	}

	// Check if file is readable
	file, err := os.Open(backupPath)
	if err != nil {
		return fmt.Errorf("backup file not readable: %w", err)
	}
	file.Close()

	return nil
}

// GetBackupsByDateRange returns backups within a date range
func (s *BackupStorage) GetBackupsByDateRange(databaseID string, from, to time.Time) ([]models.ExtensionBackup, error) {
	backups, err := s.ListBackups(databaseID, "")
	if err != nil {
		return nil, err
	}

	filtered := make([]models.ExtensionBackup, 0)
	for _, backup := range backups {
		if (backup.Timestamp.Equal(from) || backup.Timestamp.After(from)) &&
			(backup.Timestamp.Equal(to) || backup.Timestamp.Before(to)) {
			filtered = append(filtered, backup)
		}
	}

	return filtered, nil
}

// GetBackupStats returns statistics about backups
func (s *BackupStorage) GetBackupStats(databaseID string) (totalCount int, totalSize int64, err error) {
	backups, err := s.ListBackups(databaseID, "")
	if err != nil {
		return 0, 0, err
	}

	totalCount = len(backups)
	totalSize = 0

	for _, backup := range backups {
		totalSize += backup.SizeBytes
	}

	return totalCount, totalSize, nil
}

// CleanupOrphanedBackups removes backup files that are not in metadata
func (s *BackupStorage) CleanupOrphanedBackups(databaseID string) error {
	s.logger.Info("cleaning up orphaned backups", zap.String("database_id", databaseID))

	backupDir := s.getBackupDir(databaseID)
	if _, err := os.Stat(backupDir); os.IsNotExist(err) {
		return nil // No backups directory
	}

	// Load metadata
	backups, err := s.loadMetadata(databaseID)
	if err != nil {
		if os.IsNotExist(err) {
			backups = []models.ExtensionBackup{}
		} else {
			return err
		}
	}

	// Build set of valid backup files
	validFiles := make(map[string]bool)
	for _, backup := range backups {
		validFiles[filepath.Base(backup.BackupPath)] = true
	}

	// Scan directory for .cfe files
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		return fmt.Errorf("failed to read backup directory: %w", err)
	}

	orphanedCount := 0
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".cfe") {
			continue
		}

		if !validFiles[entry.Name()] {
			// Orphaned file - delete it
			orphanedPath := filepath.Join(backupDir, entry.Name())
			if err := os.Remove(orphanedPath); err != nil {
				s.logger.Warn("failed to delete orphaned backup",
					zap.String("path", orphanedPath),
					zap.Error(err))
			} else {
				orphanedCount++
				s.logger.Debug("deleted orphaned backup",
					zap.String("file", entry.Name()))
			}
		}
	}

	if orphanedCount > 0 {
		s.logger.Info("orphaned backups cleaned up",
			zap.Int("count", orphanedCount))
	}

	return nil
}
