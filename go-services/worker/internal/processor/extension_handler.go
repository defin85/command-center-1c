// go-services/worker/internal/processor/extension_handler.go
package processor

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

// ExtensionInstallRequest represents Batch Service install request
type ExtensionInstallRequest struct {
	ConnectionString string `json:"connection_string"`
	ExtensionPath    string `json:"extension_path"`
	ExtensionName    string `json:"extension_name"`
}

// ExtensionInstallResponse represents Batch Service install response
type ExtensionInstallResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Error   string `json:"error,omitempty"`
}

// StatusUpdateRequest represents Django status update request
type StatusUpdateRequest struct {
	Status          string `json:"status"`
	ErrorMessage    string `json:"error_message,omitempty"`
	ProgressPercent int    `json:"progress_percent,omitempty"`
}

// executeExtensionInstall handles extension installation via Batch Service
func (p *TaskProcessor) executeExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
	log := logger.GetLogger()
	start := time.Now()

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	// Extract extension data from payload
	extensionName, ok := msg.Payload.Data["extension_name"].(string)
	if !ok || extensionName == "" {
		result.Success = false
		result.Error = "extension_name is required in payload.data"
		result.ErrorCode = "VALIDATION_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	extensionPath, ok := msg.Payload.Data["extension_path"].(string)
	if !ok || extensionPath == "" {
		result.Success = false
		result.Error = "extension_path is required in payload.data"
		result.ErrorCode = "VALIDATION_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	log.Infof("installing extension %s on database %s", extensionName, databaseID)

	// Update status to in_progress
	if err := p.updateExtensionStatus(ctx, databaseID, "in_progress", "", 10); err != nil {
		log.Warnf("failed to update status to in_progress: %v", err)
	}

	// Fetch database credentials
	creds, err := p.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("failed to fetch credentials: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Build connection string for 1cv8.exe
	// Format: /S<server>\<infobase> /N<username> /P<password>
	// If port is not default (1540), use server:port format
	serverAddress := creds.Host
	if creds.Port != 0 && creds.Port != 1540 {
		serverAddress = fmt.Sprintf("%s:%d", creds.Host, creds.Port)
	}

	connectionString := fmt.Sprintf("/S%s\\%s /N%s /P%s",
		serverAddress,
		creds.BaseName,
		creds.Username,
		creds.Password,
	)

	// Update status to 50%
	if err := p.updateExtensionStatus(ctx, databaseID, "in_progress", "", 50); err != nil {
		log.Warnf("failed to update status to 50%%: %v", err)
	}

	// Call Batch Service
	installReq := ExtensionInstallRequest{
		ConnectionString: connectionString,
		ExtensionPath:    extensionPath,
		ExtensionName:    extensionName,
	}

	batchServiceURL := fmt.Sprintf("%s/api/v1/extensions/install", p.config.BatchServiceURL)
	installResp, err := p.callBatchService(ctx, batchServiceURL, installReq)
	if err != nil {
		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("batch service error: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("batch service error: %v", err)
		result.ErrorCode = "BATCH_SERVICE_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	if !installResp.Success {
		p.updateExtensionStatus(ctx, databaseID, "failed", installResp.Error, 0)
		result.Success = false
		result.Error = installResp.Error
		result.ErrorCode = "INSTALLATION_FAILED"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Update status to completed
	if err := p.updateExtensionStatus(ctx, databaseID, "completed", "", 100); err != nil {
		log.Warnf("failed to update status to completed: %v", err)
	}

	result.Success = true
	result.Data = map[string]interface{}{
		"extension_name": extensionName,
		"message":        installResp.Message,
	}
	result.Duration = time.Since(start).Seconds()

	log.Infof("successfully installed extension %s on database %s, duration=%.2fs", extensionName, databaseID, result.Duration)

	return result
}

// callBatchService calls Batch Service API
func (p *TaskProcessor) callBatchService(ctx context.Context, url string, req ExtensionInstallRequest) (*ExtensionInstallResponse, error) {
	log := logger.GetLogger()

	// Marshal request
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Execute request
	client := &http.Client{Timeout: 5 * time.Minute} // Extension install can take time
	resp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		log.Errorf("batch service returned status %d: %s", resp.StatusCode, string(respBody))
		return nil, fmt.Errorf("batch service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse response
	var installResp ExtensionInstallResponse
	if err := json.Unmarshal(respBody, &installResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return &installResp, nil
}

// updateExtensionStatus updates extension installation status in Django
func (p *TaskProcessor) updateExtensionStatus(ctx context.Context, databaseID, status, errorMessage string, progressPercent int) error {
	log := logger.GetLogger()

	statusReq := StatusUpdateRequest{
		Status:          status,
		ErrorMessage:    errorMessage,
		ProgressPercent: progressPercent,
	}

	reqBody, err := json.Marshal(statusReq)
	if err != nil {
		return fmt.Errorf("failed to marshal status request: %w", err)
	}

	// PATCH /api/v1/databases/{id}/extension-installation-status/
	url := fmt.Sprintf("%s/api/v1/databases/%s/extension-installation-status/", p.config.OrchestratorURL, databaseID)

	httpReq, err := http.NewRequestWithContext(ctx, "PATCH", url, bytes.NewBuffer(reqBody))
	if err != nil {
		return fmt.Errorf("failed to create status update request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		return fmt.Errorf("failed to execute status update: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		log.Errorf("status update failed with status %d: %s", resp.StatusCode, string(respBody))
		return fmt.Errorf("status update returned status %d", resp.StatusCode)
	}

	log.Infof("updated extension status for database %s: status=%s, progress=%d%%", databaseID, status, progressPercent)

	return nil
}
