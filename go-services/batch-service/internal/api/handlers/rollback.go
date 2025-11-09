package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/command-center-1c/batch-service/internal/domain/rollback"
	"github.com/command-center-1c/batch-service/internal/models"
)

// RollbackHandler handles rollback and backup-related operations
type RollbackHandler struct {
	rollbackManager *rollback.RollbackManager
	backupManager   *rollback.BackupManager
	logger          *zap.Logger
}

// NewRollbackHandler creates a new RollbackHandler
func NewRollbackHandler(
	rollbackManager *rollback.RollbackManager,
	backupManager *rollback.BackupManager,
	logger *zap.Logger,
) *RollbackHandler {
	return &RollbackHandler{
		rollbackManager: rollbackManager,
		backupManager:   backupManager,
		logger:          logger,
	}
}

// RollbackExtension handles POST /api/v1/extensions/rollback
// @Summary Rollback extension to a previous backup
// @Description Rolls back an extension to a specific backup or the latest backup
// @Tags rollback
// @Accept json
// @Produce json
// @Param request body models.RollbackRequest true "Rollback request"
// @Success 200 {object} models.RollbackResponse
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/rollback [post]
func (h *RollbackHandler) RollbackExtension(c *gin.Context) {
	var req models.RollbackRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		h.logger.Error("invalid rollback request",
			zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request format: " + err.Error(),
		})
		return
	}

	h.logger.Info("processing rollback request",
		zap.String("database_id", req.DatabaseID),
		zap.String("extension_name", req.ExtensionName),
		zap.String("backup_timestamp", req.BackupTimestamp))

	// Validate request
	if err := h.rollbackManager.ValidateRollbackRequest(req); err != nil {
		h.logger.Error("rollback validation failed",
			zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Validation failed: " + err.Error(),
		})
		return
	}

	// Perform rollback
	resp, err := h.rollbackManager.Rollback(req)
	if err != nil {
		h.logger.Error("rollback failed",
			zap.String("database_id", req.DatabaseID),
			zap.String("extension_name", req.ExtensionName),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Rollback failed: " + err.Error(),
		})
		return
	}

	h.logger.Info("rollback completed successfully",
		zap.String("database_id", req.DatabaseID),
		zap.String("extension_name", req.ExtensionName),
		zap.Float64("duration_seconds", resp.Duration))

	c.JSON(http.StatusOK, resp)
}

// ListBackupsForDatabase handles GET /api/v1/extensions/backups/:database_id
// @Summary List backups for a database
// @Description Returns list of all backups for a specific database, optionally filtered by extension name
// @Tags rollback
// @Produce json
// @Param database_id path string true "Database ID"
// @Param extension_name query string false "Filter by extension name"
// @Success 200 {object} models.BackupListResponse
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/backups/{database_id} [get]
func (h *RollbackHandler) ListBackupsForDatabase(c *gin.Context) {
	databaseID := c.Param("database_id")
	extensionName := c.Query("extension_name") // optional filter

	if databaseID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "database_id is required",
		})
		return
	}

	h.logger.Info("listing backups",
		zap.String("database_id", databaseID),
		zap.String("extension_name", extensionName))

	backups, err := h.backupManager.ListBackups(databaseID, extensionName)
	if err != nil {
		h.logger.Error("failed to list backups",
			zap.String("database_id", databaseID),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to list backups: " + err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, models.BackupListResponse{
		Backups:    backups,
		TotalCount: len(backups),
	})
}

// GetLatestBackup handles GET /api/v1/extensions/backups/:database_id/latest
// @Summary Get latest backup for extension
// @Description Returns the most recent backup for a specific extension
// @Tags rollback
// @Produce json
// @Param database_id path string true "Database ID"
// @Param extension_name query string true "Extension name"
// @Success 200 {object} models.ExtensionBackup
// @Failure 400 {object} map[string]string
// @Failure 404 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/backups/{database_id}/latest [get]
func (h *RollbackHandler) GetLatestBackup(c *gin.Context) {
	databaseID := c.Param("database_id")
	extensionName := c.Query("extension_name")

	if databaseID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "database_id is required",
		})
		return
	}

	if extensionName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "extension_name query parameter is required",
		})
		return
	}

	h.logger.Info("getting latest backup",
		zap.String("database_id", databaseID),
		zap.String("extension_name", extensionName))

	backup, err := h.backupManager.GetLatestBackup(databaseID, extensionName)
	if err != nil {
		h.logger.Error("failed to get latest backup",
			zap.String("database_id", databaseID),
			zap.String("extension_name", extensionName),
			zap.Error(err))
		c.JSON(http.StatusNotFound, gin.H{
			"error": "No backups found: " + err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, backup)
}

// DeleteBackup handles DELETE /api/v1/extensions/backups/:database_id/:backup_id
// @Summary Delete a specific backup
// @Description Deletes a backup by its ID
// @Tags rollback
// @Produce json
// @Param database_id path string true "Database ID"
// @Param backup_id path string true "Backup ID"
// @Success 200 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/backups/{database_id}/{backup_id} [delete]
func (h *RollbackHandler) DeleteBackup(c *gin.Context) {
	databaseID := c.Param("database_id")
	backupID := c.Param("backup_id")

	if databaseID == "" || backupID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "database_id and backup_id are required",
		})
		return
	}

	h.logger.Info("deleting backup",
		zap.String("database_id", databaseID),
		zap.String("backup_id", backupID))

	if err := h.backupManager.DeleteBackup(databaseID, backupID); err != nil {
		h.logger.Error("failed to delete backup",
			zap.String("database_id", databaseID),
			zap.String("backup_id", backupID),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to delete backup: " + err.Error(),
		})
		return
	}

	h.logger.Info("backup deleted successfully",
		zap.String("backup_id", backupID))

	c.JSON(http.StatusOK, gin.H{
		"message": "Backup deleted successfully",
	})
}

// GetRollbackHistory handles GET /api/v1/extensions/rollback/history
// @Summary Get rollback history
// @Description Returns available backups for rollback (alias for list backups)
// @Tags rollback
// @Produce json
// @Param database_id query string true "Database ID"
// @Param extension_name query string true "Extension name"
// @Success 200 {object} models.BackupListResponse
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/rollback/history [get]
func (h *RollbackHandler) GetRollbackHistory(c *gin.Context) {
	databaseID := c.Query("database_id")
	extensionName := c.Query("extension_name")

	if databaseID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "database_id query parameter is required",
		})
		return
	}

	if extensionName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "extension_name query parameter is required",
		})
		return
	}

	h.logger.Info("getting rollback history",
		zap.String("database_id", databaseID),
		zap.String("extension_name", extensionName))

	backups, err := h.rollbackManager.GetRollbackHistory(databaseID, extensionName)
	if err != nil {
		h.logger.Error("failed to get rollback history",
			zap.String("database_id", databaseID),
			zap.String("extension_name", extensionName),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get rollback history: " + err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, models.BackupListResponse{
		Backups:    backups,
		TotalCount: len(backups),
	})
}

// CreateManualBackup handles POST /api/v1/extensions/backups/create
// @Summary Create manual backup
// @Description Creates a manual backup of an extension
// @Tags rollback
// @Accept json
// @Produce json
// @Param request body object true "Manual backup request"
// @Success 200 {object} models.ExtensionBackup
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/v1/extensions/backups/create [post]
func (h *RollbackHandler) CreateManualBackup(c *gin.Context) {
	var req struct {
		DatabaseID    string `json:"database_id" binding:"required"`
		Server        string `json:"server" binding:"required"`
		InfobaseName  string `json:"infobase_name" binding:"required"`
		Username      string `json:"username" binding:"required"`
		Password      string `json:"password" binding:"required"`
		ExtensionName string `json:"extension_name" binding:"required"`
		CreatedBy     string `json:"created_by"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		h.logger.Error("invalid manual backup request",
			zap.Error(err))
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request format: " + err.Error(),
		})
		return
	}

	h.logger.Info("creating manual backup",
		zap.String("database_id", req.DatabaseID),
		zap.String("extension_name", req.ExtensionName),
		zap.String("created_by", req.CreatedBy))

	backup, err := h.backupManager.CreateManualBackup(
		req.DatabaseID, req.Server, req.InfobaseName,
		req.Username, req.Password, req.ExtensionName, req.CreatedBy,
	)

	if err != nil {
		h.logger.Error("failed to create manual backup",
			zap.String("database_id", req.DatabaseID),
			zap.String("extension_name", req.ExtensionName),
			zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to create backup: " + err.Error(),
		})
		return
	}

	h.logger.Info("manual backup created successfully",
		zap.String("backup_id", backup.BackupID))

	c.JSON(http.StatusOK, backup)
}
