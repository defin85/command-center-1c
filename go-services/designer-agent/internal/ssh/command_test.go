package ssh

import (
	"strings"
	"testing"
)

func TestCommand_String(t *testing.T) {
	tests := []struct {
		name string
		cmd  Command
		want string
	}{
		{
			name: "command without args",
			cmd: Command{
				executable: "designer",
				args:       []string{},
			},
			want: "designer",
		},
		{
			name: "command with single arg",
			cmd: Command{
				executable: "designer",
				args:       []string{"/LoadCfg"},
			},
			want: "designer /LoadCfg",
		},
		{
			name: "command with multiple args",
			cmd: Command{
				executable: "designer",
				args:       []string{"/S192.168.1.1/base", "/Nadmin", "/LoadCfg", "config.cf"},
			},
			want: "designer /S192.168.1.1/base /Nadmin /LoadCfg config.cf",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.cmd.String(); got != tt.want {
				t.Errorf("String() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNewCommandBuilder(t *testing.T) {
	builder := NewCommandBuilder()

	if builder == nil {
		t.Fatal("NewCommandBuilder() returned nil")
	}

	if builder.DesignerPath != "designer" {
		t.Errorf("DesignerPath = %s, want 'designer'", builder.DesignerPath)
	}
}

func TestCommandBuilder_WithConnection(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	if builder.Server != "192.168.1.1" {
		t.Errorf("Server = %s, want 192.168.1.1", builder.Server)
	}

	if builder.Database != "testdb" {
		t.Errorf("Database = %s, want testdb", builder.Database)
	}

	if builder.User != "admin" {
		t.Errorf("User = %s, want admin", builder.User)
	}

	if builder.Password != "secret" {
		t.Errorf("Password = %s, want secret", builder.Password)
	}
}

func TestCommandBuilder_ConfigLoadCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ConfigLoadCmd("/tmp/config.cf")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/S192.168.1.1/testdb") {
		t.Errorf("Command missing server connection: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/Nadmin") {
		t.Errorf("Command missing user: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/Psecret") {
		t.Errorf("Command missing password: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/LoadCfg") {
		t.Errorf("Command missing /LoadCfg: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/config.cf") {
		t.Errorf("Command missing config file path: %s", cmdStr)
	}
}

func TestCommandBuilder_ConfigDumpCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ConfigDumpCmd("/tmp/dump")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/DumpCfg") {
		t.Errorf("Command missing /DumpCfg: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/dump") {
		t.Errorf("Command missing output directory: %s", cmdStr)
	}
}

func TestCommandBuilder_ConfigUpdateDBCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	tests := []struct {
		name    string
		options ConfigUpdateDBOptions
		want    []string
	}{
		{
			name:    "no options",
			options: ConfigUpdateDBOptions{},
			want:    []string{"/UpdateDBCfg"},
		},
		{
			name: "server mode",
			options: ConfigUpdateDBOptions{
				Server: true,
			},
			want: []string{"/UpdateDBCfg", "-Server"},
		},
		{
			name: "dynamic update",
			options: ConfigUpdateDBOptions{
				DynamicUpdate: true,
			},
			want: []string{"/UpdateDBCfg", "-Dynamic+"},
		},
		{
			name: "all options",
			options: ConfigUpdateDBOptions{
				Server:           true,
				DynamicUpdate:    true,
				BackgroundUpdate: true,
				WarningAsError:   true,
			},
			want: []string{"/UpdateDBCfg", "-Server", "-Dynamic+", "-BackgroundStart", "-WarningsAsErrors"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cmd := builder.ConfigUpdateDBCmd(tt.options)
			cmdStr := cmd.String()

			for _, expected := range tt.want {
				if !strings.Contains(cmdStr, expected) {
					t.Errorf("Command missing %s: %s", expected, cmdStr)
				}
			}
		})
	}
}

func TestCommandBuilder_ExtensionInstallCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ExtensionInstallCmd("/tmp/ext.cfe", "TestExtension")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/LoadCfg") {
		t.Errorf("Command missing /LoadCfg: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/ext.cfe") {
		t.Errorf("Command missing extension file: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "-Extension") {
		t.Errorf("Command missing -Extension: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "TestExtension") {
		t.Errorf("Command missing extension name: %s", cmdStr)
	}
}

func TestCommandBuilder_ExtensionInstallCmd_NoName(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ExtensionInstallCmd("/tmp/ext.cfe", "")

	cmdStr := cmd.String()

	if strings.Contains(cmdStr, "-Extension") {
		t.Errorf("Command should not contain -Extension when name is empty: %s", cmdStr)
	}
}

func TestCommandBuilder_ExtensionRemoveCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ExtensionRemoveCmd("TestExtension")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/ManageCfgExtensions") {
		t.Errorf("Command missing /ManageCfgExtensions: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "-delete") {
		t.Errorf("Command missing -delete: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "-Extension") {
		t.Errorf("Command missing -Extension: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "TestExtension") {
		t.Errorf("Command missing extension name: %s", cmdStr)
	}
}

func TestCommandBuilder_ExtensionListCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.ExtensionListCmd()

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/ManageCfgExtensions") {
		t.Errorf("Command missing /ManageCfgExtensions: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "-list") {
		t.Errorf("Command missing -list: %s", cmdStr)
	}
}

func TestCommandBuilder_DumpExtFilesCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.DumpExtFilesCmd("/tmp/ext.epf", "/tmp/output")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/DumpExternalDataProcessorOrReportToFiles") {
		t.Errorf("Command missing /DumpExternalDataProcessorOrReportToFiles: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/output") {
		t.Errorf("Command missing output directory: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/ext.epf") {
		t.Errorf("Command missing extension file: %s", cmdStr)
	}
}

func TestCommandBuilder_DumpConfigToFilesCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.DumpConfigToFilesCmd("/tmp/dump")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/DumpConfigToFiles") {
		t.Errorf("Command missing /DumpConfigToFiles: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/dump") {
		t.Errorf("Command missing output directory: %s", cmdStr)
	}
}

func TestCommandBuilder_LoadConfigFromFilesCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	cmd := builder.LoadConfigFromFilesCmd("/tmp/config")

	cmdStr := cmd.String()

	if !strings.Contains(cmdStr, "/LoadConfigFromFiles") {
		t.Errorf("Command missing /LoadConfigFromFiles: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/config") {
		t.Errorf("Command missing input directory: %s", cmdStr)
	}
}

func TestCommandBuilder_CheckConfigCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	tests := []struct {
		name    string
		options CheckConfigOptions
		want    []string
		notWant []string
	}{
		{
			name:    "no options",
			options: CheckConfigOptions{},
			want:    []string{"/CheckConfig"},
		},
		{
			name: "all clients",
			options: CheckConfigOptions{
				AllClients: true,
			},
			want:    []string{"/CheckConfig", "-AllClients"},
			notWant: []string{"-ThinClient", "-WebClient", "-Server"},
		},
		{
			name: "specific clients",
			options: CheckConfigOptions{
				ThinClient: true,
				WebClient:  true,
			},
			want: []string{"/CheckConfig", "-ThinClient", "-WebClient"},
		},
		{
			name: "extended checks",
			options: CheckConfigOptions{
				ExtendedCheck:       true,
				IncorrectReferences: true,
				EmptyHandlers:       true,
			},
			want: []string{"/CheckConfig", "-ExtendedModulesCheck", "-IncorrectReferences", "-EmptyHandlers"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cmd := builder.CheckConfigCmd(tt.options)
			cmdStr := cmd.String()

			for _, expected := range tt.want {
				if !strings.Contains(cmdStr, expected) {
					t.Errorf("Command missing %s: %s", expected, cmdStr)
				}
			}

			for _, notExpected := range tt.notWant {
				if strings.Contains(cmdStr, notExpected) {
					t.Errorf("Command should not contain %s: %s", notExpected, cmdStr)
				}
			}
		})
	}
}

func TestCommandBuilder_CreateInfobaseCmd(t *testing.T) {
	builder := NewCommandBuilder()

	tests := []struct {
		name    string
		options CreateInfobaseOptions
		want    []string
	}{
		{
			name: "file-based",
			options: CreateInfobaseOptions{
				FilePath: "/opt/1c/bases/test",
			},
			want: []string{"/CreateInfobase", "File=", "/opt/1c/bases/test"},
		},
		{
			name: "server-based",
			options: CreateInfobaseOptions{
				Server:   "192.168.1.1",
				Database: "testdb",
			},
			want: []string{"/CreateInfobase", "Srvr=", "Ref=", "192.168.1.1", "testdb"},
		},
		{
			name: "with template",
			options: CreateInfobaseOptions{
				FilePath:     "/opt/1c/bases/test",
				TemplatePath: "/opt/1c/templates/template.dt",
			},
			want: []string{"/CreateInfobase", "/UseTemplate", "/opt/1c/templates/template.dt"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cmd := builder.CreateInfobaseCmd(tt.options)
			cmdStr := cmd.String()

			for _, expected := range tt.want {
				if !strings.Contains(cmdStr, expected) {
					t.Errorf("Command missing %s: %s", expected, cmdStr)
				}
			}
		})
	}
}

func TestCommandBuilder_RunEnterpriseCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	builder.DesignerPath = "/opt/1c/designer"

	cmd := builder.RunEnterpriseCmd(RunEnterpriseOptions{
		Execute:       "/tmp/process.epf",
		CloseOnFinish: true,
		Parameters:    "param1;param2",
		Out:           "/tmp/output.log",
	})

	cmdStr := cmd.String()

	// Should use 1cv8 instead of designer
	if !strings.Contains(cmdStr, "1cv8") {
		t.Errorf("Command should use 1cv8: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "ENTERPRISE") {
		t.Errorf("Command missing ENTERPRISE: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/Execute") {
		t.Errorf("Command missing /Execute: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/tmp/process.epf") {
		t.Errorf("Command missing execute path: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/DisableStartupDialogs") {
		t.Errorf("Command missing /DisableStartupDialogs: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/Cparam1;param2") {
		t.Errorf("Command missing parameters: %s", cmdStr)
	}

	if !strings.Contains(cmdStr, "/Out") {
		t.Errorf("Command missing /Out: %s", cmdStr)
	}
}

func TestBatchCmd(t *testing.T) {
	builder := NewCommandBuilder().
		WithConnection("192.168.1.1", "testdb", "admin", "secret")

	batch := NewBatchCmd().
		Add(builder.ConfigLoadCmd("/tmp/config.cf")).
		Add(builder.ConfigUpdateDBCmd(ConfigUpdateDBOptions{}))

	commands := batch.Commands()
	if len(commands) != 2 {
		t.Errorf("Batch has %d commands, want 2", len(commands))
	}

	batchStr := batch.String()
	if !strings.Contains(batchStr, "/LoadCfg") {
		t.Errorf("Batch missing /LoadCfg: %s", batchStr)
	}

	if !strings.Contains(batchStr, "/UpdateDBCfg") {
		t.Errorf("Batch missing /UpdateDBCfg: %s", batchStr)
	}

	// Should be separated by newlines
	lines := strings.Split(batchStr, "\n")
	if len(lines) != 2 {
		t.Errorf("Batch has %d lines, want 2", len(lines))
	}
}

func TestCommandBuilder_NoConnection(t *testing.T) {
	// Test that commands work without connection parameters
	builder := NewCommandBuilder()

	cmd := builder.ConfigLoadCmd("/tmp/config.cf")
	cmdStr := cmd.String()

	// Should still contain the command
	if !strings.Contains(cmdStr, "/LoadCfg") {
		t.Errorf("Command missing /LoadCfg: %s", cmdStr)
	}

	// Should not contain connection args
	if strings.Contains(cmdStr, "/S") {
		t.Errorf("Command should not contain server connection: %s", cmdStr)
	}
}
