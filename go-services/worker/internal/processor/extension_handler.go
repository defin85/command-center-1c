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
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow"
)

// ExtensionInstallRequest represents Batch Service install request
// Must match batch-service/internal/models/extension.go:InstallExtensionRequest
type ExtensionInstallRequest struct {
	Server                 string `json:"server"`                   // "localhost" or "localhost:1541"
	InfobaseName           string `json:"infobase_name"`            // e.g., "dev"
	Username               string `json:"username"`
	Password               string `json:"password"`
	ExtensionPath          string `json:"extension_path"`           // Path to .cfe file
	ExtensionName          string `json:"extension_name"`           // Extension name
	UpdateDBConfig         bool   `json:"update_db_config"`         // Update database configuration
	ForceTerminateSessions bool   `json:"force_terminate_sessions"` // Terminate active sessions before install
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

// ClusterInfo represents cluster metadata for workflow operations
type ClusterInfo struct {
	DatabaseID string `json:"database_id"`
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
}

// fetchClusterInfo получает cluster_id и infobase_id через Orchestrator API
func (p *TaskProcessor) fetchClusterInfo(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	url := fmt.Sprintf("%s/api/v1/databases/%s/cluster-info", p.config.OrchestratorURL, databaseID)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("cluster-info endpoint returned status %d", resp.StatusCode)
	}

	var info ClusterInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, err
	}

	return &info, nil
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
		// Детальный error log
		log.Errorf("failed to fetch credentials for database %s: %v", databaseID, err)

		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("failed to fetch credentials: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// Success log
	log.Infof("credentials fetched successfully for database %s, odata_url=%s", databaseID, creds.ODataURL)

	// Build server address for Batch Service using 1C Server fields (not OData)
	// Format: "localhost" or "localhost:1541" (if port is not default 1540)
	serverAddress := creds.ServerAddress
	if creds.ServerPort != 0 && creds.ServerPort != 1540 {
		serverAddress = fmt.Sprintf("%s:%d", creds.ServerAddress, creds.ServerPort)
	}

	// Use InfobaseName from credentials (не BaseName из OData URL)
	infobaseName := creds.InfobaseName
	if infobaseName == "" {
		// Fallback to BaseName if InfobaseName not provided
		infobaseName = creds.BaseName
		log.Warnf("InfobaseName not provided for database %s, using BaseName fallback: %s", databaseID, infobaseName)
	}

	// Update status to 50%
	if err := p.updateExtensionStatus(ctx, databaseID, "in_progress", "", 50); err != nil {
		log.Warnf("failed to update status to 50%%: %v", err)
	}

	// NEW: Fetch cluster info для workflow
	clusterInfo, err := p.fetchClusterInfo(ctx, databaseID)
	if err != nil {
		log.Errorf("failed to fetch cluster info for database %s: %v", databaseID, err)
		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("failed to fetch cluster info: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch cluster info: %v", err)
		result.ErrorCode = "CLUSTER_INFO_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// NEW: Initialize workflow with Redis Pub/Sub support
	redisAddr := fmt.Sprintf("%s:%s", p.config.RedisHost, p.config.RedisPort)
	pubSubEnabled := true // TODO: Add config parameter REDIS_PUBSUB_ENABLED

	workflowOrchestrator := workflow.NewExtensionInstallWorkflow(
		p.config.ClusterServiceURL,
		redisAddr,
		pubSubEnabled,
	)

	// NEW: Execute pre-install (lock jobs + terminate sessions + wait)
	log.Infof("Starting pre-install workflow (lock + terminate + wait)")
	err = workflowOrchestrator.PreInstall(ctx, workflow.WorkflowParams{
		ClusterID:  clusterInfo.ClusterID,
		InfobaseID: clusterInfo.InfobaseID,
	})
	if err != nil {
		log.Errorf("pre-install workflow failed: %v", err)
		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("workflow error: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("workflow error: %v", err)
		result.ErrorCode = "WORKFLOW_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// CRITICAL: defer rollback для гарантии unlock
	defer func() {
		if !result.Success {
			log.Warnf("Installation failed, executing rollback (unlock jobs)")
			workflowOrchestrator.Rollback(context.Background(), workflow.WorkflowParams{
				ClusterID:  clusterInfo.ClusterID,
				InfobaseID: clusterInfo.InfobaseID,
			})
		}
	}()

	// Call Batch Service with structured request
	installReq := ExtensionInstallRequest{
		Server:                 serverAddress,
		InfobaseName:           infobaseName,
		Username:               creds.Username,
		Password:               creds.Password,
		ExtensionPath:          extensionPath,
		ExtensionName:          extensionName,
		UpdateDBConfig:         false, // Default: don't update DB config
		ForceTerminateSessions: true,  // Force terminate sessions для успешного UpdateDBCfg
	}

	// Log request details
	batchServiceURL := fmt.Sprintf("%s/api/v1/extensions/install", p.config.BatchServiceURL)
	log.Infof("calling Batch Service for database %s, url=%s, extension=%s, path=%s",
		databaseID, batchServiceURL, extensionName, extensionPath)

	installResp, err := p.callBatchService(ctx, batchServiceURL, installReq)
	if err != nil {
		// Детальный error log
		log.Errorf("batch service call failed for database %s, url=%s, error=%v",
			databaseID, batchServiceURL, err)

		p.updateExtensionStatus(ctx, databaseID, "failed", fmt.Sprintf("batch service error: %v", err), 0)
		result.Success = false
		result.Error = fmt.Sprintf("batch service error: %v", err)
		result.ErrorCode = "BATCH_SERVICE_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	if !installResp.Success {
		// Детальный error log
		log.Errorf("extension installation failed for database %s, batch_error=%s",
			databaseID, installResp.Error)

		p.updateExtensionStatus(ctx, databaseID, "failed", installResp.Error, 0)
		result.Success = false
		result.Error = installResp.Error
		result.ErrorCode = "INSTALLATION_FAILED"
		result.Duration = time.Since(start).Seconds()
		return result
	}

	// NEW: Execute post-install (unlock jobs)
	log.Infof("Starting post-install workflow (unlock jobs)")
	err = workflowOrchestrator.PostInstall(ctx, workflow.WorkflowParams{
		ClusterID:  clusterInfo.ClusterID,
		InfobaseID: clusterInfo.InfobaseID,
	})
	if err != nil {
		log.Errorf("CRITICAL: post-install workflow failed: %v", err)
		// Не возвращаем error - установка прошла успешно, только unlock failed
		// Admin должен вручную unlock
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
