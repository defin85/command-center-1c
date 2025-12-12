package odata

import (
	"testing"
	"time"
)

func TestODataCommand_Validate(t *testing.T) {
	validCreds := ODataCredentials{
		BaseURL:  "http://server/base/odata/standard.odata",
		Username: "admin",
		Password: "secret",
	}

	tests := []struct {
		name    string
		command ODataCommand
		wantErr error
	}{
		{
			name: "valid query command",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Credentials: validCreds,
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: nil,
		},
		{
			name: "valid batch command",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeBatch,
				Credentials: validCreds,
				BatchItems: []BatchItem{
					{Operation: "create", Entity: "Catalog_Контрагенты", Data: map[string]interface{}{"name": "Test"}},
				},
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			command: ODataCommand{
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Credentials: validCreds,
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			command: ODataCommand{
				OperationID: "op-123",
				CommandType: CommandTypeQuery,
				Credentials: validCreds,
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				Credentials: validCreds,
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: ErrEmptyCommandType,
		},
		{
			name: "invalid command_type",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: "invalid",
				Credentials: validCreds,
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: ErrInvalidCommandType,
		},
		{
			name: "empty base_url",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Credentials: ODataCredentials{Username: "admin"},
				Entity:      "Catalog_Контрагенты",
			},
			wantErr: ErrEmptyBaseURL,
		},
		{
			name: "empty entity for query",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Credentials: validCreds,
			},
			wantErr: ErrEmptyEntity,
		},
		{
			name: "empty batch_items for batch",
			command: ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeBatch,
				Credentials: validCreds,
			},
			wantErr: ErrEmptyBatchItems,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.command.Validate()
			if err != tt.wantErr {
				t.Errorf("ODataCommand.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestODataResult_Validate(t *testing.T) {
	tests := []struct {
		name    string
		result  ODataResult
		wantErr error
	}{
		{
			name: "valid result",
			result: ODataResult{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Success:     true,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			result: ODataResult{
				DatabaseID:  "db-456",
				CommandType: CommandTypeQuery,
				Success:     true,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			result: ODataResult{
				OperationID: "op-123",
				CommandType: CommandTypeQuery,
				Success:     true,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			result: ODataResult{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				Success:     true,
			},
			wantErr: ErrEmptyCommandType,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.result.Validate()
			if err != tt.wantErr {
				t.Errorf("ODataResult.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestNewODataCommand(t *testing.T) {
	creds := ODataCredentials{
		BaseURL:  "http://server/base/odata/standard.odata",
		Username: "admin",
		Password: "secret",
	}
	cmd := NewODataCommand("op-123", "db-456", CommandTypeQuery, creds)

	if cmd.OperationID != "op-123" {
		t.Errorf("OperationID = %v, want op-123", cmd.OperationID)
	}
	if cmd.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %v, want db-456", cmd.DatabaseID)
	}
	if cmd.CommandType != CommandTypeQuery {
		t.Errorf("CommandType = %v, want %v", cmd.CommandType, CommandTypeQuery)
	}
	if cmd.Credentials.BaseURL != creds.BaseURL {
		t.Errorf("Credentials.BaseURL = %v, want %v", cmd.Credentials.BaseURL, creds.BaseURL)
	}
	if cmd.CreatedAt.IsZero() {
		t.Error("CreatedAt should not be zero")
	}
}

func TestNewODataResult(t *testing.T) {
	data := map[string]interface{}{"count": 5}
	result := NewODataResult("op-123", "db-456", CommandTypeQuery, data, 100*time.Millisecond)

	if result.OperationID != "op-123" {
		t.Errorf("OperationID = %v, want op-123", result.OperationID)
	}
	if !result.Success {
		t.Error("Success should be true")
	}
	if result.Error != "" {
		t.Errorf("Error should be empty, got %v", result.Error)
	}
	if result.Duration != 100*time.Millisecond {
		t.Errorf("Duration = %v, want 100ms", result.Duration)
	}
	if result.CompletedAt.IsZero() {
		t.Error("CompletedAt should not be zero")
	}
}

func TestNewODataErrorResult(t *testing.T) {
	result := NewODataErrorResult("op-123", "db-456", CommandTypeQuery, "connection failed", "CONN_ERR", 50*time.Millisecond)

	if result.OperationID != "op-123" {
		t.Errorf("OperationID = %v, want op-123", result.OperationID)
	}
	if result.Success {
		t.Error("Success should be false")
	}
	if result.Error != "connection failed" {
		t.Errorf("Error = %v, want 'connection failed'", result.Error)
	}
	if result.ErrorCode != "CONN_ERR" {
		t.Errorf("ErrorCode = %v, want 'CONN_ERR'", result.ErrorCode)
	}
	if result.Duration != 50*time.Millisecond {
		t.Errorf("Duration = %v, want 50ms", result.Duration)
	}
}

func TestValidCommandTypes(t *testing.T) {
	types := ValidCommandTypes()
	expected := []string{
		CommandTypeQuery,
		CommandTypeCreate,
		CommandTypeUpdate,
		CommandTypeDelete,
		CommandTypeBatch,
	}

	if len(types) != len(expected) {
		t.Errorf("ValidCommandTypes() returned %d types, want %d", len(types), len(expected))
	}

	for i, ct := range expected {
		if types[i] != ct {
			t.Errorf("ValidCommandTypes()[%d] = %v, want %v", i, types[i], ct)
		}
	}
}

func TestODataCommand_AllCommandTypes(t *testing.T) {
	validCreds := ODataCredentials{
		BaseURL:  "http://server/base/odata/standard.odata",
		Username: "admin",
		Password: "secret",
	}

	commandTypes := []string{
		CommandTypeQuery,
		CommandTypeCreate,
		CommandTypeUpdate,
		CommandTypeDelete,
	}

	for _, ct := range commandTypes {
		t.Run(ct, func(t *testing.T) {
			cmd := ODataCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: ct,
				Credentials: validCreds,
				Entity:      "Catalog_Test",
			}
			if err := cmd.Validate(); err != nil {
				t.Errorf("Valid %s command should not return error: %v", ct, err)
			}
		})
	}
}

func TestBatchItem_Validate(t *testing.T) {
	tests := []struct {
		name    string
		item    BatchItem
		wantErr error
	}{
		{
			name: "valid create item",
			item: BatchItem{
				Operation: BatchOperationCreate,
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"name": "Test User"},
			},
			wantErr: nil,
		},
		{
			name: "valid update item",
			item: BatchItem{
				Operation: BatchOperationUpdate,
				Entity:    "Catalog_Users",
				EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
				Data:      map[string]interface{}{"name": "Updated User"},
			},
			wantErr: nil,
		},
		{
			name: "valid delete item",
			item: BatchItem{
				Operation: BatchOperationDelete,
				Entity:    "Catalog_Users",
				EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
			},
			wantErr: nil,
		},
		{
			name: "invalid operation type",
			item: BatchItem{
				Operation: "invalid",
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"name": "Test"},
			},
			wantErr: ErrInvalidBatchOperation,
		},
		{
			name: "empty entity",
			item: BatchItem{
				Operation: BatchOperationCreate,
				Entity:    "",
				Data:      map[string]interface{}{"name": "Test"},
			},
			wantErr: ErrEmptyEntity,
		},
		{
			name: "missing entityID for update",
			item: BatchItem{
				Operation: BatchOperationUpdate,
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"name": "Test"},
			},
			wantErr: ErrMissingEntityID,
		},
		{
			name: "missing entityID for delete",
			item: BatchItem{
				Operation: BatchOperationDelete,
				Entity:    "Catalog_Users",
			},
			wantErr: ErrMissingEntityID,
		},
		{
			name: "missing data for create",
			item: BatchItem{
				Operation: BatchOperationCreate,
				Entity:    "Catalog_Users",
			},
			wantErr: ErrMissingData,
		},
		{
			name: "missing data for update",
			item: BatchItem{
				Operation: BatchOperationUpdate,
				Entity:    "Catalog_Users",
				EntityID:  "guid'12345678-1234-1234-1234-123456789012'",
			},
			wantErr: ErrMissingData,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.item.Validate()
			if err != tt.wantErr {
				t.Errorf("BatchItem.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestNewBatchResult(t *testing.T) {
	itemCount := 5
	result := NewBatchResult(itemCount)

	if result.TotalCount != itemCount {
		t.Errorf("TotalCount = %d, want %d", result.TotalCount, itemCount)
	}
	if result.SuccessCount != 0 {
		t.Errorf("SuccessCount = %d, want 0", result.SuccessCount)
	}
	if result.FailureCount != 0 {
		t.Errorf("FailureCount = %d, want 0", result.FailureCount)
	}
	if len(result.Items) != 0 {
		t.Errorf("Items length = %d, want 0", len(result.Items))
	}
	if cap(result.Items) != itemCount {
		t.Errorf("Items capacity = %d, want %d", cap(result.Items), itemCount)
	}
}

func TestBatchResult_AddSuccess(t *testing.T) {
	result := NewBatchResult(3)
	data := map[string]interface{}{"Ref_Key": "12345678-1234-1234-1234-123456789012"}

	result.AddSuccess(0, BatchOperationCreate, "Catalog_Users", "guid'12345678-1234-1234-1234-123456789012'", data, 201)

	if result.SuccessCount != 1 {
		t.Errorf("SuccessCount = %d, want 1", result.SuccessCount)
	}
	if result.FailureCount != 0 {
		t.Errorf("FailureCount = %d, want 0", result.FailureCount)
	}
	if len(result.Items) != 1 {
		t.Fatalf("Items length = %d, want 1", len(result.Items))
	}

	item := result.Items[0]
	if item.Index != 0 {
		t.Errorf("Index = %d, want 0", item.Index)
	}
	if !item.Success {
		t.Error("Success should be true")
	}
	if item.Operation != BatchOperationCreate {
		t.Errorf("Operation = %s, want %s", item.Operation, BatchOperationCreate)
	}
	if item.Entity != "Catalog_Users" {
		t.Errorf("Entity = %s, want Catalog_Users", item.Entity)
	}
	if item.EntityID != "guid'12345678-1234-1234-1234-123456789012'" {
		t.Errorf("EntityID = %s, want guid'12345678-1234-1234-1234-123456789012'", item.EntityID)
	}
	if item.HTTPStatus != 201 {
		t.Errorf("HTTPStatus = %d, want 201", item.HTTPStatus)
	}
	if item.Error != "" {
		t.Errorf("Error should be empty, got %s", item.Error)
	}
}

func TestBatchResult_AddFailure(t *testing.T) {
	result := NewBatchResult(3)

	result.AddFailure(1, BatchOperationUpdate, "Catalog_Users", "entity not found", 404)

	if result.SuccessCount != 0 {
		t.Errorf("SuccessCount = %d, want 0", result.SuccessCount)
	}
	if result.FailureCount != 1 {
		t.Errorf("FailureCount = %d, want 1", result.FailureCount)
	}
	if len(result.Items) != 1 {
		t.Fatalf("Items length = %d, want 1", len(result.Items))
	}

	item := result.Items[0]
	if item.Index != 1 {
		t.Errorf("Index = %d, want 1", item.Index)
	}
	if item.Success {
		t.Error("Success should be false")
	}
	if item.Operation != BatchOperationUpdate {
		t.Errorf("Operation = %s, want %s", item.Operation, BatchOperationUpdate)
	}
	if item.Entity != "Catalog_Users" {
		t.Errorf("Entity = %s, want Catalog_Users", item.Entity)
	}
	if item.Error != "entity not found" {
		t.Errorf("Error = %s, want 'entity not found'", item.Error)
	}
	if item.HTTPStatus != 404 {
		t.Errorf("HTTPStatus = %d, want 404", item.HTTPStatus)
	}
}

func TestBatchResult_AllSucceeded(t *testing.T) {
	tests := []struct {
		name string
		setup func() *BatchResult
		want bool
	}{
		{
			name: "all succeeded",
			setup: func() *BatchResult {
				result := NewBatchResult(2)
				result.AddSuccess(0, BatchOperationCreate, "Catalog_Users", "guid'1'", nil, 201)
				result.AddSuccess(1, BatchOperationUpdate, "Catalog_Users", "guid'2'", nil, 200)
				return result
			},
			want: true,
		},
		{
			name: "one failure",
			setup: func() *BatchResult {
				result := NewBatchResult(2)
				result.AddSuccess(0, BatchOperationCreate, "Catalog_Users", "guid'1'", nil, 201)
				result.AddFailure(1, BatchOperationUpdate, "Catalog_Users", "error", 404)
				return result
			},
			want: false,
		},
		{
			name: "all failed",
			setup: func() *BatchResult {
				result := NewBatchResult(2)
				result.AddFailure(0, BatchOperationCreate, "Catalog_Users", "error", 400)
				result.AddFailure(1, BatchOperationUpdate, "Catalog_Users", "error", 404)
				return result
			},
			want: false,
		},
		{
			name: "empty batch",
			setup: func() *BatchResult {
				return NewBatchResult(0)
			},
			want: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tt.setup()
			got := result.AllSucceeded()
			if got != tt.want {
				t.Errorf("AllSucceeded() = %v, want %v (SuccessCount=%d, FailureCount=%d, TotalCount=%d)",
					got, tt.want, result.SuccessCount, result.FailureCount, result.TotalCount)
			}
		})
	}
}
