package workflows

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
	"github.com/commandcenter1c/commandcenter/worker/internal/saga"
)

// OData workflow errors.
var (
	ErrMissingDatabaseID      = errors.New("database_id is required")
	ErrMissingODataCredentials = errors.New("odata_credentials is required")
	ErrMissingOperations      = errors.New("operations is required")
	ErrBatchFailed            = errors.New("batch operation failed")
)

// ODataBatchInput defines input parameters for OData batch workflow.
type ODataBatchInput struct {
	// DatabaseID is the internal CommandCenter database ID.
	DatabaseID string `json:"database_id"`

	// Credentials contains OData endpoint credentials.
	Credentials ODataCredentials `json:"odata_credentials"`

	// Operations is the list of batch operations to execute.
	Operations []ODataOperation `json:"operations"`

	// SavePreviousValues indicates whether to save previous values for compensation.
	// If true, update operations will first query the current values.
	SavePreviousValues bool `json:"save_previous_values"`
}

// ODataOperation represents a single operation in the batch.
type ODataOperation struct {
	// Operation is the type: create, update, delete.
	Operation string `json:"operation"`

	// Entity is the OData entity name.
	Entity string `json:"entity"`

	// EntityID is the unique identifier for update/delete operations.
	EntityID string `json:"entity_id,omitempty"`

	// Data contains entity data for create/update operations.
	Data map[string]interface{} `json:"data,omitempty"`

	// Select specifies which fields to query for compensation (update only).
	Select []string `json:"select,omitempty"`
}

// BatchCompensationData stores data needed for compensation.
type BatchCompensationData struct {
	// CreatedEntityIDs stores entity_id for created records (to delete on rollback).
	CreatedEntityIDs []CreatedEntity `json:"created_entity_ids"`

	// PreviousValues stores original values for updated records (to restore on rollback).
	PreviousValues []PreviousValue `json:"previous_values"`

	// DeletedRecords stores deleted records (cannot be restored, just logged).
	DeletedRecords []DeletedRecord `json:"deleted_records"`
}

// CreatedEntity stores information about a created entity for compensation.
type CreatedEntity struct {
	Index    int    `json:"index"`
	Entity   string `json:"entity"`
	EntityID string `json:"entity_id"`
}

// PreviousValue stores the previous value of an updated entity.
type PreviousValue struct {
	Index    int                    `json:"index"`
	Entity   string                 `json:"entity"`
	EntityID string                 `json:"entity_id"`
	Data     map[string]interface{} `json:"data"`
}

// DeletedRecord stores information about a deleted record (for logging).
type DeletedRecord struct {
	Index    int    `json:"index"`
	Entity   string `json:"entity"`
	EntityID string `json:"entity_id"`
}

// NewODataBatchWorkflow creates a saga for OData batch operations.
//
// Input variables:
//   - database_id: string - internal database ID
//   - odata_credentials: map - {base_url, username, password}
//   - operations: []map - list of {operation, entity, entity_id, data}
//   - save_previous_values: bool - whether to save values for compensation
//
// Steps:
// 1. acquire_lock - acquire distributed lock on the database
// 2. save_previous_values - (optional) query current values for updates
// 3. execute_batch - execute the batch operation
// 4. release_lock - release the distributed lock
//
// Compensation:
//   - For create operations: delete the created records
//   - For update operations: restore previous values (if saved)
//   - For delete operations: cannot restore (logged as warning)
func NewODataBatchWorkflow(
	rm resourcemanager.ResourceManager,
	deps *WorkflowDependencies,
) *saga.SagaDefinition {
	return &saga.SagaDefinition{
		ID:             WorkflowODataBatch,
		Name:           "OData Batch",
		Description:    "Executes OData batch operations (create/update/delete) with compensation support",
		DefaultTimeout: deps.Config.DefaultStepTimeout,
		Steps: []*saga.Step{
			{
				ID:         "acquire_lock",
				Name:       "Acquire Database Lock",
				Execute:    acquireSingleLockStep(rm, deps),
				Compensate: releaseSingleLockCompensation(rm),
				Timeout:    2 * time.Minute,
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 500 * time.Millisecond,
					MaxBackoff:     5 * time.Second,
					BackoffFactor:  2.0,
				},
				Idempotent: true,
			},
			{
				ID:         "save_previous_values",
				Name:       "Save Previous Values",
				Execute:    savePreviousValuesStep(deps),
				Timeout:    deps.Config.DefaultStepTimeout,
				Idempotent: true,
			},
			{
				ID:         "execute_batch",
				Name:       "Execute Batch Operations",
				Execute:    executeBatchStep(deps),
				Compensate: compensateBatchStep(deps),
				Timeout:    10 * time.Minute, // Batch can take time
				RetryPolicy: &saga.RetryPolicy{
					MaxRetries:     1,
					InitialBackoff: 2 * time.Second,
					MaxBackoff:     10 * time.Second,
					BackoffFactor:  2.0,
				},
			},
			{
				ID:         "release_lock",
				Name:       "Release Database Lock",
				Execute:    releaseSingleLockStep(rm),
				Timeout:    1 * time.Minute,
				Idempotent: true,
			},
		},
	}
}

// acquireSingleLockStep acquires a lock on a single database.
func acquireSingleLockStep(rm resourcemanager.ResourceManager, deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		databaseID := sagaCtx.GetString("database_id")
		if databaseID == "" {
			return ErrMissingDatabaseID
		}

		req := &resourcemanager.LockRequest{
			DatabaseID:    databaseID,
			OwnerID:       sagaCtx.ExecutionID,
			Operation:     sagaCtx.SagaID,
			CorrelationID: sagaCtx.CorrelationID,
			TTL:           deps.Config.LockTTL,
			WaitTimeout:   2 * time.Minute,
		}

		result, err := rm.AcquireLock(ctx, req)
		if err != nil {
			return fmt.Errorf("failed to acquire lock for database %s: %w", databaseID, err)
		}

		if !result.Acquired {
			return fmt.Errorf("could not acquire lock for database %s: lock held by %s",
				databaseID, result.LockInfo.OwnerID)
		}

		sagaCtx.Set("lock_acquired", true)
		sagaCtx.DatabaseIDs = []string{databaseID}

		return nil
	}
}

// releaseSingleLockCompensation releases the lock in compensation.
func releaseSingleLockCompensation(rm resourcemanager.ResourceManager) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		if !sagaCtx.GetBool("lock_acquired") {
			return nil
		}

		databaseID := sagaCtx.GetString("database_id")
		if databaseID == "" {
			return nil
		}

		return rm.ReleaseLock(ctx, databaseID, sagaCtx.ExecutionID)
	}
}

// releaseSingleLockStep releases the lock at the end of workflow.
func releaseSingleLockStep(rm resourcemanager.ResourceManager) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		databaseID := sagaCtx.GetString("database_id")
		if databaseID == "" {
			return nil
		}

		err := rm.ReleaseLock(ctx, databaseID, sagaCtx.ExecutionID)
		if err != nil {
			// Log but don't fail - lock will expire anyway
			return nil
		}

		sagaCtx.Set("lock_acquired", false)
		return nil
	}
}

// savePreviousValuesStep queries and saves current values for update operations.
func savePreviousValuesStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		// Check if we should save previous values
		savePrevious := sagaCtx.GetBool("save_previous_values")
		if !savePrevious {
			return nil
		}

		creds := getODataCredentials(sagaCtx)
		operations := getODataOperations(sagaCtx)

		previousValues := make([]PreviousValue, 0)

		for i, op := range operations {
			if op.Operation != odata.BatchOperationUpdate || op.EntityID == "" {
				continue
			}

			// Build query to get current value
			query := &odata.QueryParams{
				Select: op.Select,
			}

			// Query single entity by ID
			// For 1C OData, the URL would be Entity(guid'...')
			results, err := deps.ODataClient.Query(ctx, creds, op.Entity+"("+op.EntityID+")", query)
			if err != nil {
				// If we can't get current value, log warning but continue
				continue
			}

			if len(results) > 0 {
				previousValues = append(previousValues, PreviousValue{
					Index:    i,
					Entity:   op.Entity,
					EntityID: op.EntityID,
					Data:     results[0],
				})
			}
		}

		// Store for compensation
		sagaCtx.Set("previous_values", previousValues)

		return nil
	}
}

// executeBatchStep executes the batch operations.
func executeBatchStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		creds := getODataCredentials(sagaCtx)
		operations := getODataOperations(sagaCtx)

		if len(operations) == 0 {
			return ErrMissingOperations
		}

		// Convert to odata.BatchItem
		batchItems := make([]odata.BatchItem, len(operations))
		for i, op := range operations {
			batchItems[i] = odata.BatchItem{
				Operation: op.Operation,
				Entity:    op.Entity,
				EntityID:  op.EntityID,
				Data:      op.Data,
			}
		}

		// Execute batch
		result, err := deps.ODataClient.ExecuteBatch(ctx, creds, batchItems)
		if err != nil {
			return fmt.Errorf("batch execution failed: %w", err)
		}

		// Store compensation data
		compData := BatchCompensationData{
			CreatedEntityIDs: make([]CreatedEntity, 0),
			PreviousValues:   make([]PreviousValue, 0),
			DeletedRecords:   make([]DeletedRecord, 0),
		}

		// Extract created entity IDs for compensation
		for _, item := range result.Items {
			if item.Success {
				switch operations[item.Index].Operation {
				case odata.BatchOperationCreate:
					if item.EntityID != "" {
						compData.CreatedEntityIDs = append(compData.CreatedEntityIDs, CreatedEntity{
							Index:    item.Index,
							Entity:   item.Entity,
							EntityID: item.EntityID,
						})
					}
				case odata.BatchOperationDelete:
					compData.DeletedRecords = append(compData.DeletedRecords, DeletedRecord{
						Index:    item.Index,
						Entity:   item.Entity,
						EntityID: operations[item.Index].EntityID,
					})
				}
			}
		}

		// Copy previous values from context
		if prevRaw, ok := sagaCtx.Get("previous_values"); ok {
			if prev, ok := prevRaw.([]PreviousValue); ok {
				compData.PreviousValues = prev
			}
		}

		// Store compensation data
		sagaCtx.Set("compensation_data", compData)
		sagaCtx.Set("batch_result", result)

		// Check if batch was successful
		if result.ChangesetFailed || result.FailureCount > 0 {
			// Return error to trigger compensation
			return fmt.Errorf("%w: %d/%d operations failed", ErrBatchFailed, result.FailureCount, result.TotalCount)
		}

		return nil
	}
}

// compensateBatchStep compensates for batch operations.
func compensateBatchStep(deps *WorkflowDependencies) saga.StepFunc {
	return func(ctx context.Context, sagaCtx *saga.SagaContext) error {
		creds := getODataCredentials(sagaCtx)

		compDataRaw, ok := sagaCtx.Get("compensation_data")
		if !ok {
			return nil // Nothing to compensate
		}

		compData, ok := compDataRaw.(BatchCompensationData)
		if !ok {
			// Try to parse from JSON
			if jsonBytes, err := json.Marshal(compDataRaw); err == nil {
				json.Unmarshal(jsonBytes, &compData)
			}
		}

		var lastErr error

		// 1. Delete created records
		for _, created := range compData.CreatedEntityIDs {
			if err := deps.ODataClient.Delete(ctx, creds, created.Entity, created.EntityID); err != nil {
				lastErr = err
				// Continue with other compensations
			}
		}

		// 2. Restore previous values for updates
		for _, prev := range compData.PreviousValues {
			if err := deps.ODataClient.Update(ctx, creds, prev.Entity, prev.EntityID, prev.Data); err != nil {
				lastErr = err
				// Continue with other compensations
			}
		}

		// 3. Log deleted records (cannot restore)
		if len(compData.DeletedRecords) > 0 {
			// Store warning in context for reporting
			sagaCtx.Set("compensation_warnings", fmt.Sprintf(
				"WARNING: %d deleted records cannot be restored",
				len(compData.DeletedRecords),
			))
		}

		return lastErr
	}
}

// Helper functions

func getODataCredentials(sagaCtx *saga.SagaContext) ODataCredentials {
	credsRaw, _ := sagaCtx.Get("odata_credentials")
	creds := ODataCredentials{}

	switch v := credsRaw.(type) {
	case ODataCredentials:
		return v
	case map[string]interface{}:
		if baseURL, ok := v["base_url"].(string); ok {
			creds.BaseURL = baseURL
		}
		if username, ok := v["username"].(string); ok {
			creds.Username = username
		}
		if password, ok := v["password"].(string); ok {
			creds.Password = password
		}
	case string:
		// Try to parse as JSON
		json.Unmarshal([]byte(v), &creds)
	}

	return creds
}

func getODataOperations(sagaCtx *saga.SagaContext) []ODataOperation {
	opsRaw, _ := sagaCtx.Get("operations")
	operations := make([]ODataOperation, 0)

	switch v := opsRaw.(type) {
	case []ODataOperation:
		return v
	case []interface{}:
		for _, item := range v {
			op := ODataOperation{}
			if m, ok := item.(map[string]interface{}); ok {
				if operation, ok := m["operation"].(string); ok {
					op.Operation = operation
				}
				if entity, ok := m["entity"].(string); ok {
					op.Entity = entity
				}
				if entityID, ok := m["entity_id"].(string); ok {
					op.EntityID = entityID
				}
				if data, ok := m["data"].(map[string]interface{}); ok {
					op.Data = data
				}
				if selectFields, ok := m["select"].([]interface{}); ok {
					op.Select = make([]string, len(selectFields))
					for i, f := range selectFields {
						if s, ok := f.(string); ok {
							op.Select[i] = s
						}
					}
				}
				operations = append(operations, op)
			}
		}
	case string:
		// Try to parse as JSON
		json.Unmarshal([]byte(v), &operations)
	}

	return operations
}
