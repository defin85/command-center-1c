// shared/models/operation_v2_test.go
package models

import (
	"encoding/json"
	"testing"
	"time"
)

func TestOperationMessage_Validate(t *testing.T) {
	tests := []struct {
		name    string
		msg     OperationMessage
		wantErr bool
	}{
		{
			name: "valid message",
			msg: OperationMessage{
				Version:         "2.0",
				OperationID:     "test-123",
				OperationType:   "create",
				TargetDatabases: []string{"db-1"},
			},
			wantErr: false,
		},
		{
			name: "missing operation_id",
			msg: OperationMessage{
				Version:       "2.0",
				OperationType: "create",
			},
			wantErr: true,
		},
		{
			name: "invalid version",
			msg: OperationMessage{
				Version:         "1.0",
				OperationID:     "test-123",
				OperationType:   "create",
				TargetDatabases: []string{"db-1"},
			},
			wantErr: true,
		},
		{
			name: "missing operation_type",
			msg: OperationMessage{
				Version:         "2.0",
				OperationID:     "test-123",
				TargetDatabases: []string{"db-1"},
			},
			wantErr: true,
		},
		{
			name: "empty target_databases",
			msg: OperationMessage{
				Version:         "2.0",
				OperationID:     "test-123",
				OperationType:   "create",
				TargetDatabases: []string{},
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.msg.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestOperationMessage_JSONSerialization(t *testing.T) {
	msg := OperationMessage{
		Version:         "2.0",
		OperationID:     "test-123",
		OperationType:   "create",
		Entity:          "Catalog_Users",
		TargetDatabases: []string{"db-1", "db-2"},
		Payload: OperationPayload{
			Data: map[string]interface{}{
				"Name": "Test User",
			},
		},
		Metadata: MessageMetadata{
			CreatedBy: "user-123",
			CreatedAt: time.Now(),
		},
	}

	// Marshal
	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("failed to marshal: %v", err)
	}

	// Unmarshal
	var decoded OperationMessage
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}

	if decoded.OperationID != msg.OperationID {
		t.Errorf("OperationID mismatch: got %s, want %s", decoded.OperationID, msg.OperationID)
	}
}

func TestOperationResultV2_JSONSerialization(t *testing.T) {
	result := OperationResultV2{
		OperationID: "test-123",
		Status:      "completed",
		Results: []DatabaseResultV2{
			{
				DatabaseID: "db-1",
				Success:    true,
				Data: map[string]interface{}{
					"created": true,
				},
				Duration: 2.5,
			},
		},
		Summary: ResultSummary{
			Total:       1,
			Succeeded:   1,
			Failed:      0,
			AvgDuration: 2.5,
		},
		Timestamp: time.Now(),
		WorkerID:  "worker-1",
	}

	// Marshal
	data, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("failed to marshal: %v", err)
	}

	// Unmarshal
	var decoded OperationResultV2
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}

	if decoded.OperationID != result.OperationID {
		t.Errorf("OperationID mismatch: got %s, want %s", decoded.OperationID, result.OperationID)
	}

	if decoded.Status != result.Status {
		t.Errorf("Status mismatch: got %s, want %s", decoded.Status, result.Status)
	}

	if len(decoded.Results) != len(result.Results) {
		t.Errorf("Results count mismatch: got %d, want %d", len(decoded.Results), len(result.Results))
	}
}
