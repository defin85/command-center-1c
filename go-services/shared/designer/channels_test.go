package designer

import (
	"strings"
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
			name:        "extension-install",
			commandType: CommandTypeExtensionInstall,
			wantStream:  StreamCommandsExtensionInstall,
			wantErr:     false,
		},
		{
			name:        "extension-remove",
			commandType: CommandTypeExtensionRemove,
			wantStream:  StreamCommandsExtensionRemove,
			wantErr:     false,
		},
		{
			name:        "config-update",
			commandType: CommandTypeConfigUpdate,
			wantStream:  StreamCommandsConfigUpdate,
			wantErr:     false,
		},
		{
			name:        "config-load",
			commandType: CommandTypeConfigLoad,
			wantStream:  StreamCommandsConfigLoad,
			wantErr:     false,
		},
		{
			name:        "config-dump",
			commandType: CommandTypeConfigDump,
			wantStream:  StreamCommandsConfigDump,
			wantErr:     false,
		},
		{
			name:        "epf-export",
			commandType: CommandTypeEpfExport,
			wantStream:  StreamCommandsEpfExport,
			wantErr:     false,
		},
		{
			name:        "epf-import",
			commandType: CommandTypeEpfImport,
			wantStream:  StreamCommandsEpfImport,
			wantErr:     false,
		},
		{
			name:        "metadata-export",
			commandType: CommandTypeMetadataExport,
			wantStream:  StreamCommandsMetadataExport,
			wantErr:     false,
		},
		{
			name:        "invalid command type",
			commandType: "unknown-command",
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
			if tt.wantErr && err != nil {
				if !strings.Contains(err.Error(), "invalid command_type") {
					t.Errorf("Error should contain 'invalid command_type', got %v", err)
				}
			}
		})
	}
}

func TestMustGetCommandStream(t *testing.T) {
	// Test valid command types
	validTypes := []struct {
		commandType string
		wantStream  string
	}{
		{CommandTypeExtensionInstall, StreamCommandsExtensionInstall},
		{CommandTypeExtensionRemove, StreamCommandsExtensionRemove},
		{CommandTypeConfigUpdate, StreamCommandsConfigUpdate},
		{CommandTypeConfigLoad, StreamCommandsConfigLoad},
		{CommandTypeConfigDump, StreamCommandsConfigDump},
		{CommandTypeEpfExport, StreamCommandsEpfExport},
		{CommandTypeEpfImport, StreamCommandsEpfImport},
		{CommandTypeMetadataExport, StreamCommandsMetadataExport},
	}

	for _, tt := range validTypes {
		t.Run(tt.commandType, func(t *testing.T) {
			stream := MustGetCommandStream(tt.commandType)
			if stream != tt.wantStream {
				t.Errorf("MustGetCommandStream() = %v, want %v", stream, tt.wantStream)
			}
		})
	}

	// Test panic on invalid command type
	t.Run("panics on invalid", func(t *testing.T) {
		defer func() {
			if r := recover(); r == nil {
				t.Error("MustGetCommandStream() should panic on invalid command type")
			}
		}()
		MustGetCommandStream("invalid-command")
	})
}

func TestAllCommandStreams(t *testing.T) {
	streams := AllCommandStreams()

	expected := []string{
		StreamCommandsExtensionInstall,
		StreamCommandsExtensionRemove,
		StreamCommandsConfigUpdate,
		StreamCommandsConfigLoad,
		StreamCommandsConfigDump,
		StreamCommandsEpfExport,
		StreamCommandsEpfImport,
		StreamCommandsMetadataExport,
	}

	if len(streams) != len(expected) {
		t.Errorf("AllCommandStreams() returned %d streams, expected %d", len(streams), len(expected))
	}

	for i, stream := range streams {
		if stream != expected[i] {
			t.Errorf("AllCommandStreams()[%d] = %s, expected %s", i, stream, expected[i])
		}
	}

	// Verify all streams start with "commands:designer:"
	for _, stream := range streams {
		if !strings.HasPrefix(stream, "commands:designer:") {
			t.Errorf("Stream %s should start with 'commands:designer:'", stream)
		}
	}
}

func TestAllEventStreams(t *testing.T) {
	streams := AllEventStreams()

	expected := []string{
		StreamEventsCompleted,
		StreamEventsFailed,
		StreamEventsProgress,
	}

	if len(streams) != len(expected) {
		t.Errorf("AllEventStreams() returned %d streams, expected %d", len(streams), len(expected))
	}

	for i, stream := range streams {
		if stream != expected[i] {
			t.Errorf("AllEventStreams()[%d] = %s, expected %s", i, stream, expected[i])
		}
	}

	// Verify all streams start with "events:designer:"
	for _, stream := range streams {
		if !strings.HasPrefix(stream, "events:designer:") {
			t.Errorf("Stream %s should start with 'events:designer:'", stream)
		}
	}
}

func TestStreamConstants(t *testing.T) {
	// Verify command stream names
	commandStreams := map[string]string{
		"StreamCommandsExtensionInstall": StreamCommandsExtensionInstall,
		"StreamCommandsExtensionRemove":  StreamCommandsExtensionRemove,
		"StreamCommandsConfigUpdate":     StreamCommandsConfigUpdate,
		"StreamCommandsConfigLoad":       StreamCommandsConfigLoad,
		"StreamCommandsConfigDump":       StreamCommandsConfigDump,
		"StreamCommandsEpfExport":        StreamCommandsEpfExport,
		"StreamCommandsEpfImport":        StreamCommandsEpfImport,
		"StreamCommandsMetadataExport":   StreamCommandsMetadataExport,
	}

	for name, stream := range commandStreams {
		if stream == "" {
			t.Errorf("%s should not be empty", name)
		}
		if !strings.HasPrefix(stream, "commands:designer:") {
			t.Errorf("%s = %s, should start with 'commands:designer:'", name, stream)
		}
	}

	// Verify event stream names
	eventStreams := map[string]string{
		"StreamEventsCompleted": StreamEventsCompleted,
		"StreamEventsFailed":    StreamEventsFailed,
		"StreamEventsProgress":  StreamEventsProgress,
	}

	for name, stream := range eventStreams {
		if stream == "" {
			t.Errorf("%s should not be empty", name)
		}
		if !strings.HasPrefix(stream, "events:designer:") {
			t.Errorf("%s = %s, should start with 'events:designer:'", name, stream)
		}
	}
}

func TestConsumerGroupConstants(t *testing.T) {
	if ConsumerGroupDesigner == "" {
		t.Error("ConsumerGroupDesigner should not be empty")
	}
	if ConsumerGroupDesigner != "designer-agent-group" {
		t.Errorf("ConsumerGroupDesigner = %s, expected 'designer-agent-group'", ConsumerGroupDesigner)
	}

	if ConsumerGroupWorker == "" {
		t.Error("ConsumerGroupWorker should not be empty")
	}
	if ConsumerGroupWorker != "worker-designer-results-group" {
		t.Errorf("ConsumerGroupWorker = %s, expected 'worker-designer-results-group'", ConsumerGroupWorker)
	}
}

func TestCommandStreamMapCompleteness(t *testing.T) {
	// Verify that all command types have corresponding streams
	commandTypes := ValidCommandTypes()

	for _, cmdType := range commandTypes {
		stream, err := GetCommandStream(cmdType)
		if err != nil {
			t.Errorf("Command type %s has no corresponding stream: %v", cmdType, err)
		}
		if stream == "" {
			t.Errorf("Stream for command type %s should not be empty", cmdType)
		}
	}
}
