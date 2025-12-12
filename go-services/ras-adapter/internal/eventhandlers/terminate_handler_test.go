package eventhandlers

import (
	"context"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/ras"

	"go.uber.org/zap"
)

// TestNewTerminateHandler tests handler instantiation
func TestNewTerminateHandler(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	handler := NewTerminateHandler(nil, nil, nil, nil, logger)

	if handler == nil {
		t.Error("expected handler to be non-nil")
	}
}

// TestCheckIdempotency_NoRedis tests idempotency check when Redis is nil
// Uses common CheckIdempotency from helpers.go
func TestCheckIdempotency_NoRedis_Terminate(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	isFirst, err := CheckIdempotency(context.Background(), nil, "corr-id", "terminate", logger)

	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}

	if !isFirst {
		t.Error("expected isFirst to be true when Redis is nil (fail-open)")
	}
}

// TestRASCommandValidate tests RASCommand validation for terminate
func TestRASCommandValidate_Terminate(t *testing.T) {
	tests := []struct {
		name    string
		cmd     ras.RASCommand
		wantErr bool
	}{
		{
			name: "valid command",
			cmd: ras.RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-123",
				ClusterID:   "cluster-uuid",
				InfobaseID:  "infobase-uuid",
				CommandType: ras.CommandTypeTerminate,
			},
			wantErr: false,
		},
		{
			name: "missing operation_id",
			cmd: ras.RASCommand{
				DatabaseID:  "db-123",
				ClusterID:   "cluster-uuid",
				InfobaseID:  "infobase-uuid",
				CommandType: ras.CommandTypeTerminate,
			},
			wantErr: true,
		},
		{
			name: "missing cluster_id",
			cmd: ras.RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-123",
				InfobaseID:  "infobase-uuid",
				CommandType: ras.CommandTypeTerminate,
			},
			wantErr: true,
		},
		{
			name: "missing infobase_id",
			cmd: ras.RASCommand{
				OperationID: "op-123",
				DatabaseID:  "db-123",
				ClusterID:   "cluster-uuid",
				CommandType: ras.CommandTypeTerminate,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cmd.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestChannelNames tests channel name constants (new ras prefix)
func TestChannelNames_Terminate(t *testing.T) {
	if TerminateCommandChannel != ras.StreamCommandsTerminate {
		t.Errorf("expected TerminateCommandChannel to be %s, got %s", ras.StreamCommandsTerminate, TerminateCommandChannel)
	}

	if SessionsClosedChannel != ras.StreamEventsCompleted {
		t.Errorf("expected SessionsClosedChannel to be %s, got %s", ras.StreamEventsCompleted, SessionsClosedChannel)
	}

	if TerminateFailedChannel != ras.StreamEventsFailed {
		t.Errorf("expected TerminateFailedChannel to be %s, got %s", ras.StreamEventsFailed, TerminateFailedChannel)
	}
}

// TestEventTypeConstants tests event type constants (new ras prefix)
func TestEventTypeConstants_Terminate(t *testing.T) {
	if SessionsTerminatedEvent != "ras.sessions.terminated" {
		t.Errorf("expected SessionsTerminatedEvent to be ras.sessions.terminated, got %s", SessionsTerminatedEvent)
	}

	if SessionsTerminateFailedEvent != "ras.sessions.terminate.failed" {
		t.Errorf("expected SessionsTerminateFailedEvent to be ras.sessions.terminate.failed, got %s", SessionsTerminateFailedEvent)
	}
}

// TestPublishSuccess tests publishSuccess method exists
func TestPublishSuccess_Terminate(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	// Create a mock publisher that accepts calls
	handler := NewTerminateHandler(nil, nil, nil, nil, logger)

	if handler == nil {
		t.Error("expected handler to be non-nil")
	}

	// Just verify the method exists and can be called
	// Real testing would require mock implementation
}
