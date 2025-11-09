package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/command-center-1c/batch-service/internal/infrastructure/v8executor"
	"github.com/command-center-1c/batch-service/internal/models"
)

// ExtensionInstaller handles installation of 1C extensions using V8Executor
type ExtensionInstaller struct {
	executor *v8executor.V8Executor
}

// NewExtensionInstaller creates a new ExtensionInstaller
func NewExtensionInstaller(exe1cv8Path string, defaultTimeout time.Duration) *ExtensionInstaller {
	if defaultTimeout == 0 {
		defaultTimeout = 5 * time.Minute
	}

	return &ExtensionInstaller{
		executor: v8executor.NewV8Executor(exe1cv8Path, defaultTimeout),
	}
}

// InstallExtension installs an extension into a 1C infobase
func (i *ExtensionInstaller) InstallExtension(ctx context.Context, req *models.InstallExtensionRequest) (*models.InstallExtensionResponse, error) {
	startTime := time.Now()

	// Build request for V8Executor
	installReq := v8executor.InstallRequest{
		Server:        req.Server,
		InfobaseName:  req.InfobaseName,
		Username:      req.Username,
		Password:      req.Password,
		ExtensionName: req.ExtensionName,
		ExtensionPath: req.ExtensionPath,
	}

	// Install extension using V8Executor (LoadCfg + UpdateDBCfg)
	// Note: V8Executor.InstallExtension always performs UpdateDBCfg,
	// so we ignore the req.UpdateDBConfig flag (it's always true now)
	err := i.executor.InstallExtension(ctx, installReq)

	duration := time.Since(startTime)

	if err != nil {
		return &models.InstallExtensionResponse{
			Success:         false,
			Message:         fmt.Sprintf("Failed to install extension: %v", err),
			DurationSeconds: duration.Seconds(),
		}, err
	}

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
