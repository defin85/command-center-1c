package models

import "time"

// OperationStatus represents the status of an operation
type OperationStatus string

const (
	OperationStatusPending    OperationStatus = "pending"
	OperationStatusProcessing OperationStatus = "processing"
	OperationStatusCompleted  OperationStatus = "completed"
	OperationStatusFailed     OperationStatus = "failed"
	OperationStatusCancelled  OperationStatus = "cancelled"
)

// OperationType represents the type of operation
type OperationType string

const (
	OperationTypeCreate OperationType = "create"
	OperationTypeUpdate OperationType = "update"
	OperationTypeDelete OperationType = "delete"
	OperationTypeQuery  OperationType = "query"
)

// Operation represents a task for workers
type Operation struct {
	ID           string                 `json:"id"`
	Type         OperationType          `json:"type"`
	Status       OperationStatus        `json:"status"`
	DatabaseID   string                 `json:"database_id"`
	TemplateID   string                 `json:"template_id,omitempty"`
	Payload      map[string]interface{} `json:"payload"`
	Result       map[string]interface{} `json:"result,omitempty"`
	Error        string                 `json:"error,omitempty"`
	CreatedAt    time.Time              `json:"created_at"`
	UpdatedAt    time.Time              `json:"updated_at"`
	CompletedAt  *time.Time             `json:"completed_at,omitempty"`
	RetryCount   int                    `json:"retry_count"`
	MaxRetries   int                    `json:"max_retries"`
}

// BatchOperation represents a batch of operations
type BatchOperation struct {
	ID         string                 `json:"id"`
	Operations []Operation            `json:"operations"`
	Status     OperationStatus        `json:"status"`
	Progress   int                    `json:"progress"` // 0-100
	Total      int                    `json:"total"`
	Completed  int                    `json:"completed"`
	Failed     int                    `json:"failed"`
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt  time.Time              `json:"created_at"`
	UpdatedAt  time.Time              `json:"updated_at"`
}

// OperationResult represents the result of an operation
type OperationResult struct {
	OperationID string                 `json:"operation_id"`
	Success     bool                   `json:"success"`
	Data        map[string]interface{} `json:"data,omitempty"`
	Error       string                 `json:"error,omitempty"`
	Duration    time.Duration          `json:"duration"`
	Timestamp   time.Time              `json:"timestamp"`
}
