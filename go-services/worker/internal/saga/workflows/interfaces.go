// Package workflows provides concrete saga workflow implementations for CommandCenter1C.
// Each workflow defines steps, compensation handlers, and integration with external services.
package workflows

import (
	"context"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/odata"
)

// RASClient sends commands to ras-adapter via Redis Streams.
// Implementations should publish commands and wait for results.
type RASClient interface {
	// LockScheduledJobs blocks scheduled jobs (reglamentirovannye zadaniya) for an infobase.
	LockScheduledJobs(ctx context.Context, clusterID, infobaseID string) error

	// UnlockScheduledJobs unblocks scheduled jobs for an infobase.
	UnlockScheduledJobs(ctx context.Context, clusterID, infobaseID string) error

	// BlockConnections denies new connections to an infobase.
	BlockConnections(ctx context.Context, clusterID, infobaseID string) error

	// UnblockConnections allows new connections to an infobase.
	UnblockConnections(ctx context.Context, clusterID, infobaseID string) error

	// TerminateSessions forcefully terminates all active sessions for an infobase.
	TerminateSessions(ctx context.Context, clusterID, infobaseID string) error

	// GetSessionCount returns the number of active sessions for an infobase.
	GetSessionCount(ctx context.Context, clusterID, infobaseID string) (int, error)
}

// SSHCredentials contains SSH connection parameters.
type SSHCredentials struct {
	Host       string `json:"host"`
	Port       int    `json:"port"`
	Username   string `json:"username"`
	Password   string `json:"password,omitempty"`
	KeyFile    string `json:"key_file,omitempty"`
	Passphrase string `json:"passphrase,omitempty"`
}

// DesignerClient sends commands to designer-agent via Redis Streams.
// Designer-agent executes 1C:Enterprise Designer commands via SSH.
type DesignerClient interface {
	// InstallExtension installs a .cfe extension file to an infobase.
	InstallExtension(ctx context.Context, ssh SSHCredentials, dbPath, extFile, extName string) error

	// RemoveExtension removes an extension from an infobase by name.
	RemoveExtension(ctx context.Context, ssh SSHCredentials, dbPath, extName string) error

	// UpdateDBCfg applies configuration changes to the database (UpdateDBCfg).
	// This is the longest operation, can take up to 4 hours for large databases.
	UpdateDBCfg(ctx context.Context, ssh SSHCredentials, dbPath string) error

	// LoadConfig loads a .cf configuration file to an infobase.
	LoadConfig(ctx context.Context, ssh SSHCredentials, dbPath, cfFile string) error

	// DumpConfig exports the current configuration to a .cf file.
	DumpConfig(ctx context.Context, ssh SSHCredentials, dbPath, targetPath string) error
}

// ODataClient executes OData calls (direct HTTP inside worker).
type ODataClient interface {
	// Query executes an OData query and returns results.
	Query(ctx context.Context, creds odata.ODataCredentials, entity string, query *odata.QueryParams) ([]map[string]interface{}, error)

	// Create creates a new entity record.
	Create(ctx context.Context, creds odata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error)

	// Update updates an existing entity record.
	Update(ctx context.Context, creds odata.ODataCredentials, entity, entityID string, data map[string]interface{}) error

	// Delete deletes an entity record.
	Delete(ctx context.Context, creds odata.ODataCredentials, entity, entityID string) error

	// ExecuteBatch executes multiple operations in a single batch request.
	ExecuteBatch(ctx context.Context, creds odata.ODataCredentials, items []odata.BatchItem) (*odata.BatchResult, error)
}

// DatabaseInfo contains information about a 1C database for workflow operations.
type DatabaseInfo struct {
	// DatabaseID is the internal CommandCenter database ID.
	DatabaseID string `json:"database_id"`

	// ClusterID is the 1C RAS cluster UUID.
	ClusterID string `json:"cluster_id"`

	// InfobaseID is the 1C RAS infobase UUID.
	InfobaseID string `json:"infobase_id"`

	// Name is the human-readable database name.
	Name string `json:"name"`

	// SSHHost is the hostname where designer-agent can connect.
	SSHHost string `json:"ssh_host,omitempty"`

	// InfobasePath is the path to the infobase on the 1C server.
	InfobasePath string `json:"infobase_path,omitempty"`

	// ODataBaseURL is the OData endpoint URL for this database.
	ODataBaseURL string `json:"odata_base_url,omitempty"`
}

// WorkflowConfig contains common configuration for all workflows.
type WorkflowConfig struct {
	// DefaultStepTimeout is the default timeout for workflow steps.
	DefaultStepTimeout time.Duration

	// SessionWaitTimeout is how long to wait for sessions to close.
	SessionWaitTimeout time.Duration

	// SessionCheckInterval is the interval between session count checks.
	SessionCheckInterval time.Duration

	// LockTTL is the default TTL for database locks.
	LockTTL time.Duration

	// LongOperationLockTTL is the TTL for long operations like config update (4 hours).
	LongOperationLockTTL time.Duration

	// HeartbeatInterval is the interval for lock heartbeat during long operations.
	HeartbeatInterval time.Duration
}

// DefaultWorkflowConfig returns sensible defaults for workflow configuration.
func DefaultWorkflowConfig() *WorkflowConfig {
	return &WorkflowConfig{
		DefaultStepTimeout:   5 * time.Minute,
		SessionWaitTimeout:   5 * time.Minute,
		SessionCheckInterval: 5 * time.Second,
		LockTTL:              15 * time.Minute,
		LongOperationLockTTL: 4 * time.Hour,
		HeartbeatInterval:    1 * time.Minute,
	}
}

// WorkflowDependencies contains all external dependencies for workflows.
type WorkflowDependencies struct {
	RASClient      RASClient
	DesignerClient DesignerClient
	ODataClient    ODataClient
	Config         *WorkflowConfig
}

// ContextKey is a type for context keys to avoid collisions.
type ContextKey string

// Context keys for workflow data.
const (
	// ContextKeyDatabaseInfo stores DatabaseInfo in context.
	ContextKeyDatabaseInfo ContextKey = "database_info"

	// ContextKeySSHCredentials stores SSHCredentials in context.
	ContextKeySSHCredentials ContextKey = "ssh_credentials"

	// ContextKeyODataCredentials stores ODataCredentials in context.
	ContextKeyODataCredentials ContextKey = "odata_credentials"

	// ContextKeyBackupPath stores the path to configuration backup.
	ContextKeyBackupPath ContextKey = "backup_path"

	// ContextKeyCreatedEntityIDs stores IDs of entities created in batch.
	ContextKeyCreatedEntityIDs ContextKey = "created_entity_ids"

	// ContextKeyPreviousValues stores previous values for update compensation.
	ContextKeyPreviousValues ContextKey = "previous_values"
)
