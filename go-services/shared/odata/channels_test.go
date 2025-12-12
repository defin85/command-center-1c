package odata

import (
	"errors"
	"testing"
)

func TestGetCommandStream(t *testing.T) {
	tests := []struct {
		name        string
		commandType string
		wantStream  string
		wantErr     bool
	}{
		{
			name:        "query command",
			commandType: CommandTypeQuery,
			wantStream:  StreamCommandsQuery,
			wantErr:     false,
		},
		{
			name:        "create command",
			commandType: CommandTypeCreate,
			wantStream:  StreamCommandsCreate,
			wantErr:     false,
		},
		{
			name:        "update command",
			commandType: CommandTypeUpdate,
			wantStream:  StreamCommandsUpdate,
			wantErr:     false,
		},
		{
			name:        "delete command",
			commandType: CommandTypeDelete,
			wantStream:  StreamCommandsDelete,
			wantErr:     false,
		},
		{
			name:        "batch command",
			commandType: CommandTypeBatch,
			wantStream:  StreamCommandsBatch,
			wantErr:     false,
		},
		{
			name:        "invalid command type",
			commandType: "invalid",
			wantStream:  "",
			wantErr:     true,
		},
		{
			name:        "empty command type",
			commandType: "",
			wantStream:  "",
			wantErr:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stream, err := GetCommandStream(tt.commandType)
			if (err != nil) != tt.wantErr {
				t.Errorf("GetCommandStream() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if stream != tt.wantStream {
				t.Errorf("GetCommandStream() = %v, want %v", stream, tt.wantStream)
			}
			if tt.wantErr && !errors.Is(err, ErrInvalidCommandType) {
				t.Errorf("GetCommandStream() error should wrap ErrInvalidCommandType")
			}
		})
	}
}

func TestMustGetCommandStream(t *testing.T) {
	// Test valid command type
	stream := MustGetCommandStream(CommandTypeQuery)
	if stream != StreamCommandsQuery {
		t.Errorf("MustGetCommandStream(query) = %v, want %v", stream, StreamCommandsQuery)
	}

	// Test panic on invalid command type
	defer func() {
		if r := recover(); r == nil {
			t.Error("MustGetCommandStream should panic on invalid command type")
		}
	}()
	MustGetCommandStream("invalid")
}

func TestAllCommandStreams(t *testing.T) {
	streams := AllCommandStreams()
	expected := []string{
		StreamCommandsQuery,
		StreamCommandsCreate,
		StreamCommandsUpdate,
		StreamCommandsDelete,
		StreamCommandsBatch,
	}

	if len(streams) != len(expected) {
		t.Errorf("AllCommandStreams() returned %d streams, want %d", len(streams), len(expected))
	}

	for i, s := range expected {
		if streams[i] != s {
			t.Errorf("AllCommandStreams()[%d] = %v, want %v", i, streams[i], s)
		}
	}
}

func TestAllEventStreams(t *testing.T) {
	streams := AllEventStreams()
	expected := []string{
		StreamEventsCompleted,
		StreamEventsFailed,
	}

	if len(streams) != len(expected) {
		t.Errorf("AllEventStreams() returned %d streams, want %d", len(streams), len(expected))
	}

	for i, s := range expected {
		if streams[i] != s {
			t.Errorf("AllEventStreams()[%d] = %v, want %v", i, streams[i], s)
		}
	}
}

func TestConsumerGroupConstants(t *testing.T) {
	if ConsumerGroupOData == "" {
		t.Error("ConsumerGroupOData should not be empty")
	}
	if ConsumerGroupWorker == "" {
		t.Error("ConsumerGroupWorker should not be empty")
	}
	if ConsumerGroupOData == ConsumerGroupWorker {
		t.Error("ConsumerGroupOData and ConsumerGroupWorker should be different")
	}
}

func TestStreamConstants(t *testing.T) {
	// Verify stream naming convention
	commandStreams := AllCommandStreams()
	for _, s := range commandStreams {
		if len(s) < 15 { // "commands:odata:" = 15 chars
			t.Errorf("Stream %s should start with 'commands:odata:'", s)
		}
	}

	eventStreams := AllEventStreams()
	for _, s := range eventStreams {
		if len(s) < 13 { // "events:odata:" = 13 chars
			t.Errorf("Stream %s should start with 'events:odata:'", s)
		}
	}
}
