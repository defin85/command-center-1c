package ras

import (
	"testing"
	"time"
)

func TestRASCommand_Validate(t *testing.T) {
	tests := []struct {
		name    string
		command RASCommand
		wantErr error
	}{
		{
			name: "valid command",
			command: RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				ClusterID:   "cluster-789",
				InfobaseID:  "ib-012",
				CommandType: CommandTypeLock,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			command: RASCommand{
				DatabaseID:  "db-456",
				ClusterID:   "cluster-789",
				InfobaseID:  "ib-012",
				CommandType: CommandTypeLock,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			command: RASCommand{
				OperationID: "op-123",
				ClusterID:   "cluster-789",
				InfobaseID:  "ib-012",
				CommandType: CommandTypeLock,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty cluster_id",
			command: RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				InfobaseID:  "ib-012",
				CommandType: CommandTypeLock,
			},
			wantErr: ErrEmptyClusterID,
		},
		{
			name: "empty infobase_id",
			command: RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				ClusterID:   "cluster-789",
				CommandType: CommandTypeLock,
			},
			wantErr: ErrEmptyInfobaseID,
		},
		{
			name: "empty command_type",
			command: RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				ClusterID:   "cluster-789",
				InfobaseID:  "ib-012",
			},
			wantErr: ErrEmptyCommandType,
		},
		{
			name: "invalid command_type",
			command: RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				ClusterID:   "cluster-789",
				InfobaseID:  "ib-012",
				CommandType: "invalid",
			},
			wantErr: ErrInvalidCommandType,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.command.Validate()
			if err != tt.wantErr {
				t.Errorf("RASCommand.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestRASResult_Validate(t *testing.T) {
	tests := []struct {
		name    string
		result  RASResult
		wantErr error
	}{
		{
			name: "valid result",
			result: RASResult{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeLock,
				Success:     true,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			result: RASResult{
				DatabaseID:  "db-456",
				CommandType: CommandTypeLock,
				Success:     true,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			result: RASResult{
				OperationID: "op-123",
				CommandType: CommandTypeLock,
				Success:     true,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			result: RASResult{
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
				t.Errorf("RASResult.Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestNewRASCommand(t *testing.T) {
	cmd := NewRASCommand("op-123", "db-456", "cluster-789", "ib-012", CommandTypeLock)

	if cmd.OperationID != "op-123" {
		t.Errorf("OperationID = %v, want op-123", cmd.OperationID)
	}
	if cmd.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %v, want db-456", cmd.DatabaseID)
	}
	if cmd.ClusterID != "cluster-789" {
		t.Errorf("ClusterID = %v, want cluster-789", cmd.ClusterID)
	}
	if cmd.InfobaseID != "ib-012" {
		t.Errorf("InfobaseID = %v, want ib-012", cmd.InfobaseID)
	}
	if cmd.CommandType != CommandTypeLock {
		t.Errorf("CommandType = %v, want %v", cmd.CommandType, CommandTypeLock)
	}
	if cmd.CreatedAt.IsZero() {
		t.Error("CreatedAt should not be zero")
	}
}

func TestNewRASResult(t *testing.T) {
	data := map[string]interface{}{"sessions": 5}
	result := NewRASResult("op-123", "db-456", CommandTypeLock, data, 100*time.Millisecond)

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
}

func TestNewRASErrorResult(t *testing.T) {
	result := NewRASErrorResult("op-123", "db-456", CommandTypeLock, "connection failed", 50*time.Millisecond)

	if result.OperationID != "op-123" {
		t.Errorf("OperationID = %v, want op-123", result.OperationID)
	}
	if result.Success {
		t.Error("Success should be false")
	}
	if result.Error != "connection failed" {
		t.Errorf("Error = %v, want 'connection failed'", result.Error)
	}
}

func TestValidCommandTypes(t *testing.T) {
	types := ValidCommandTypes()
	expected := []string{CommandTypeLock, CommandTypeUnlock, CommandTypeBlock, CommandTypeUnblock, CommandTypeTerminate}

	if len(types) != len(expected) {
		t.Errorf("ValidCommandTypes() returned %d types, want %d", len(types), len(expected))
	}

	for i, ct := range expected {
		if types[i] != ct {
			t.Errorf("ValidCommandTypes()[%d] = %v, want %v", i, types[i], ct)
		}
	}
}
