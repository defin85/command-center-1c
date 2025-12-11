package ras

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
			name:        "lock command",
			commandType: CommandTypeLock,
			wantStream:  StreamCommandsLock,
			wantErr:     false,
		},
		{
			name:        "unlock command",
			commandType: CommandTypeUnlock,
			wantStream:  StreamCommandsUnlock,
			wantErr:     false,
		},
		{
			name:        "block command",
			commandType: CommandTypeBlock,
			wantStream:  StreamCommandsBlock,
			wantErr:     false,
		},
		{
			name:        "unblock command",
			commandType: CommandTypeUnblock,
			wantStream:  StreamCommandsUnblock,
			wantErr:     false,
		},
		{
			name:        "terminate command",
			commandType: CommandTypeTerminate,
			wantStream:  StreamCommandsTerminate,
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
	stream := MustGetCommandStream(CommandTypeLock)
	if stream != StreamCommandsLock {
		t.Errorf("MustGetCommandStream(lock) = %v, want %v", stream, StreamCommandsLock)
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
		StreamCommandsLock,
		StreamCommandsUnlock,
		StreamCommandsBlock,
		StreamCommandsUnblock,
		StreamCommandsTerminate,
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
	if ConsumerGroupRAS == "" {
		t.Error("ConsumerGroupRAS should not be empty")
	}
	if ConsumerGroupWorker == "" {
		t.Error("ConsumerGroupWorker should not be empty")
	}
	if ConsumerGroupRAS == ConsumerGroupWorker {
		t.Error("ConsumerGroupRAS and ConsumerGroupWorker should be different")
	}
}
