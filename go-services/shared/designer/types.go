// Package designer provides types and constants for Designer operations.
// Used for communication between Worker and designer-agent via Redis Streams.
// Designer-agent works through SSH to 1C Agent Mode for configuration management.
package designer

import (
	"errors"
	"time"
)

// Command type constants
const (
	CommandTypeExtensionInstall = "extension-install"
	CommandTypeExtensionRemove  = "extension-remove"
	CommandTypeConfigUpdate     = "config-update"
	CommandTypeConfigLoad       = "config-load"
	CommandTypeConfigDump       = "config-dump"
	CommandTypeEpfExport        = "epf-export"
	CommandTypeEpfImport        = "epf-import"
	CommandTypeMetadataExport   = "metadata-export"
)

// Progress status constants
const (
	ProgressStatusStarted    = "started"
	ProgressStatusInProgress = "in_progress"
	ProgressStatusCompleted  = "completed"
	ProgressStatusFailed     = "failed"
)

// Errors for validation
var (
	// ErrEmptyOperationID indicates that the operation ID is empty
	ErrEmptyOperationID = errors.New("designer: empty operation_id")

	// ErrEmptyDatabaseID indicates that the database ID is empty
	ErrEmptyDatabaseID = errors.New("designer: empty database_id")

	// ErrEmptyCommandType indicates that the command type is empty
	ErrEmptyCommandType = errors.New("designer: empty command_type")

	// ErrInvalidCommandType indicates that the command type is not recognized
	ErrInvalidCommandType = errors.New("designer: invalid command_type")

	// ErrEmptySSHHost indicates that the SSH host is empty
	ErrEmptySSHHost = errors.New("designer: empty ssh_host")

	// ErrEmptySSHUser indicates that the SSH user is empty
	ErrEmptySSHUser = errors.New("designer: empty ssh_user")

	// ErrInvalidSSHPort indicates that the SSH port is invalid
	ErrInvalidSSHPort = errors.New("designer: invalid ssh_port (must be 1-65535)")

	// ErrEmptyInfobasePath indicates that the infobase path is empty
	ErrEmptyInfobasePath = errors.New("designer: empty infobase_path")

	// ErrEmptyExtensionName indicates that the extension name is empty for extension operations
	ErrEmptyExtensionName = errors.New("designer: empty extension_name for extension operation")

	// ErrEmptySourcePath indicates that the source path is empty for load/import operations
	ErrEmptySourcePath = errors.New("designer: empty source_path for load/import operation")

	// ErrEmptyTargetPath indicates that the target path is empty for dump/export operations
	ErrEmptyTargetPath = errors.New("designer: empty target_path for dump/export operation")

	// ErrInvalidProgressStatus indicates that the progress status is not valid
	ErrInvalidProgressStatus = errors.New("designer: invalid progress_status")
)

// SSHCredentials contains SSH connection parameters for designer-agent.
type SSHCredentials struct {
	// Host is the SSH server hostname or IP address
	Host string `json:"host"`

	// Port is the SSH server port (default: 22)
	Port int `json:"port"`

	// User is the SSH username
	User string `json:"user"`

	// Password is the SSH password (optional if using key auth)
	Password string `json:"password,omitempty"`

	// PrivateKey is the SSH private key content (optional if using password auth)
	PrivateKey string `json:"private_key,omitempty"`

	// PrivateKeyPassphrase is the passphrase for encrypted private key
	PrivateKeyPassphrase string `json:"private_key_passphrase,omitempty"`
}

// Validate checks if SSH credentials have required fields.
func (s *SSHCredentials) Validate() error {
	if s.Host == "" {
		return ErrEmptySSHHost
	}
	if s.User == "" {
		return ErrEmptySSHUser
	}
	if s.Port < 0 || s.Port > 65535 {
		return ErrInvalidSSHPort
	}
	return nil
}

// InfobaseCredentials contains 1C infobase authentication parameters.
type InfobaseCredentials struct {
	// User is the 1C infobase username (optional)
	User string `json:"user,omitempty"`

	// Password is the 1C infobase password (optional)
	Password string `json:"password,omitempty"`
}

// CommandParams contains command-specific parameters.
type CommandParams struct {
	// InfobasePath is the path to the 1C infobase on the server
	InfobasePath string `json:"infobase_path"`

	// ExtensionName is the name of the extension (for extension operations)
	ExtensionName string `json:"extension_name,omitempty"`

	// SourcePath is the path to source file/directory (for load/import operations)
	SourcePath string `json:"source_path,omitempty"`

	// TargetPath is the path to target file/directory (for dump/export operations)
	TargetPath string `json:"target_path,omitempty"`

	// ConfigurationFile is the path to configuration file (.cf)
	ConfigurationFile string `json:"configuration_file,omitempty"`

	// ExtensionFile is the path to extension file (.cfe)
	ExtensionFile string `json:"extension_file,omitempty"`

	// UpdateDBCfg indicates whether to update database configuration
	UpdateDBCfg bool `json:"update_db_cfg,omitempty"`

	// Server indicates whether this is a server infobase
	Server bool `json:"server,omitempty"`

	// ClusterHost is the 1C server hostname (for server infobases)
	ClusterHost string `json:"cluster_host,omitempty"`

	// ClusterPort is the 1C server port (for server infobases)
	ClusterPort int `json:"cluster_port,omitempty"`

	// MetadataObjects is the list of metadata objects to export
	MetadataObjects []string `json:"metadata_objects,omitempty"`

	// AdditionalArgs contains additional command-line arguments
	AdditionalArgs []string `json:"additional_args,omitempty"`
}

// DesignerCommand represents a command to be executed by designer-agent.
// Commands are published to Redis Streams by Worker and consumed by designer-agent.
type DesignerCommand struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// CommandType specifies the operation type
	CommandType string `json:"command_type"`

	// SSH contains SSH connection credentials
	SSH SSHCredentials `json:"ssh"`

	// Infobase contains 1C infobase credentials (optional)
	Infobase InfobaseCredentials `json:"infobase,omitempty"`

	// Params contains command-specific parameters
	Params CommandParams `json:"params"`

	// TimeoutSeconds specifies the operation timeout (0 = default 300s)
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`

	// CreatedAt is the timestamp when command was created
	CreatedAt time.Time `json:"created_at"`
}

// Validate checks if the command has all required fields and valid command type.
func (c *DesignerCommand) Validate() error {
	if c.OperationID == "" {
		return ErrEmptyOperationID
	}
	if c.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if c.CommandType == "" {
		return ErrEmptyCommandType
	}

	// Validate command type
	switch c.CommandType {
	case CommandTypeExtensionInstall, CommandTypeExtensionRemove,
		CommandTypeConfigUpdate, CommandTypeConfigLoad, CommandTypeConfigDump,
		CommandTypeEpfExport, CommandTypeEpfImport, CommandTypeMetadataExport:
		// Valid command type
	default:
		return ErrInvalidCommandType
	}

	// Validate SSH credentials
	if err := c.SSH.Validate(); err != nil {
		return err
	}

	// Validate params based on command type
	if c.Params.InfobasePath == "" {
		return ErrEmptyInfobasePath
	}

	// Extension operations require extension name
	if (c.CommandType == CommandTypeExtensionInstall || c.CommandType == CommandTypeExtensionRemove) &&
		c.Params.ExtensionName == "" {
		return ErrEmptyExtensionName
	}

	// Load/Import operations require source path
	if (c.CommandType == CommandTypeConfigLoad || c.CommandType == CommandTypeEpfImport) &&
		c.Params.SourcePath == "" {
		return ErrEmptySourcePath
	}

	// Dump/Export operations require target path
	if (c.CommandType == CommandTypeConfigDump || c.CommandType == CommandTypeEpfExport ||
		c.CommandType == CommandTypeMetadataExport) && c.Params.TargetPath == "" {
		return ErrEmptyTargetPath
	}

	return nil
}

// DesignerResult represents the result of a Designer command execution.
// Results are published to Redis Streams by designer-agent and consumed by Worker.
type DesignerResult struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// CommandType is the type of command that was executed
	CommandType string `json:"command_type"`

	// Success indicates whether the command completed successfully
	Success bool `json:"success"`

	// Error contains the error message if Success is false
	Error string `json:"error,omitempty"`

	// ErrorCode contains the error code for categorization
	ErrorCode string `json:"error_code,omitempty"`

	// Data contains additional result data
	Data interface{} `json:"data,omitempty"`

	// Output contains stdout/stderr from the command execution
	Output string `json:"output,omitempty"`

	// ExitCode is the exit code from the designer command
	ExitCode int `json:"exit_code,omitempty"`

	// Duration is how long the command took to execute
	Duration time.Duration `json:"duration"`

	// CompletedAt is the timestamp when command completed
	CompletedAt time.Time `json:"completed_at"`
}

// Validate checks if the result has all required fields.
func (r *DesignerResult) Validate() error {
	if r.OperationID == "" {
		return ErrEmptyOperationID
	}
	if r.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if r.CommandType == "" {
		return ErrEmptyCommandType
	}
	return nil
}

// DesignerProgress represents progress update for long-running operations.
// Published to progress stream by designer-agent for UI updates.
type DesignerProgress struct {
	// OperationID is the unique identifier for the parent batch operation
	OperationID string `json:"operation_id"`

	// DatabaseID is the internal database identifier in CommandCenter
	DatabaseID string `json:"database_id"`

	// CommandType is the type of command being executed
	CommandType string `json:"command_type"`

	// Status is the current progress status
	Status string `json:"status"`

	// Percentage is the completion percentage (0-100)
	Percentage int `json:"percentage"`

	// Message is a human-readable progress message
	Message string `json:"message,omitempty"`

	// Phase describes the current execution phase
	Phase string `json:"phase,omitempty"`

	// Timestamp is when this progress update was created
	Timestamp time.Time `json:"timestamp"`
}

// Validate checks if the progress update has all required fields.
func (p *DesignerProgress) Validate() error {
	if p.OperationID == "" {
		return ErrEmptyOperationID
	}
	if p.DatabaseID == "" {
		return ErrEmptyDatabaseID
	}
	if p.CommandType == "" {
		return ErrEmptyCommandType
	}

	// Validate status
	switch p.Status {
	case ProgressStatusStarted, ProgressStatusInProgress, ProgressStatusCompleted, ProgressStatusFailed:
		// Valid status
	default:
		return ErrInvalidProgressStatus
	}

	return nil
}

// ValidCommandTypes returns a list of all valid command types.
func ValidCommandTypes() []string {
	return []string{
		CommandTypeExtensionInstall,
		CommandTypeExtensionRemove,
		CommandTypeConfigUpdate,
		CommandTypeConfigLoad,
		CommandTypeConfigDump,
		CommandTypeEpfExport,
		CommandTypeEpfImport,
		CommandTypeMetadataExport,
	}
}

// ValidProgressStatuses returns a list of all valid progress statuses.
func ValidProgressStatuses() []string {
	return []string{
		ProgressStatusStarted,
		ProgressStatusInProgress,
		ProgressStatusCompleted,
		ProgressStatusFailed,
	}
}

// NewDesignerCommand creates a new DesignerCommand with the given parameters.
func NewDesignerCommand(operationID, databaseID, commandType string, ssh SSHCredentials, params CommandParams) *DesignerCommand {
	return &DesignerCommand{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		SSH:         ssh,
		Params:      params,
		CreatedAt:   time.Now(),
	}
}

// NewDesignerResult creates a new successful DesignerResult.
func NewDesignerResult(operationID, databaseID, commandType string, data interface{}, output string, duration time.Duration) *DesignerResult {
	return &DesignerResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     true,
		Data:        data,
		Output:      output,
		ExitCode:    0,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}

// NewDesignerErrorResult creates a new failed DesignerResult.
func NewDesignerErrorResult(operationID, databaseID, commandType, errMsg, errorCode, output string, exitCode int, duration time.Duration) *DesignerResult {
	return &DesignerResult{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Success:     false,
		Error:       errMsg,
		ErrorCode:   errorCode,
		Output:      output,
		ExitCode:    exitCode,
		Duration:    duration,
		CompletedAt: time.Now(),
	}
}

// NewDesignerProgress creates a new DesignerProgress update.
func NewDesignerProgress(operationID, databaseID, commandType, status string, percentage int, message string) *DesignerProgress {
	return &DesignerProgress{
		OperationID: operationID,
		DatabaseID:  databaseID,
		CommandType: commandType,
		Status:      status,
		Percentage:  percentage,
		Message:     message,
		Timestamp:   time.Now(),
	}
}
