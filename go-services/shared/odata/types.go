// Package odata provides types and constants for OData operations.
// Used by Worker drivers and OData client code.
package odata

import (
	"errors"
	"strings"
)

// Command type constants
const (
	CommandTypeQuery  = "query"
	CommandTypeCreate = "create"
	CommandTypeUpdate = "update"
	CommandTypeDelete = "delete"
	CommandTypeBatch  = "batch"
)

// Batch item operation types
const (
	BatchOperationCreate = "create"
	BatchOperationUpdate = "update"
	BatchOperationDelete = "delete"
)

// Errors for validation
var (
	// ErrEmptyOperationID indicates that the operation ID is empty
	ErrEmptyOperationID = errors.New("odata: empty operation_id")

	// ErrEmptyDatabaseID indicates that the database ID is empty
	ErrEmptyDatabaseID = errors.New("odata: empty database_id")

	// ErrEmptyEntity indicates that the entity name is empty
	ErrEmptyEntity = errors.New("odata: empty entity")

	// ErrEmptyCommandType indicates that the command type is empty
	ErrEmptyCommandType = errors.New("odata: empty command_type")

	// ErrInvalidCommandType indicates that the command type is not recognized
	ErrInvalidCommandType = errors.New("odata: invalid command_type")

	// ErrEmptyBaseURL indicates that the OData base URL is empty
	ErrEmptyBaseURL = errors.New("odata: empty base_url")

	// ErrEmptyBatchItems indicates that batch items are empty for batch command
	ErrEmptyBatchItems = errors.New("odata: empty batch_items")

	// ErrInvalidBatchOperation indicates that the batch item operation is not valid
	ErrInvalidBatchOperation = errors.New("odata: invalid batch item operation")

	// ErrMissingEntityID indicates that entity ID is required but missing
	ErrMissingEntityID = errors.New("odata: entity_id required for update/delete")

	// ErrMissingData indicates that data is required but missing
	ErrMissingData = errors.New("odata: data required for create/update")

	// ErrBatchTooLarge indicates that batch exceeds maximum size
	ErrBatchTooLarge = errors.New("odata: batch size exceeds maximum limit")

	// ErrInvalidEntityIDFormat indicates that entity_id has invalid format
	ErrInvalidEntityIDFormat = errors.New("odata: invalid entity_id format, expected guid'...'")
)


// ODataCredentials contains credentials for OData endpoint.
type ODataCredentials struct {
	// BaseURL is the OData endpoint URL (e.g., "http://server/base/odata/standard.odata")
	BaseURL string `json:"base_url"`

	// Username is the 1C user name
	Username string `json:"username"`

	// Password is the 1C user password
	Password string `json:"password"`
}

// QueryParams contains parameters for OData query operations.
type QueryParams struct {
	// Filter is the OData $filter expression
	Filter string `json:"filter,omitempty"`

	// Select is the list of fields to return ($select)
	Select []string `json:"select,omitempty"`

	// OrderBy is the OData $orderby expression
	OrderBy string `json:"orderby,omitempty"`

	// Top limits the number of returned records ($top)
	Top int `json:"top,omitempty"`

	// Skip specifies the number of records to skip ($skip)
	Skip int `json:"skip,omitempty"`

	// Expand specifies related entities to include ($expand)
	Expand string `json:"expand,omitempty"`
}

// BatchItem represents a single operation in a batch request.
type BatchItem struct {
	// Operation is the type of operation: create, update, delete
	Operation string `json:"operation"`

	// Entity is the OData entity name
	Entity string `json:"entity"`

	// EntityID is the unique identifier for update/delete operations
	EntityID string `json:"entity_id,omitempty"`

	// Data contains entity data for create/update operations
	Data map[string]interface{} `json:"data,omitempty"`
}

// ValidateEntityID checks if entityID has valid format for 1C OData (guid'...').
func ValidateEntityID(entityID string) error {
	if entityID == "" {
		return nil // Empty is allowed for create operations
	}
	if !strings.HasPrefix(entityID, "guid'") || !strings.HasSuffix(entityID, "'") {
		return ErrInvalidEntityIDFormat
	}
	return nil
}

// Validate checks if the batch item has all required fields.
func (b *BatchItem) Validate() error {
	// Validate operation type
	switch b.Operation {
	case BatchOperationCreate, BatchOperationUpdate, BatchOperationDelete:
		// Valid operation
	default:
		return ErrInvalidBatchOperation
	}

	// Entity is always required
	if b.Entity == "" {
		return ErrEmptyEntity
	}

	// EntityID required for update/delete
	if (b.Operation == BatchOperationUpdate || b.Operation == BatchOperationDelete) && b.EntityID == "" {
		return ErrMissingEntityID
	}

	// Validate EntityID format for update/delete
	if b.EntityID != "" {
		if err := ValidateEntityID(b.EntityID); err != nil {
			return err
		}
	}

	// Data required for create/update
	if (b.Operation == BatchOperationCreate || b.Operation == BatchOperationUpdate) && len(b.Data) == 0 {
		return ErrMissingData
	}

	return nil
}

// BatchResult represents the result of a batch operation.
// Contains results for each item in the batch.
type BatchResult struct {
	// TotalCount is the total number of items in the batch
	TotalCount int `json:"total_count"`

	// SuccessCount is the number of successfully processed items
	SuccessCount int `json:"success_count"`

	// FailureCount is the number of failed items
	FailureCount int `json:"failure_count"`

	// Items contains results for each batch item (in order)
	Items []BatchItemResult `json:"items"`

	// ChangesetFailed indicates if the entire changeset was rolled back
	ChangesetFailed bool `json:"changeset_failed,omitempty"`
}

// BatchItemResult represents the result of a single batch item operation.
type BatchItemResult struct {
	// Index is the position of this item in the original batch (0-based)
	Index int `json:"index"`

	// Success indicates whether this item was processed successfully
	Success bool `json:"success"`

	// Operation is the type of operation that was executed
	Operation string `json:"operation"`

	// Entity is the OData entity name
	Entity string `json:"entity"`

	// EntityID is the entity identifier (returned for create, echoed for update/delete)
	EntityID string `json:"entity_id,omitempty"`

	// Data contains the response data (created/updated entity)
	Data map[string]interface{} `json:"data,omitempty"`

	// Error contains the error message if Success is false
	Error string `json:"error,omitempty"`

	// HTTPStatus is the HTTP status code from OData response
	HTTPStatus int `json:"http_status,omitempty"`
}

// NewBatchResult creates a new BatchResult initialized with capacity.
func NewBatchResult(itemCount int) *BatchResult {
	return &BatchResult{
		TotalCount: itemCount,
		Items:      make([]BatchItemResult, 0, itemCount),
	}
}

// AddSuccess adds a successful item result to the batch.
func (br *BatchResult) AddSuccess(index int, operation, entity, entityID string, data map[string]interface{}, httpStatus int) {
	br.Items = append(br.Items, BatchItemResult{
		Index:      index,
		Success:    true,
		Operation:  operation,
		Entity:     entity,
		EntityID:   entityID,
		Data:       data,
		HTTPStatus: httpStatus,
	})
	br.SuccessCount++
}

// AddFailure adds a failed item result to the batch.
func (br *BatchResult) AddFailure(index int, operation, entity, errMsg string, httpStatus int) {
	br.Items = append(br.Items, BatchItemResult{
		Index:      index,
		Success:    false,
		Operation:  operation,
		Entity:     entity,
		Error:      errMsg,
		HTTPStatus: httpStatus,
	})
	br.FailureCount++
}

// AllSucceeded returns true if all items in the batch succeeded.
func (br *BatchResult) AllSucceeded() bool {
	return br.FailureCount == 0 && br.SuccessCount == br.TotalCount
}
