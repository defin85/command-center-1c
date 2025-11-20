package eventhandlers

// CommandPayload represents the generic structure for command payloads
type CommandPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"` // Optional: Django Database ID
}

// LockCommandPayload represents the payload for lock infobase commands
type LockCommandPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
}

// UnlockCommandPayload represents the payload for unlock infobase commands
type UnlockCommandPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
}

// TerminateCommandPayload represents the payload for terminate sessions commands
type TerminateCommandPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
}

// LockSuccessPayload represents the success response for lock commands
type LockSuccessPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
	Message    string `json:"message"`
}

// UnlockSuccessPayload represents the success response for unlock commands
type UnlockSuccessPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
	Message    string `json:"message"`
}

// TerminateSuccessPayload represents the success response for terminate commands
type TerminateSuccessPayload struct {
	ClusterID        string `json:"cluster_id"`
	InfobaseID       string `json:"infobase_id"`
	DatabaseID       string `json:"database_id,omitempty"`
	SessionsCount    int    `json:"sessions_count"`
	TerminatedCount  int    `json:"terminated_count"`
	RemainingCount   int    `json:"remaining_count"`
	Message          string `json:"message"`
}

// SessionsClosedPayload represents the payload when all sessions are closed
type SessionsClosedPayload struct {
	ClusterID  string `json:"cluster_id"`
	InfobaseID string `json:"infobase_id"`
	DatabaseID string `json:"database_id,omitempty"`
	Message    string `json:"message"`
}

// ErrorPayload represents an error response
type ErrorPayload struct {
	ClusterID  string `json:"cluster_id,omitempty"`
	InfobaseID string `json:"infobase_id,omitempty"`
	DatabaseID string `json:"database_id,omitempty"`
	Error      string `json:"error"`
	Message    string `json:"message,omitempty"`
}
