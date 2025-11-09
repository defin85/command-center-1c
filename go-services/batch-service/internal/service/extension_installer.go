package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	v8 "github.com/v8platform/api"
	"go.uber.org/zap"
	"github.com/command-center-1c/batch-service/internal/models"
	"github.com/command-center-1c/batch-service/internal/domain/session"
	"github.com/command-center-1c/batch-service/internal/domain/rollback"
)

// ExtensionInstaller handles installation of 1C extensions using v8platform/api
type ExtensionInstaller struct {
	exe1cv8Path       string
	defaultTimeout    time.Duration
	sessionManager    *session.SessionManager
	backupManager     *rollback.BackupManager
	retentionBackups  int // Number of backups to keep
	logger            *zap.Logger
}

// NewExtensionInstaller creates a new ExtensionInstaller
func NewExtensionInstaller(
	exe1cv8Path string,
	defaultTimeout time.Duration,
	sessionManager *session.SessionManager,
	backupManager *rollback.BackupManager,
	retentionBackups int,
	logger *zap.Logger,
) *ExtensionInstaller {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if defaultTimeout == 0 {
		defaultTimeout = 5 * time.Minute
	}

	if retentionBackups <= 0 {
		retentionBackups = 5 // Default: keep 5 backups
	}

	return &ExtensionInstaller{
		exe1cv8Path:      exe1cv8Path,
		defaultTimeout:   defaultTimeout,
		sessionManager:   sessionManager,
		backupManager:    backupManager,
		retentionBackups: retentionBackups,
		logger:           logger,
	}
}

// InstallExtension installs an extension into a 1C infobase
func (i *ExtensionInstaller) InstallExtension(ctx context.Context, req *models.InstallExtensionRequest) (*models.InstallExtensionResponse, error) {
	startTime := time.Now()

	i.logger.Info("starting extension installation",
		zap.String("infobase", req.InfobaseName),
		zap.String("extension", req.ExtensionName),
		zap.Bool("force_terminate_sessions", req.ForceTerminateSessions))

	// Get database ID (using InfobaseName as ID for now - will be replaced with real UUID)
	databaseID := req.InfobaseName

	// 1. Terminate active sessions if requested
	if req.ForceTerminateSessions {
		i.logger.Info("terminating active sessions before installation",
			zap.String("infobase", req.InfobaseName))

		// TODO: Get infobase UUID from infobase name (requires cluster-service integration)
		// For now, use infobase name as ID (MOCK implementation)
		infobaseID := req.InfobaseName

		if err := i.sessionManager.TerminateSessionsIfNeeded(infobaseID, true); err != nil {
			i.logger.Error("failed to terminate sessions",
				zap.String("infobase", req.InfobaseName),
				zap.Error(err))
			return &models.InstallExtensionResponse{
				Success:         false,
				Message:         fmt.Sprintf("Session termination failed: %v", err),
				DurationSeconds: time.Since(startTime).Seconds(),
			}, fmt.Errorf("session termination failed: %w", err)
		}

		i.logger.Info("sessions terminated successfully",
			zap.String("infobase", req.InfobaseName))
	}

	// 2. Create backup of existing extension (if exists)
	var backup *models.ExtensionBackup
	var backupErr error

	i.logger.Info("attempting to create pre-install backup",
		zap.String("extension_name", req.ExtensionName))

	backup, backupErr = i.backupManager.CreatePreInstallBackup(
		databaseID, req.Server, req.InfobaseName, req.Username, req.Password, req.ExtensionName,
	)

	if backupErr != nil {
		i.logger.Warn("failed to create backup (extension may not exist, continuing with installation)",
			zap.String("extension_name", req.ExtensionName),
			zap.Error(backupErr))
		// Continue anyway - this might be the first installation
	} else if backup != nil {
		i.logger.Info("backup created successfully",
			zap.String("backup_id", backup.BackupID),
			zap.Int64("size_bytes", backup.SizeBytes))
	} else {
		i.logger.Info("no backup needed (extension does not exist yet)")
	}

	// 3. Create infobase connection
	infobase := v8.NewServerIB(req.Server, req.InfobaseName)

	// 4. Load extension from .cfe file
	what := v8.LoadExtensionCfg(req.ExtensionName, req.ExtensionPath)

	// 5. Execute installation with v8platform/api
	i.logger.Info("executing extension installation",
		zap.String("infobase", req.InfobaseName),
		zap.String("extension_path", req.ExtensionPath))

	err := v8.Run(infobase, what,
		v8.WithCredentials(req.Username, req.Password),
		v8.WithTimeout(int64(i.defaultTimeout.Seconds())),
		v8.WithPath(i.exe1cv8Path),
	)

	if err != nil {
		// Installation failed - attempt restore from backup if exists
		i.logger.Error("extension installation failed",
			zap.String("infobase", req.InfobaseName),
			zap.Error(err))

		if backup != nil {
			i.logger.Info("attempting to restore from backup after installation failure",
				zap.String("backup_id", backup.BackupID))

			restoreErr := i.backupManager.RestoreFromBackup(
				backup, req.Server, req.InfobaseName, req.Username, req.Password,
			)

			if restoreErr != nil {
				i.logger.Error("restore from backup failed",
					zap.String("backup_id", backup.BackupID),
					zap.Error(restoreErr))
				return &models.InstallExtensionResponse{
					Success:         false,
					Message:         fmt.Sprintf("Installation failed: %v. Restore also failed: %v", err, restoreErr),
					DurationSeconds: time.Since(startTime).Seconds(),
				}, fmt.Errorf("installation failed: %w, restore also failed: %v", err, restoreErr)
			}

			i.logger.Info("successfully restored from backup after installation failure")
			return &models.InstallExtensionResponse{
				Success:         false,
				Message:         fmt.Sprintf("Installation failed: %v. Extension restored to previous version from backup.", err),
				DurationSeconds: time.Since(startTime).Seconds(),
			}, fmt.Errorf("installation failed (restored from backup): %w", err)
		}

		return &models.InstallExtensionResponse{
			Success:         false,
			Message:         fmt.Sprintf("Failed to install extension: %v", err),
			DurationSeconds: time.Since(startTime).Seconds(),
		}, err
	}

	// 6. Update DB configuration if requested
	if req.UpdateDBConfig {
		updateWhat := v8.UpdateExtensionDBCfg(req.ExtensionName, true, false)

		err = v8.Run(infobase, updateWhat,
			v8.WithCredentials(req.Username, req.Password),
			v8.WithTimeout(int64(i.defaultTimeout.Seconds())),
			v8.WithPath(i.exe1cv8Path),
		)

		if err != nil {
			return &models.InstallExtensionResponse{
				Success:         false,
				Message:         fmt.Sprintf("Extension installed but failed to update DB config: %v", err),
				DurationSeconds: time.Since(startTime).Seconds(),
			}, err
		}
	}

	// 7. SUCCESS - apply retention policy to clean up old backups
	if backup != nil {
		i.logger.Info("applying retention policy to old backups",
			zap.String("extension_name", req.ExtensionName),
			zap.Int("keep_count", i.retentionBackups))

		if err := i.backupManager.ApplyRetentionPolicy(databaseID, req.ExtensionName, i.retentionBackups); err != nil {
			i.logger.Warn("failed to apply retention policy (non-critical)",
				zap.Error(err))
			// Don't fail the installation due to cleanup error
		}
	}

	duration := time.Since(startTime)

	i.logger.Info("extension installation completed successfully",
		zap.Float64("duration_seconds", duration.Seconds()))

	return &models.InstallExtensionResponse{
		Success:         true,
		Message:         fmt.Sprintf("Extension '%s' installed successfully on '%s'", req.ExtensionName, req.InfobaseName),
		DurationSeconds: duration.Seconds(),
	}, nil
}

// BatchInstall installs extension on multiple infobases in parallel
func (i *ExtensionInstaller) BatchInstall(ctx context.Context, req *models.BatchInstallRequest) *models.BatchInstallResponse {
	// Default to 10 parallel workers
	parallelWorkers := req.ParallelWorkers
	if parallelWorkers <= 0 {
		parallelWorkers = 10
	}

	results := make([]models.InstallResult, len(req.Infobases))
	sem := make(chan struct{}, parallelWorkers) // Semaphore for limiting concurrency

	var wg sync.WaitGroup

	for idx, installReq := range req.Infobases {
		wg.Add(1)

		go func(index int, request models.InstallExtensionRequest) {
			defer wg.Done()

			// Acquire semaphore
			sem <- struct{}{}
			defer func() { <-sem }() // Release semaphore

			startTime := time.Now()

			// Install extension
			_, err := i.InstallExtension(ctx, &request)

			status := "success"
			errorMsg := ""

			if err != nil {
				status = "failed"
				errorMsg = err.Error()
			}

			results[index] = models.InstallResult{
				Infobase:        request.InfobaseName,
				Status:          status,
				Error:           errorMsg,
				DurationSeconds: time.Since(startTime).Seconds(),
			}
		}(idx, installReq)
	}

	wg.Wait()

	// Count successes and failures
	successCount := 0
	failedCount := 0

	for _, result := range results {
		if result.Status == "success" {
			successCount++
		} else {
			failedCount++
		}
	}

	return &models.BatchInstallResponse{
		Total:   len(req.Infobases),
		Success: successCount,
		Failed:  failedCount,
		Results: results,
	}
}
