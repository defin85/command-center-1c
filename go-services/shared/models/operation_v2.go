// go-services/shared/models/operation_v2.go
package models

import (
	"fmt"
	"strings"
	"time"
)

// ========== Message Protocol v2.0 Structs ==========

// TargetDatabase represents a target database for operation
type TargetDatabase struct {
	ID            string `json:"id"`
	Name          string `json:"name,omitempty"`
	ClusterID     string `json:"cluster_id,omitempty"`
	RASInfobaseID string `json:"ras_infobase_id,omitempty"`
}

// OperationMessage v2.0 - Full protocol specification
type OperationMessage struct {
	Version       string `json:"version"`
	OperationID   string `json:"operation_id"`
	BatchID       string `json:"batch_id,omitempty"`
	OperationType string `json:"operation_type"`
	Entity        string `json:"entity"`

	TargetDatabases []TargetDatabase `json:"target_databases"`

	Payload    OperationPayload `json:"payload"`
	ExecConfig ExecutionConfig  `json:"execution_config"`
	Metadata   MessageMetadata  `json:"metadata"`
}

// GetTargetDatabaseIDs returns slice of database IDs
func (om *OperationMessage) GetTargetDatabaseIDs() []string {
	ids := make([]string, len(om.TargetDatabases))
	for i, db := range om.TargetDatabases {
		ids[i] = db.ID
	}
	return ids
}

type OperationPayload struct {
	Data    map[string]interface{} `json:"data"`
	Filters map[string]interface{} `json:"filters,omitempty"`
	Options map[string]interface{} `json:"options,omitempty"`
}

type ExecutionConfig struct {
	BatchSize      int    `json:"batch_size"`
	TimeoutSeconds int    `json:"timeout_seconds"`
	RetryCount     int    `json:"retry_count"`
	Priority       string `json:"priority"`
	IdempotencyKey string `json:"idempotency_key"`
}

type MessageMetadata struct {
	CreatedBy                string    `json:"created_by"`
	CreatedAt                time.Time `json:"created_at"`
	TemplateID               string    `json:"template_id,omitempty"`
	TemplateExposureID       string    `json:"template_exposure_id,omitempty"`
	TemplateExposureRevision int       `json:"template_exposure_revision,omitempty"`
	Tags                     []string  `json:"tags,omitempty"`
	WorkflowExecutionID      string    `json:"workflow_execution_id,omitempty"`
	NodeID                   string    `json:"node_id,omitempty"`
	RootOperationID          string    `json:"root_operation_id,omitempty"`
	ExecutionConsumer        string    `json:"execution_consumer,omitempty"`
	Lane                     string    `json:"lane,omitempty"`
	TraceID                  string    `json:"trace_id,omitempty"`
}

// OperationResultV2 - Worker response to Orchestrator (v2.0)
type OperationResultV2 struct {
	OperationID string `json:"operation_id"`
	Status      string `json:"status"` // completed|failed|timeout

	Results []DatabaseResultV2 `json:"results"`

	Summary ResultSummary `json:"summary"`

	Timestamp time.Time `json:"timestamp"`
	WorkerID  string    `json:"worker_id"`
}

type DatabaseResultV2 struct {
	DatabaseID string                 `json:"database_id"`
	Success    bool                   `json:"success"`
	Data       map[string]interface{} `json:"data,omitempty"`
	Error      string                 `json:"error,omitempty"`
	ErrorCode  string                 `json:"error_code,omitempty"`
	Duration   float64                `json:"duration_seconds"`
}

type ResultSummary struct {
	Total       int     `json:"total"`
	Succeeded   int     `json:"succeeded"`
	Failed      int     `json:"failed"`
	AvgDuration float64 `json:"avg_duration_seconds"`
}

// ========== Validation ==========

// Operation types that don't require target_databases
// These are meta-operations or workflow executions that determine targets internally.
var metaOperationTypes = map[string]bool{
	"sync_cluster":      true,
	"discover_clusters": true,
	"execute_workflow":  true,
	// Future: "health_check_cluster", "backup_cluster", etc.
}

// IsMetaOperation checks if operation type is a meta-operation
func IsMetaOperation(opType string) bool {
	return metaOperationTypes[opType]
}

// Validate validates the OperationMessage
func (om *OperationMessage) Validate() error {
	if om.Version != "2.0" {
		return fmt.Errorf("invalid version: %s (expected 2.0)", om.Version)
	}

	if om.OperationID == "" {
		return fmt.Errorf("operation_id is required")
	}

	if om.OperationType == "" {
		return fmt.Errorf("operation_type is required")
	}

	// Meta-operations (sync_cluster, etc.) don't require target_databases
	targetScope := ""
	if om.Payload.Options != nil {
		if rawScope, ok := om.Payload.Options["target_scope"]; ok {
			if rawScopeStr, ok := rawScope.(string); ok {
				targetScope = strings.ToLower(strings.TrimSpace(rawScopeStr))
			}
		}
	}

	if !IsMetaOperation(om.OperationType) && len(om.TargetDatabases) == 0 && targetScope != "global" {
		return fmt.Errorf("target_databases cannot be empty")
	}

	// Validate each target has ID
	for i, db := range om.TargetDatabases {
		if db.ID == "" {
			return fmt.Errorf("target_databases[%d].id cannot be empty", i)
		}
	}

	return nil
}
