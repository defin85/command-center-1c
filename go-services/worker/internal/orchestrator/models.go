// Package orchestrator provides HTTP client for communicating with Django Orchestrator Internal API.
package orchestrator

import "time"

// ============================================================================
// Error Types
// ============================================================================

// APIError represents a structured error from Orchestrator API.
type APIError struct {
	Error     string `json:"error"`
	Code      string `json:"code"`
	Details   string `json:"details,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

// ============================================================================
// Scheduler Schemas
// ============================================================================

// SchedulerJobRunStartRequest represents request to start a scheduler job run.
type SchedulerJobRunStartRequest struct {
	JobName        string                 `json:"job_name"`
	WorkerInstance string                 `json:"worker_instance"`
	JobConfig      map[string]interface{} `json:"job_config,omitempty"`
}

// SchedulerJobRunCompleteRequest represents request to complete a scheduler job run.
type SchedulerJobRunCompleteRequest struct {
	Status         string `json:"status"` // success, failed, skipped
	DurationMs     int64  `json:"duration_ms,omitempty"`
	ResultSummary  string `json:"result_summary,omitempty"`
	ErrorMessage   string `json:"error_message,omitempty"`
	ItemsProcessed int    `json:"items_processed,omitempty"`
	ItemsFailed    int    `json:"items_failed,omitempty"`
}

// SchedulerJobRunResponse represents response from scheduler job run endpoints.
type SchedulerJobRunResponse struct {
	Success bool   `json:"success,omitempty"`
	RunID   int    `json:"run_id"`
	Status  string `json:"status"` // running, success, failed, skipped
}

// ============================================================================
// Task Execution Schemas
// ============================================================================

// TaskExecutionStartRequest represents request to start a task execution.
type TaskExecutionStartRequest struct {
	OperationID    string                 `json:"operation_id"`
	TaskType       string                 `json:"task_type"`
	TargetID       string                 `json:"target_id"`
	TargetType     string                 `json:"target_type,omitempty"` // database, cluster, infobase
	WorkerInstance string                 `json:"worker_instance,omitempty"`
	Parameters     map[string]interface{} `json:"parameters,omitempty"`
}

// TaskExecutionCompleteRequest represents request to complete a task execution.
type TaskExecutionCompleteRequest struct {
	Status       string                 `json:"status"` // success, failed, skipped
	DurationMs   int64                  `json:"duration_ms,omitempty"`
	Result       map[string]interface{} `json:"result,omitempty"`
	ErrorMessage string                 `json:"error_message,omitempty"`
	ErrorCode    string                 `json:"error_code,omitempty"`
	RetryCount   int                    `json:"retry_count,omitempty"`
}

// TaskExecutionResponse represents response from task execution endpoints.
type TaskExecutionResponse struct {
	Success bool   `json:"success,omitempty"`
	TaskID  int    `json:"task_id"`
	Status  string `json:"status"` // running, success, failed, skipped
}

// DatabaseForHealthCheck represents a database entry for health monitoring.
type DatabaseForHealthCheck struct {
	ID       string `json:"id"`
	ODataURL string `json:"odata_url"`
	Name     string `json:"name"`
}

// DatabasesForHealthCheckResponse represents response from databases health check list endpoint.
type DatabasesForHealthCheckResponse struct {
	Success   bool                     `json:"success"`
	Databases []DatabaseForHealthCheck `json:"databases"`
	Count     int                      `json:"count"`
}

// ============================================================================
// Health Update Schemas
// ============================================================================

// HealthUpdateRequest represents request to update health status.
type HealthUpdateRequest struct {
	Healthy        bool                   `json:"healthy"`
	ErrorMessage   string                 `json:"error_message,omitempty"`
	ErrorCode      string                 `json:"error_code,omitempty"`
	LastCheckAt    *time.Time             `json:"last_check_at,omitempty"`
	ResponseTimeMs int                    `json:"response_time_ms,omitempty"`
	Details        map[string]interface{} `json:"details,omitempty"`
}

// HealthUpdateResponse represents response from health update endpoints.
type HealthUpdateResponse struct {
	Success    bool   `json:"success"`
	DatabaseID string `json:"database_id,omitempty"`
	ClusterID  string `json:"cluster_id,omitempty"`
	Healthy    bool   `json:"healthy"`
}

// =============================================================================
// Runtime Settings Schemas
// =============================================================================

// RuntimeSetting represents a runtime-configurable setting.
type RuntimeSetting struct {
	Key         string      `json:"key"`
	Value       interface{} `json:"value"`
	ValueType   string      `json:"value_type"`
	Description string      `json:"description,omitempty"`
	MinValue    *int        `json:"min_value,omitempty"`
	MaxValue    *int        `json:"max_value,omitempty"`
	Default     interface{} `json:"default,omitempty"`
}

// RuntimeSettingsResponse represents response from runtime settings endpoint.
type RuntimeSettingsResponse struct {
	Success  bool             `json:"success,omitempty"`
	Settings []RuntimeSetting `json:"settings"`
}

// ============================================================================
// Template Schemas (Sprint 2.2)
// ============================================================================

// TemplateStep represents a single step in a template.
type TemplateStep struct {
	StepID     string                 `json:"step_id"`
	Action     string                 `json:"action"`
	Parameters map[string]interface{} `json:"parameters,omitempty"`
	Condition  string                 `json:"condition,omitempty"`
	OnError    string                 `json:"on_error,omitempty"` // fail, skip, continue, rollback
	Retry      *RetryConfig           `json:"retry,omitempty"`
}

// RetryConfig represents retry configuration for a step.
type RetryConfig struct {
	MaxAttempts int `json:"max_attempts"`
	DelayMs     int `json:"delay_ms"`
}

// TemplateResponse represents a template definition.
type TemplateResponse struct {
	TemplateID       string                 `json:"template_id"`
	Code             string                 `json:"code"`
	Name             string                 `json:"name"`
	Description      string                 `json:"description,omitempty"`
	Version          string                 `json:"version"`
	ParametersSchema map[string]interface{} `json:"parameters_schema,omitempty"`
	Steps            []TemplateStep         `json:"steps"`
	RollbackSteps    []TemplateStep         `json:"rollback_steps,omitempty"`
	TimeoutSeconds   int                    `json:"timeout_seconds,omitempty"`
}

// ============================================================================
// Workflow Schemas (Sprint 3.x)
// ============================================================================

// WorkflowNode represents a node in workflow graph.
type WorkflowNode struct {
	NodeID         string `json:"node_id"`
	Type           string `json:"type"` // start, end, action, condition, parallel, wait
	TemplateID     string `json:"template_id,omitempty"`
	Condition      string `json:"condition,omitempty"`
	TimeoutSeconds int    `json:"timeout_seconds,omitempty"`
}

// WorkflowEdge represents an edge in workflow graph.
type WorkflowEdge struct {
	FromNode  string `json:"from_node"`
	ToNode    string `json:"to_node"`
	Condition string `json:"condition,omitempty"`
}

// WorkflowResponse represents a workflow definition.
type WorkflowResponse struct {
	WorkflowID       string                 `json:"workflow_id"`
	Code             string                 `json:"code"`
	Name             string                 `json:"name"`
	Description      string                 `json:"description,omitempty"`
	Version          string                 `json:"version"`
	ParametersSchema map[string]interface{} `json:"parameters_schema,omitempty"`
	Nodes            []WorkflowNode         `json:"nodes"`
	Edges            []WorkflowEdge         `json:"edges,omitempty"`
	TimeoutSeconds   int                    `json:"timeout_seconds,omitempty"`
}

// PoolRuntimeOperationRef preserves operation binding provenance in bridge payload.
type PoolRuntimeOperationRef struct {
	Alias                    string `json:"alias"`
	BindingMode              string `json:"binding_mode,omitempty"`
	TemplateExposureID       string `json:"template_exposure_id,omitempty"`
	TemplateExposureRevision int    `json:"template_exposure_revision,omitempty"`
}

// PoolRuntimePublicationAuth carries publication credentials provenance for pool publication step.
type PoolRuntimePublicationAuth struct {
	Strategy      string `json:"strategy,omitempty"`
	ActorUsername string `json:"actor_username,omitempty"`
	Source        string `json:"source,omitempty"`
}

// PoolRuntimeStepExecutionRequest represents request to pool runtime bridge endpoint.
type PoolRuntimeStepExecutionRequest struct {
	TenantID            string                      `json:"tenant_id"`
	PoolRunID           string                      `json:"pool_run_id"`
	WorkflowExecutionID string                      `json:"workflow_execution_id"`
	NodeID              string                      `json:"node_id"`
	OperationType       string                      `json:"operation_type"`
	OperationRef        *PoolRuntimeOperationRef    `json:"operation_ref,omitempty"`
	StepAttempt         int                         `json:"step_attempt"`
	TransportAttempt    int                         `json:"transport_attempt"`
	IdempotencyKey      string                      `json:"idempotency_key"`
	PublicationAuth     *PoolRuntimePublicationAuth `json:"publication_auth,omitempty"`
	Payload             map[string]interface{}      `json:"payload"`
}

// SetTransportAttempt updates transport attempt for retries in orchestrator HTTP client.
func (r *PoolRuntimeStepExecutionRequest) SetTransportAttempt(attempt int) {
	if r == nil {
		return
	}
	if attempt > 0 {
		r.TransportAttempt = attempt
	}
}

// PoolRuntimeStepExecutionResponse represents response from pool runtime bridge endpoint.
type PoolRuntimeStepExecutionResponse struct {
	Success        bool                   `json:"success"`
	Status         string                 `json:"status,omitempty"`
	ErrorCode      string                 `json:"error_code,omitempty"`
	ErrorMessage   string                 `json:"error_message,omitempty"`
	Result         map[string]interface{} `json:"result,omitempty"`
	ErrorDetails   map[string]interface{} `json:"error_details,omitempty"`
	IdempotencyKey string                 `json:"idempotency_key,omitempty"`
}

// ============================================================================
// Failed Events Schemas (Event Replay System)
// ============================================================================

// FailedEvent represents a failed event awaiting replay.
type FailedEvent struct {
	ID                int                    `json:"id"`
	Channel           string                 `json:"channel"`
	EventType         string                 `json:"event_type"`
	CorrelationID     string                 `json:"correlation_id"`
	Payload           map[string]interface{} `json:"payload"`
	SourceService     string                 `json:"source_service"`
	OriginalTimestamp time.Time              `json:"original_timestamp"`
	Status            string                 `json:"status"` // pending, replayed, failed
	RetryCount        int                    `json:"retry_count"`
	MaxRetries        int                    `json:"max_retries"`
	LastError         string                 `json:"last_error,omitempty"`
	CreatedAt         time.Time              `json:"created_at"`
}

// FailedEventsPendingResponse represents response from pending events endpoint.
type FailedEventsPendingResponse struct {
	Success bool          `json:"success"`
	Events  []FailedEvent `json:"events"`
	Count   int           `json:"count"`
}

// FailedEventReplayedRequest represents request to mark event as replayed.
type FailedEventReplayedRequest struct {
	ReplayedAt *time.Time `json:"replayed_at,omitempty"`
}

// FailedEventFailedRequest represents request to mark event as failed.
type FailedEventFailedRequest struct {
	ErrorMessage   string `json:"error_message"`
	IncrementRetry *bool  `json:"increment_retry,omitempty"` // defaults to true
}

// FailedEventFailedResponse represents response from mark failed endpoint.
type FailedEventFailedResponse struct {
	Success    bool   `json:"success"`
	NewStatus  string `json:"new_status"` // pending or failed
	RetryCount int    `json:"retry_count"`
}

// FailedEventsCleanupRequest represents request for cleanup endpoint.
type FailedEventsCleanupRequest struct {
	RetentionDays int `json:"retention_days,omitempty"` // 1-365, default 7
}

// FailedEventsCleanupResponse represents response from cleanup endpoint.
type FailedEventsCleanupResponse struct {
	Success      bool `json:"success"`
	DeletedCount int  `json:"deleted_count"`
}

// FailedEventReplayedResponse represents response from mark replayed endpoint.
type FailedEventReplayedResponse struct {
	Success bool   `json:"success"`
	EventID int    `json:"event_id"`
	Status  string `json:"status"` // replayed
}

// ============================================================================
// Template Response Schemas
// ============================================================================

// TemplateGetResponse represents response from template endpoint.
type TemplateGetResponse struct {
	Success  bool                  `json:"success"`
	Template OperationTemplateData `json:"template"`
}

// OperationTemplateData represents template data from API.
type OperationTemplateData struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	OperationType string                 `json:"operation_type"`
	TargetEntity  string                 `json:"target_entity"`
	TemplateData  map[string]interface{} `json:"template_data"`
	Version       int                    `json:"version"`
	IsActive      bool                   `json:"is_active"`
}

// ============================================================================
// Common Schemas
// ============================================================================

// SuccessResponse represents a generic success response.
type SuccessResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}
