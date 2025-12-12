package designer

import (
	"testing"
	"time"
)

func TestDesignerCommand_Validate(t *testing.T) {
	validSSH := SSHCredentials{
		Host: "server.example.com",
		Port: 22,
		User: "admin",
	}
	validParams := CommandParams{
		InfobasePath:  "/opt/1c/bases/test",
		ExtensionName: "MyExtension",
		SourcePath:    "/tmp/source.cfe",
		TargetPath:    "/tmp/export",
	}

	tests := []struct {
		name    string
		cmd     DesignerCommand
		wantErr error
	}{
		{
			name: "valid extension-install command",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH:         validSSH,
				Params:      validParams,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			cmd: DesignerCommand{
				OperationID: "",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH:         validSSH,
				Params:      validParams,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "",
				CommandType: CommandTypeExtensionInstall,
				SSH:         validSSH,
				Params:      validParams,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: "",
				SSH:         validSSH,
				Params:      validParams,
			},
			wantErr: ErrEmptyCommandType,
		},
		{
			name: "invalid command_type",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: "unknown-command",
				SSH:         validSSH,
				Params:      validParams,
			},
			wantErr: ErrInvalidCommandType,
		},
		{
			name: "empty ssh host",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH: SSHCredentials{
					Host: "",
					Port: 22,
					User: "admin",
				},
				Params: validParams,
			},
			wantErr: ErrEmptySSHHost,
		},
		{
			name: "empty ssh user",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH: SSHCredentials{
					Host: "server.example.com",
					Port: 22,
					User: "",
				},
				Params: validParams,
			},
			wantErr: ErrEmptySSHUser,
		},
		{
			name: "invalid ssh port",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH: SSHCredentials{
					Host: "server.example.com",
					Port: 70000,
					User: "admin",
				},
				Params: validParams,
			},
			wantErr: ErrInvalidSSHPort,
		},
		{
			name: "empty infobase_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath:  "",
					ExtensionName: "MyExtension",
				},
			},
			wantErr: ErrEmptyInfobasePath,
		},
		{
			name: "extension-install without extension_name",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath:  "/opt/1c/bases/test",
					ExtensionName: "",
				},
			},
			wantErr: ErrEmptyExtensionName,
		},
		{
			name: "extension-remove without extension_name",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionRemove,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath:  "/opt/1c/bases/test",
					ExtensionName: "",
				},
			},
			wantErr: ErrEmptyExtensionName,
		},
		{
			name: "config-load without source_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeConfigLoad,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					SourcePath:   "",
				},
			},
			wantErr: ErrEmptySourcePath,
		},
		{
			name: "epf-import without source_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeEpfImport,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					SourcePath:   "",
				},
			},
			wantErr: ErrEmptySourcePath,
		},
		{
			name: "config-dump without target_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeConfigDump,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					TargetPath:   "",
				},
			},
			wantErr: ErrEmptyTargetPath,
		},
		{
			name: "epf-export without target_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeEpfExport,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					TargetPath:   "",
				},
			},
			wantErr: ErrEmptyTargetPath,
		},
		{
			name: "metadata-export without target_path",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeMetadataExport,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					TargetPath:   "",
				},
			},
			wantErr: ErrEmptyTargetPath,
		},
		{
			name: "valid config-update command",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeConfigUpdate,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
				},
			},
			wantErr: nil,
		},
		{
			name: "valid config-dump command",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeConfigDump,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					TargetPath:   "/tmp/dump",
				},
			},
			wantErr: nil,
		},
		{
			name: "valid config-load command",
			cmd: DesignerCommand{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeConfigLoad,
				SSH:         validSSH,
				Params: CommandParams{
					InfobasePath: "/opt/1c/bases/test",
					SourcePath:   "/tmp/config.cf",
				},
			},
			wantErr: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.cmd.Validate()
			if err != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestDesignerResult_Validate(t *testing.T) {
	tests := []struct {
		name    string
		result  DesignerResult
		wantErr error
	}{
		{
			name: "valid result",
			result: DesignerResult{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Success:     true,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			result: DesignerResult{
				OperationID: "",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			result: DesignerResult{
				OperationID: "op-123",
				DatabaseID:  "",
				CommandType: CommandTypeExtensionInstall,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			result: DesignerResult{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: "",
			},
			wantErr: ErrEmptyCommandType,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.result.Validate()
			if err != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestDesignerProgress_Validate(t *testing.T) {
	tests := []struct {
		name     string
		progress DesignerProgress
		wantErr  error
	}{
		{
			name: "valid progress",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusInProgress,
				Percentage:  50,
			},
			wantErr: nil,
		},
		{
			name: "empty operation_id",
			progress: DesignerProgress{
				OperationID: "",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusInProgress,
			},
			wantErr: ErrEmptyOperationID,
		},
		{
			name: "empty database_id",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusInProgress,
			},
			wantErr: ErrEmptyDatabaseID,
		},
		{
			name: "empty command_type",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: "",
				Status:      ProgressStatusInProgress,
			},
			wantErr: ErrEmptyCommandType,
		},
		{
			name: "invalid status",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      "unknown-status",
			},
			wantErr: ErrInvalidProgressStatus,
		},
		{
			name: "valid started status",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusStarted,
			},
			wantErr: nil,
		},
		{
			name: "valid completed status",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusCompleted,
			},
			wantErr: nil,
		},
		{
			name: "valid failed status",
			progress: DesignerProgress{
				OperationID: "op-123",
				DatabaseID:  "db-456",
				CommandType: CommandTypeExtensionInstall,
				Status:      ProgressStatusFailed,
			},
			wantErr: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.progress.Validate()
			if err != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestSSHCredentials_Validate(t *testing.T) {
	tests := []struct {
		name    string
		ssh     SSHCredentials
		wantErr error
	}{
		{
			name: "valid with password",
			ssh: SSHCredentials{
				Host:     "server.example.com",
				Port:     22,
				User:     "admin",
				Password: "secret",
			},
			wantErr: nil,
		},
		{
			name: "valid with private key",
			ssh: SSHCredentials{
				Host:       "server.example.com",
				Port:       22,
				User:       "admin",
				PrivateKey: "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
			},
			wantErr: nil,
		},
		{
			name: "valid with zero port (default)",
			ssh: SSHCredentials{
				Host: "server.example.com",
				Port: 0,
				User: "admin",
			},
			wantErr: nil,
		},
		{
			name: "empty host",
			ssh: SSHCredentials{
				Host: "",
				Port: 22,
				User: "admin",
			},
			wantErr: ErrEmptySSHHost,
		},
		{
			name: "empty user",
			ssh: SSHCredentials{
				Host: "server.example.com",
				Port: 22,
				User: "",
			},
			wantErr: ErrEmptySSHUser,
		},
		{
			name: "invalid port negative",
			ssh: SSHCredentials{
				Host: "server.example.com",
				Port: -1,
				User: "admin",
			},
			wantErr: ErrInvalidSSHPort,
		},
		{
			name: "invalid port too high",
			ssh: SSHCredentials{
				Host: "server.example.com",
				Port: 70000,
				User: "admin",
			},
			wantErr: ErrInvalidSSHPort,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.ssh.Validate()
			if err != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestValidCommandTypes(t *testing.T) {
	types := ValidCommandTypes()
	expected := []string{
		CommandTypeExtensionInstall,
		CommandTypeExtensionRemove,
		CommandTypeConfigUpdate,
		CommandTypeConfigLoad,
		CommandTypeConfigDump,
		CommandTypeEpfExport,
		CommandTypeEpfImport,
		CommandTypeMetadataExport,
	}

	if len(types) != len(expected) {
		t.Errorf("ValidCommandTypes() returned %d types, expected %d", len(types), len(expected))
	}

	for i, typ := range types {
		if typ != expected[i] {
			t.Errorf("ValidCommandTypes()[%d] = %s, expected %s", i, typ, expected[i])
		}
	}
}

func TestValidProgressStatuses(t *testing.T) {
	statuses := ValidProgressStatuses()
	expected := []string{
		ProgressStatusStarted,
		ProgressStatusInProgress,
		ProgressStatusCompleted,
		ProgressStatusFailed,
	}

	if len(statuses) != len(expected) {
		t.Errorf("ValidProgressStatuses() returned %d statuses, expected %d", len(statuses), len(expected))
	}

	for i, status := range statuses {
		if status != expected[i] {
			t.Errorf("ValidProgressStatuses()[%d] = %s, expected %s", i, status, expected[i])
		}
	}
}

func TestNewDesignerCommand(t *testing.T) {
	ssh := SSHCredentials{
		Host: "server.example.com",
		Port: 22,
		User: "admin",
	}
	params := CommandParams{
		InfobasePath:  "/opt/1c/bases/test",
		ExtensionName: "MyExtension",
	}

	cmd := NewDesignerCommand("op-123", "db-456", CommandTypeExtensionInstall, ssh, params)

	if cmd.OperationID != "op-123" {
		t.Errorf("OperationID = %s, expected op-123", cmd.OperationID)
	}
	if cmd.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %s, expected db-456", cmd.DatabaseID)
	}
	if cmd.CommandType != CommandTypeExtensionInstall {
		t.Errorf("CommandType = %s, expected %s", cmd.CommandType, CommandTypeExtensionInstall)
	}
	if cmd.SSH.Host != ssh.Host {
		t.Errorf("SSH.Host = %s, expected %s", cmd.SSH.Host, ssh.Host)
	}
	if cmd.Params.InfobasePath != params.InfobasePath {
		t.Errorf("Params.InfobasePath = %s, expected %s", cmd.Params.InfobasePath, params.InfobasePath)
	}
	if cmd.CreatedAt.IsZero() {
		t.Error("CreatedAt should not be zero")
	}
}

func TestNewDesignerResult(t *testing.T) {
	duration := 5 * time.Second
	result := NewDesignerResult("op-123", "db-456", CommandTypeExtensionInstall, map[string]string{"key": "value"}, "success output", duration)

	if result.OperationID != "op-123" {
		t.Errorf("OperationID = %s, expected op-123", result.OperationID)
	}
	if result.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %s, expected db-456", result.DatabaseID)
	}
	if result.CommandType != CommandTypeExtensionInstall {
		t.Errorf("CommandType = %s, expected %s", result.CommandType, CommandTypeExtensionInstall)
	}
	if !result.Success {
		t.Error("Success should be true")
	}
	if result.Output != "success output" {
		t.Errorf("Output = %s, expected 'success output'", result.Output)
	}
	if result.ExitCode != 0 {
		t.Errorf("ExitCode = %d, expected 0", result.ExitCode)
	}
	if result.Duration != duration {
		t.Errorf("Duration = %v, expected %v", result.Duration, duration)
	}
	if result.CompletedAt.IsZero() {
		t.Error("CompletedAt should not be zero")
	}
}

func TestNewDesignerErrorResult(t *testing.T) {
	duration := 3 * time.Second
	result := NewDesignerErrorResult("op-123", "db-456", CommandTypeExtensionInstall, "connection failed", "SSH_ERROR", "error output", 1, duration)

	if result.OperationID != "op-123" {
		t.Errorf("OperationID = %s, expected op-123", result.OperationID)
	}
	if result.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %s, expected db-456", result.DatabaseID)
	}
	if result.CommandType != CommandTypeExtensionInstall {
		t.Errorf("CommandType = %s, expected %s", result.CommandType, CommandTypeExtensionInstall)
	}
	if result.Success {
		t.Error("Success should be false")
	}
	if result.Error != "connection failed" {
		t.Errorf("Error = %s, expected 'connection failed'", result.Error)
	}
	if result.ErrorCode != "SSH_ERROR" {
		t.Errorf("ErrorCode = %s, expected 'SSH_ERROR'", result.ErrorCode)
	}
	if result.Output != "error output" {
		t.Errorf("Output = %s, expected 'error output'", result.Output)
	}
	if result.ExitCode != 1 {
		t.Errorf("ExitCode = %d, expected 1", result.ExitCode)
	}
	if result.Duration != duration {
		t.Errorf("Duration = %v, expected %v", result.Duration, duration)
	}
}

func TestNewDesignerProgress(t *testing.T) {
	progress := NewDesignerProgress("op-123", "db-456", CommandTypeExtensionInstall, ProgressStatusInProgress, 50, "Installing extension...")

	if progress.OperationID != "op-123" {
		t.Errorf("OperationID = %s, expected op-123", progress.OperationID)
	}
	if progress.DatabaseID != "db-456" {
		t.Errorf("DatabaseID = %s, expected db-456", progress.DatabaseID)
	}
	if progress.CommandType != CommandTypeExtensionInstall {
		t.Errorf("CommandType = %s, expected %s", progress.CommandType, CommandTypeExtensionInstall)
	}
	if progress.Status != ProgressStatusInProgress {
		t.Errorf("Status = %s, expected %s", progress.Status, ProgressStatusInProgress)
	}
	if progress.Percentage != 50 {
		t.Errorf("Percentage = %d, expected 50", progress.Percentage)
	}
	if progress.Message != "Installing extension..." {
		t.Errorf("Message = %s, expected 'Installing extension...'", progress.Message)
	}
	if progress.Timestamp.IsZero() {
		t.Error("Timestamp should not be zero")
	}
}
