package ssh

import (
	"fmt"
	"strings"
)

// Command represents a 1C Designer command.
type Command struct {
	executable string
	args       []string
}

// String returns the command as a string ready for execution.
func (c *Command) String() string {
	if len(c.args) == 0 {
		return c.executable
	}
	return fmt.Sprintf("%s %s", c.executable, strings.Join(c.args, " "))
}

// CommandBuilder builds 1C Designer/Agent commands.
type CommandBuilder struct {
	// Path to 1C Designer executable (default: designer)
	DesignerPath string

	// Common connection parameters
	Server   string // /S<server>/<base>
	Database string
	User     string
	Password string
}

// NewCommandBuilder creates a new command builder with defaults.
func NewCommandBuilder() *CommandBuilder {
	return &CommandBuilder{
		DesignerPath: "designer", // Will be overridden based on platform
	}
}

// WithConnection sets connection parameters.
func (b *CommandBuilder) WithConnection(server, database, user, password string) *CommandBuilder {
	b.Server = server
	b.Database = database
	b.User = user
	b.Password = password
	return b
}

// connectionArgs returns common connection arguments.
func (b *CommandBuilder) connectionArgs() []string {
	var args []string

	if b.Server != "" && b.Database != "" {
		args = append(args, fmt.Sprintf("/S%s/%s", b.Server, b.Database))
	}

	if b.User != "" {
		args = append(args, fmt.Sprintf("/N%s", b.User))
	}

	if b.Password != "" {
		args = append(args, fmt.Sprintf("/P%s", b.Password))
	}

	return args
}

// ConfigLoadCmd creates config load-cfg command.
// Loads configuration from file into infobase.
func (b *CommandBuilder) ConfigLoadCmd(configFile string) *Command {
	args := b.connectionArgs()
	args = append(args, "/LoadCfg", configFile)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// ConfigDumpCmd creates config dump-cfg command.
// Dumps configuration from infobase to directory.
func (b *CommandBuilder) ConfigDumpCmd(outputDir string) *Command {
	args := b.connectionArgs()
	args = append(args, "/DumpCfg", outputDir)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// ConfigUpdateDBOptions holds options for config update-db-cfg command.
type ConfigUpdateDBOptions struct {
	// Server mode update
	Server bool

	// Dynamic update allowed
	DynamicUpdate bool

	// Background update
	BackgroundUpdate bool

	// Warning as error
	WarningAsError bool
}

// ConfigUpdateDBCmd creates config update-db-cfg command.
// Updates database configuration.
func (b *CommandBuilder) ConfigUpdateDBCmd(options ConfigUpdateDBOptions) *Command {
	args := b.connectionArgs()
	args = append(args, "/UpdateDBCfg")

	if options.Server {
		args = append(args, "-Server")
	}

	if options.DynamicUpdate {
		args = append(args, "-Dynamic+")
	}

	if options.BackgroundUpdate {
		args = append(args, "-BackgroundStart")
	}

	if options.WarningAsError {
		args = append(args, "-WarningsAsErrors")
	}

	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// ExtensionInstallCmd creates extension load command.
// Installs extension from file.
func (b *CommandBuilder) ExtensionInstallCmd(extensionFile, extensionName string) *Command {
	args := b.connectionArgs()
	args = append(args, "/LoadCfg", extensionFile)

	if extensionName != "" {
		args = append(args, "-Extension", extensionName)
	}

	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// ExtensionRemoveCmd creates extension delete command.
// Removes extension by name.
func (b *CommandBuilder) ExtensionRemoveCmd(extensionName string) *Command {
	args := b.connectionArgs()
	args = append(args, "/ManageCfgExtensions", "-delete", "-Extension", extensionName)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// ExtensionListCmd creates command to list extensions.
func (b *CommandBuilder) ExtensionListCmd() *Command {
	args := b.connectionArgs()
	args = append(args, "/ManageCfgExtensions", "-list")
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// DumpExtFilesCmd creates dump-ext-files command.
// Extracts extension files to directory.
func (b *CommandBuilder) DumpExtFilesCmd(extensionFile, outputDir string) *Command {
	args := b.connectionArgs()
	args = append(args, "/DumpExternalDataProcessorOrReportToFiles", outputDir, extensionFile)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// DumpConfigToFilesCmd creates DumpConfigToFiles command.
// Dumps configuration to XML files.
func (b *CommandBuilder) DumpConfigToFilesCmd(outputDir string) *Command {
	args := b.connectionArgs()
	args = append(args, "/DumpConfigToFiles", outputDir)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// LoadConfigFromFilesCmd creates LoadConfigFromFiles command.
// Loads configuration from XML files.
func (b *CommandBuilder) LoadConfigFromFilesCmd(inputDir string) *Command {
	args := b.connectionArgs()
	args = append(args, "/LoadConfigFromFiles", inputDir)
	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// CheckConfigCmd creates CheckConfig command.
// Validates configuration.
type CheckConfigOptions struct {
	// Thin client mode
	ThinClient bool

	// Web client mode
	WebClient bool

	// Server mode
	Server bool

	// External connection mode
	ExternalConnection bool

	// Check all modes
	AllClients bool

	// Extended check
	ExtendedCheck bool

	// Check references
	IncorrectReferences bool

	// Check emptiness
	EmptyHandlers bool
}

// CheckConfigCmd creates configuration check command.
func (b *CommandBuilder) CheckConfigCmd(options CheckConfigOptions) *Command {
	args := b.connectionArgs()
	args = append(args, "/CheckConfig")

	if options.AllClients {
		args = append(args, "-AllClients")
	} else {
		if options.ThinClient {
			args = append(args, "-ThinClient")
		}
		if options.WebClient {
			args = append(args, "-WebClient")
		}
		if options.Server {
			args = append(args, "-Server")
		}
		if options.ExternalConnection {
			args = append(args, "-ExternalConnection")
		}
	}

	if options.ExtendedCheck {
		args = append(args, "-ExtendedModulesCheck")
	}

	if options.IncorrectReferences {
		args = append(args, "-IncorrectReferences")
	}

	if options.EmptyHandlers {
		args = append(args, "-EmptyHandlers")
	}

	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// CreateInfobaseCmd creates create infobase command.
type CreateInfobaseOptions struct {
	// File-based infobase path
	FilePath string

	// Server-based infobase
	Server   string
	Database string

	// Locale
	Locale string

	// From template
	TemplatePath string
}

// CreateInfobaseCmd creates command to create new infobase.
func (b *CommandBuilder) CreateInfobaseCmd(options CreateInfobaseOptions) *Command {
	args := []string{"/CreateInfobase"}

	if options.FilePath != "" {
		args = append(args, fmt.Sprintf("File=%q", options.FilePath))
	} else if options.Server != "" && options.Database != "" {
		args = append(args, fmt.Sprintf("Srvr=%q;Ref=%q", options.Server, options.Database))
	}

	if options.Locale != "" {
		args = append(args, fmt.Sprintf("Locale=%s", options.Locale))
	}

	if options.TemplatePath != "" {
		args = append(args, "/UseTemplate", options.TemplatePath)
	}

	return &Command{
		executable: b.DesignerPath,
		args:       args,
	}
}

// RunEnterpriseCmd creates command to run 1C:Enterprise.
type RunEnterpriseOptions struct {
	// Execute external processing
	Execute string

	// Close after execution
	CloseOnFinish bool

	// Parameters to pass
	Parameters string

	// Output file
	Out string
}

// RunEnterpriseCmd creates command to run 1C:Enterprise mode.
func (b *CommandBuilder) RunEnterpriseCmd(options RunEnterpriseOptions) *Command {
	// Use 1cv8 for enterprise mode
	executable := strings.Replace(b.DesignerPath, "designer", "1cv8", 1)
	if executable == b.DesignerPath {
		executable = "1cv8"
	}

	args := []string{"ENTERPRISE"}
	args = append(args, b.connectionArgs()...)

	if options.Execute != "" {
		args = append(args, "/Execute", options.Execute)
	}

	if options.CloseOnFinish {
		args = append(args, "/DisableStartupDialogs", "/DisableStartupMessages")
	}

	if options.Parameters != "" {
		args = append(args, fmt.Sprintf("/C%s", options.Parameters))
	}

	if options.Out != "" {
		args = append(args, "/Out", options.Out)
	}

	return &Command{
		executable: executable,
		args:       args,
	}
}

// BatchCmd creates a batch of commands to execute sequentially.
type BatchCmd struct {
	commands []*Command
}

// NewBatchCmd creates a new batch command.
func NewBatchCmd() *BatchCmd {
	return &BatchCmd{
		commands: make([]*Command, 0),
	}
}

// Add adds a command to the batch.
func (b *BatchCmd) Add(cmd *Command) *BatchCmd {
	b.commands = append(b.commands, cmd)
	return b
}

// Commands returns all commands in the batch.
func (b *BatchCmd) Commands() []*Command {
	return b.commands
}

// String returns all commands as a single string separated by newlines.
func (b *BatchCmd) String() string {
	var lines []string
	for _, cmd := range b.commands {
		lines = append(lines, cmd.String())
	}
	return strings.Join(lines, "\n")
}
