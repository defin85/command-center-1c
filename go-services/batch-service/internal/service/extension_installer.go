package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	v8 "github.com/v8platform/api"
	"github.com/command-center-1c/batch-service/internal/models"
)

// ExtensionInstaller handles installation of 1C extensions using v8platform/api
type ExtensionInstaller struct {
	exe1cv8Path    string
	defaultTimeout time.Duration
}

// NewExtensionInstaller creates a new ExtensionInstaller
func NewExtensionInstaller(exe1cv8Path string, defaultTimeout time.Duration) *ExtensionInstaller {
	if exe1cv8Path == "" {
		exe1cv8Path = `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`
	}

	if defaultTimeout == 0 {
		defaultTimeout = 5 * time.Minute
	}

	return &ExtensionInstaller{
		exe1cv8Path:    exe1cv8Path,
		defaultTimeout: defaultTimeout,
	}
}

// InstallExtension installs an extension into a 1C infobase
func (i *ExtensionInstaller) InstallExtension(ctx context.Context, req *models.InstallExtensionRequest) (*models.InstallExtensionResponse, error) {
	startTime := time.Now()

	// 1. Create infobase connection
	infobase := v8.NewServerIB(req.Server, req.InfobaseName)

	// 2. Load extension from .cfe file
	what := v8.LoadExtensionCfg(req.ExtensionName, req.ExtensionPath)

	// 3. Execute installation with v8platform/api
	err := v8.Run(infobase, what,
		v8.WithCredentials(req.Username, req.Password),
		v8.WithTimeout(int64(i.defaultTimeout.Seconds())),
		v8.WithPath(i.exe1cv8Path),
	)

	if err != nil {
		return &models.InstallExtensionResponse{
			Success:         false,
			Message:         fmt.Sprintf("Failed to install extension: %v", err),
			DurationSeconds: time.Since(startTime).Seconds(),
		}, err
	}

	// 4. Update DB configuration if requested
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

	duration := time.Since(startTime)

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
