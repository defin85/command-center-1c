// Package odata provides types and constants for OData operations.
// Used by Worker drivers and legacy Redis Streams-based adapters.
package odata

import (
	"errors"
	"strings"
	"time"
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

// ODataCommand represents a command for stream-based OData execution (legacy).
// Commands are published to Redis Streams by Worker and consumed by an adapter.
type ODataCommand struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// CommandType specifies the operation: query, create, update, delete, batch
	CommandType string `json:"command_type"`

	// Credentials contains OData endpoint credentials
	Credentials ODataCredentials `json:"credentials"`

	// Entity is the OData entity name (e.g., "Catalog_Контрагенты")
	Entity string `json:"entity,omitempty"`

	// EntityID is the unique identifier of the entity for update/delete operations
	EntityID string `json:"entity_id,omitempty"`

	// Query contains query parameters for query operations
	Query *QueryParams `json:"query,omitempty"`

	// Data contains entity data for create/update operations
	Data map[string]interface{} `json:"data,omitempty"`

	// BatchItems contains items for batch operations
	BatchItems []BatchItem `json:"batch_items,omitempty"`

	// TimeoutSeconds specifies the operation timeout (0 = default)
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`

	// CreatedAt is the timestamp when command was created
	CreatedAt time.Time `json:"created_at"`
}

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

// ODataResult represents the result of an OData command execution.
// Results are published to Redis Streams by odata-adapter and consumed by Worker.
type ODataResult struct {
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

	// ErrorCode contains the error code for categorization
	ErrorCode string `json:"error_code,omitempty"`

	// Data contains the result data (query results, created entity, etc.)
	Data interface{} `json:"data,omitempty"`

	// AffectedCount is the number of affected records (for batch operations)
	AffectedCount int `json:"affected_count,omitempty"`

	// Duration is how long the command took to execute
	Duration time.Duration `json:"duration"`

	// CompletedAt is the timestamp when command completed
	CompletedAt time.Time `json:"completed_at"`
}

// Validate checks if the command has all required fields and valid command type.
func (c *ODataCommand) Validate() error {
	if c.OperationID == "" {
		return ErrEmptyOperationID
	}
	if c.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if c.CommandType == "" {
		return ErrEmptyCommandType
	}

	// Validate command type
	switch c.CommandType {
	case CommandTypeQuery, CommandTypeCreate, CommandTypeUpdate, CommandTypeDelete, CommandTypeBatch:
		// Valid command type
	default:
		return ErrInvalidCommandType
	}

	// Validate credentials
	if c.Credentials.BaseURL == "" {
		return ErrEmptyBaseURL
	}

	// Entity is required for non-batch operations
	if c.CommandType != CommandTypeBatch && c.Entity == "" {
		return ErrEmptyEntity
	}

	// BatchItems required for batch operations
	if c.CommandType == CommandTypeBatch && len(c.BatchItems) == 0 {
		return ErrEmptyBatchItems
	}

	return nil
}

// Validate checks if the result has all required fields.
func (r *ODataResult) Validate() error {
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

// ValidCommandTypes returns a list of all valid command types.
func ValidCommandTypes() []string {
	return []string{
		CommandTypeQuery,
		CommandTypeCreate,
		CommandTypeUpdate,
		CommandTypeDelete,
		CommandTypeBatch,
	}
}

// NewODataCommand creates a new ODataCommand with the given parameters.
func NewODataCommand(operationID, databaseID, commandType string, credentials ODataCredentials) *ODataCommand {
	return &ODataCommand{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Credentials: credentials,
		CreatedAt:   time.Now(),
	}
}

// NewODataResult creates a new successful ODataResult.
func NewODataResult(operationID, databaseID, commandType string, data interface{}, duration time.Duration) *ODataResult {
	return &ODataResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     true,
		Data:        data,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}

// NewODataErrorResult creates a new failed ODataResult.
func NewODataErrorResult(operationID, databaseID, commandType, errMsg, errorCode string, duration time.Duration) *ODataResult {
	return &ODataResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     false,
		Error:       errMsg,
		ErrorCode:   errorCode,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}
