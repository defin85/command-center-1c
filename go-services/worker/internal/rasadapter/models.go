// Package rasadapter provides HTTP client for communicating with RAS Adapter API.
package rasadapter

// ============================================================================
// Error Types
// ============================================================================

// ErrorResponse represents a structured error from RAS Adapter API.
type ErrorResponse struct {
	Error   string `json:"error"`
	Code    string `json:"code,omitempty"`
	Details string `json:"details,omitempty"`
}

// ============================================================================
// Health Schemas
// ============================================================================

// HealthResponse represents response from health endpoint.
type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
}

// ============================================================================
// Cluster Schemas
// ============================================================================

// Cluster represents a 1C cluster.
type Cluster struct {
	UUID string `json:"uuid"`
	Name string `json:"name"`
	Host string `json:"host"`
	Port int32  `json:"port"`
}

// ClustersResponse represents response from list-clusters endpoint.
type ClustersResponse struct {
	Clusters []*Cluster `json:"clusters"`
	Count    int        `json:"count"`
}

// ClusterResponse represents response from get-cluster endpoint.
type ClusterResponse struct {
	Cluster *Cluster `json:"cluster"`
}

// ============================================================================
// Infobase Schemas
// ============================================================================

// Infobase represents a 1C infobase.
type Infobase struct {
	UUID                string `json:"uuid"`
	Name                string `json:"name"`
	Description         string `json:"description,omitempty"`
	DBMS                string `json:"dbms,omitempty"`
	DBServerName        string `json:"db_server_name,omitempty"`
	DBName              string `json:"db_name,omitempty"`
	SessionsDenied      bool   `json:"sessions_denied"`
	ScheduledJobsDenied bool   `json:"scheduled_jobs_denied"`
	LicenseDistribution bool   `json:"license_distribution"`
}

// InfobasesResponse represents response from list-infobases endpoint.
type InfobasesResponse struct {
	Infobases []*Infobase `json:"infobases"`
	Count     int         `json:"count"`
}

// InfobaseResponse represents response from get-infobase endpoint.
type InfobaseResponse struct {
	Infobase *Infobase `json:"infobase"`
}

// ============================================================================
// Session Schemas
// ============================================================================

// Session represents a 1C session.
type Session struct {
	UUID          string `json:"uuid"`
	InfobaseID    string `json:"infobase_id"`
	UserName      string `json:"user_name"`
	AppID         string `json:"app_id"`
	StartedAt     string `json:"started_at,omitempty"`
	LastActiveAt  string `json:"last_active_at,omitempty"`
	Host          string `json:"host,omitempty"`
	DBProcInfo    string `json:"db_proc_info,omitempty"`
	DBProcTook    int64  `json:"db_proc_took,omitempty"`
	DBProcTookAt  string `json:"db_proc_took_at,omitempty"`
	DurationAll   int64  `json:"duration_all,omitempty"`
	DurationCur   int64  `json:"duration_cur,omitempty"`
	DurationDBCur int64  `json:"duration_db_cur,omitempty"`
}

// SessionsResponse represents response from list-sessions endpoint.
type SessionsResponse struct {
	Sessions []*Session `json:"sessions"`
	Count    int        `json:"count"`
}

// ============================================================================
// Lock/Unlock Schemas
// ============================================================================

// LockInfobaseRequest contains parameters for locking an infobase.
type LockInfobaseRequest struct {
	DBUser     string `json:"db_user,omitempty"`
	DBPassword string `json:"db_password,omitempty"`
}

// UnlockInfobaseRequest contains parameters for unlocking an infobase.
type UnlockInfobaseRequest struct {
	DBUser     string `json:"db_user,omitempty"`
	DBPassword string `json:"db_password,omitempty"`
}

// SuccessResponse represents a generic success response.
type SuccessResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
}

// TerminateSessionsRequest contains session IDs to terminate.
type TerminateSessionsRequest struct {
	SessionIDs []string `json:"session_ids"`
}

// TerminateSessionsResponse contains bulk termination results.
type TerminateSessionsResponse struct {
	TerminatedCount int      `json:"terminated_count"`
	FailedCount     int      `json:"failed_count"`
	FailedSessions  []string `json:"failed_sessions,omitempty"`
}

// ============================================================================
// Session Blocking Schemas (Phase 4 - Context Menu Actions)
// ============================================================================

// BlockSessionsRequest contains parameters for blocking user sessions.
type BlockSessionsRequest struct {
	DeniedFrom     string `json:"denied_from,omitempty"`     // ISO datetime
	DeniedTo       string `json:"denied_to,omitempty"`       // ISO datetime
	DeniedMessage  string `json:"denied_message,omitempty"`  // Message shown to users
	PermissionCode string `json:"permission_code,omitempty"` // Code to allow access
	Parameter      string `json:"parameter,omitempty"`       // Additional parameter
	DBUser         string `json:"db_user,omitempty"`
	DBPassword     string `json:"db_password,omitempty"`
}

// UnblockSessionsRequest contains parameters for unblocking user sessions.
type UnblockSessionsRequest struct {
	DBUser     string `json:"db_user,omitempty"`
	DBPassword string `json:"db_password,omitempty"`
}
