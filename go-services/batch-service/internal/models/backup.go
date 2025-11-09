package models

import "time"

// ExtensionBackup represents a backup of a 1C extension
type ExtensionBackup struct {
	BackupID      string    `json:"backup_id"`      // UUID
	DatabaseID    string    `json:"database_id"`    // UUID of database
	ExtensionName string    `json:"extension_name"` // Name of extension
	BackupPath    string    `json:"backup_path"`    // Path to .cfe backup file
	Timestamp     time.Time `json:"timestamp"`      // When backup was created
	Reason        string    `json:"reason"`         // "pre_install", "manual", "pre_rollback"
	SizeBytes     int64     `json:"size_bytes"`     // File size in bytes
	CreatedBy     string    `json:"created_by,omitempty"`
	Version       string    `json:"version,omitempty"` // Version of extension if known
}

// BackupListResponse represents a list of backups
type BackupListResponse struct {
	Backups    []ExtensionBackup `json:"backups"`
	TotalCount int               `json:"total_count"`
}

// RollbackRequest represents a request to rollback extension to a backup
type RollbackRequest struct {
	DatabaseID      string `json:"database_id" binding:"required"`
	Server          string `json:"server" binding:"required"`
	InfobaseName    string `json:"infobase_name" binding:"required"`
	Username        string `json:"username" binding:"required"`
	Password        string `json:"password" binding:"required"`
	ExtensionName   string `json:"extension_name" binding:"required"`
	BackupTimestamp string `json:"backup_timestamp"` // optional - latest if empty
}

// RollbackResponse represents the response from rollback operation
type RollbackResponse struct {
	Success      bool      `json:"success"`
	Message      string    `json:"message"`
	BackupUsed   string    `json:"backup_used"`
	RolledBackAt time.Time `json:"rolled_back_at"`
	Duration     float64   `json:"duration_seconds"`
}
