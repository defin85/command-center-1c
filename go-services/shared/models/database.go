package models

import "time"

// DatabaseStatus represents the status of a 1C database
type DatabaseStatus string

const (
	DatabaseStatusActive   DatabaseStatus = "active"
	DatabaseStatusInactive DatabaseStatus = "inactive"
	DatabaseStatusError    DatabaseStatus = "error"
)

// Database represents a 1C database configuration
type Database struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Description string         `json:"description,omitempty"`
	Host        string         `json:"host"`
	Port        int            `json:"port"`
	BaseName    string         `json:"base_name"`
	ODataURL    string         `json:"odata_url"`
	Username    string         `json:"username"`
	Password    string         `json:"password,omitempty"` // Should be encrypted
	Status      DatabaseStatus `json:"status"`
	Version     string         `json:"version,omitempty"`
	LastCheck   *time.Time     `json:"last_check,omitempty"`
	CreatedAt   time.Time      `json:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at"`
}

// DatabaseGroup represents a group of databases
type DatabaseGroup struct {
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Description string     `json:"description,omitempty"`
	DatabaseIDs []string   `json:"database_ids"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
}

// DatabaseHealth represents health check information
type DatabaseHealth struct {
	DatabaseID  string    `json:"database_id"`
	IsHealthy   bool      `json:"is_healthy"`
	ResponseTime time.Duration `json:"response_time"`
	Error       string    `json:"error,omitempty"`
	CheckedAt   time.Time `json:"checked_at"`
}
