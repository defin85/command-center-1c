// Package ras provides types and constants for RAS (Remote Administration Server) operations.
// Used for communication between Worker and ras-adapter via Redis Streams.
package ras

import (
	"errors"
	"time"
)

// Command type constants
const (
	CommandTypeLock      = "lock"
	CommandTypeUnlock    = "unlock"
	CommandTypeBlock     = "block"
	CommandTypeUnblock   = "unblock"
	CommandTypeTerminate = "terminate"
)

// Errors for validation
var (
	// ErrEmptyOperationID indicates that the operation ID is empty
	ErrEmptyOperationID = errors.New("empty operation_id")

	// ErrEmptyDatabaseID indicates that the database ID is empty
	ErrEmptyDatabaseID = errors.New("empty database_id")

	// ErrEmptyClusterID indicates that the cluster ID is empty
	ErrEmptyClusterID = errors.New("empty cluster_id")

	// ErrEmptyInfobaseID indicates that the infobase ID is empty
	ErrEmptyInfobaseID = errors.New("empty infobase_id")

	// ErrEmptyCommandType indicates that the command type is empty
	ErrEmptyCommandType = errors.New("empty command_type")

	// ErrInvalidCommandType indicates that the command type is not recognized
	ErrInvalidCommandType = errors.New("invalid command_type")
)

// RASCommand represents a command to be executed by ras-adapter.
// Commands are published to Redis Streams by Worker and consumed by ras-adapter.
type RASCommand struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// ClusterID is the 1C RAS cluster UUID
	ClusterID string `json:"cluster_id"`

	// InfobaseID is the 1C RAS infobase UUID
	InfobaseID string `json:"infobase_id"`

	// CommandType specifies the operation: lock, unlock, block, unblock, terminate
	CommandType string `json:"command_type"`

	// Options contains command-specific parameters
	Options map[string]interface{} `json:"options,omitempty"`

	// CreatedAt is the timestamp when command was created
	CreatedAt time.Time `json:"created_at"`
}

// Validate checks if the command has all required fields and valid command type.
func (c *RASCommand) Validate() error {
	if c.OperationID == "" {
		return ErrEmptyOperationID
	}
	if c.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if c.ClusterID == "" {
		return ErrEmptyClusterID
	}
	if c.InfobaseID == "" {
		return ErrEmptyInfobaseID
	}
	if c.CommandType == "" {
		return ErrEmptyCommandType
	}

	// Validate command type
	switch c.CommandType {
	case CommandTypeLock, CommandTypeUnlock, CommandTypeBlock, CommandTypeUnblock, CommandTypeTerminate:
		// Valid command type
	default:
		return ErrInvalidCommandType
	}

	return nil
}

// ValidCommandTypes returns a list of all valid command types.
func ValidCommandTypes() []string {
	return []string{
		CommandTypeLock,
		CommandTypeUnlock,
		CommandTypeBlock,
		CommandTypeUnblock,
		CommandTypeTerminate,
	}
}

// RASResult represents the result of a RAS command execution.
// Results are published to Redis Streams by ras-adapter and consumed by Worker.
type RASResult struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// CommandType is the type of command that was executed
	CommandType string `json:"command_type"`

	// Success indicates whether the command completed successfully
	Success bool `json:"success"`

	// Error contains the error message if Success is false
	Error string `json:"error,omitempty"`

	// Data contains additional result data (e.g., session count, lock details)
	Data interface{} `json:"data,omitempty"`

	// Duration is how long the command took to execute
	Duration time.Duration `json:"duration"`

	// CompletedAt is the timestamp when command completed
	CompletedAt time.Time `json:"completed_at"`
}

// Validate checks if the result has all required fields.
func (r *RASResult) Validate() error {
	if r.OperationID == "" {
		return ErrEmptyOperationID
	}
	if r.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if r.CommandType == "" {
		return ErrEmptyCommandType
	}
	return nil
}

// NewRASCommand creates a new RASCommand with the given parameters.
func NewRASCommand(operationID, databaseID, clusterID, infobaseID, commandType string) *RASCommand {
	return &RASCommand{
		OperationID: operationID,
		DatabaseID:  databaseID,
		ClusterID:   clusterID,
		InfobaseID:  infobaseID,
		CommandType: commandType,
		CreatedAt:   time.Now(),
	}
}

// NewRASResult creates a new successful RASResult.
func NewRASResult(operationID, databaseID, commandType string, data interface{}, duration time.Duration) *RASResult {
	return &RASResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     true,
		Data:        data,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}

// NewRASErrorResult creates a new failed RASResult.
func NewRASErrorResult(operationID, databaseID, commandType, errMsg string, duration time.Duration) *RASResult {
	return &RASResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     false,
		Error:       errMsg,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}
