// Package v2 implements action-based REST API for RAS Adapter.
//
// This API follows Kontur/Stripe style with hybrid parameter approach:
//   - Query params: routing identifiers (cluster_id, infobase_id, session_id)
//   - Request body: operation details (arrays, complex structures)
//
// All endpoints are versioned under /api/v2 prefix.
//
// Architecture:
//   - handlers_cluster.go: Cluster discovery endpoints (2 handlers)
//   - handlers_infobase.go: Infobase CRUD + lock/unlock operations (8 handlers)
//   - handlers_session.go: Session management (3 handlers)
//   - validation.go: Validation helpers and middleware
//   - types.go: Request/Response type definitions
//   - routes.go: Route registration
package v2

import (
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
)

// Request types for v2 API

// BlockSessionsRequest contains parameters for blocking user sessions
type BlockSessionsRequest struct {
	DeniedFrom     *time.Time `json:"denied_from" example:"2025-11-23T12:00:00Z"`
	DeniedTo       *time.Time `json:"denied_to" example:"2025-11-23T18:00:00Z"`
	DeniedMessage  string     `json:"denied_message" example:"Database maintenance in progress"`
	PermissionCode string     `json:"permission_code" example:"MaintenanceMode"`
	Parameter      string     `json:"parameter" example:"scheduled_maintenance"`
	DBUser         string     `json:"db_user" example:"admin"`
	DBPassword     string     `json:"db_password" example:"password"`
}

// UnblockSessionsRequest contains parameters for unblocking user sessions
type UnblockSessionsRequest struct {
	DBUser     string `json:"db_user" example:"admin"`
	DBPassword string `json:"db_password" example:"password"`
}

// CreateInfobaseRequest contains parameters for creating a new infobase
type CreateInfobaseRequest struct {
	Name                string `json:"name" binding:"required" example:"TestDatabase"`
	Description         string `json:"description" example:"Test database for development"`
	DBMS                string `json:"dbms" binding:"required" example:"MSSQLServer"`
	DBServerName        string `json:"db_server_name" example:"localhost"`
	DBName              string `json:"db_name" binding:"required" example:"testdb"`
	DBUser              string `json:"db_user" example:"sa"`
	DBPassword          string `json:"db_password" example:"password"`
	Locale              string `json:"locale" example:"ru_RU"`
	DateOffset          int    `json:"date_offset" example:"2000"`
	LicenseDistribution bool   `json:"license_distribution" example:"true"`
	ScheduledJobsDenied bool   `json:"scheduled_jobs_denied" example:"false"`
	SessionsDenied      bool   `json:"sessions_denied" example:"false"`
}

// DropInfobaseRequest contains parameters for dropping an infobase
type DropInfobaseRequest struct {
	DropDatabase bool `json:"drop_database" example:"true"`
}

// LockInfobaseRequest contains optional DB credentials for locking
type LockInfobaseRequest struct {
	DBUser     string `json:"db_user" example:"admin"`
	DBPassword string `json:"db_password" example:"password"`
}

// UnlockInfobaseRequest contains optional DB credentials for unlocking
type UnlockInfobaseRequest struct {
	DBUser     string `json:"db_user" example:"admin"`
	DBPassword string `json:"db_password" example:"password"`
}

// TerminateSessionsRequest contains array of session IDs to terminate
type TerminateSessionsRequest struct {
	SessionIDs []string `json:"session_ids" binding:"required,min=1" example:"a1b2c3d4-e5f6-7890-abcd-ef1234567890,f9e8d7c6-b5a4-3210-9876-543210fedcba"`
}

// Response types for v2 API

// SuccessResponse is a generic success response
type SuccessResponse struct {
	Success bool   `json:"success" example:"true"`
	Message string `json:"message,omitempty" example:"Operation completed successfully"`
}

// ErrorResponse is a generic error response
type ErrorResponse struct {
	Error   string `json:"error" example:"cluster_id is required"`
	Code    string `json:"code,omitempty" example:"MISSING_PARAMETER"`
	Details string `json:"details,omitempty" example:"validation failed"`
}

// ClustersResponse contains list of clusters
type ClustersResponse struct {
	Clusters []*models.Cluster `json:"clusters"`
	Count    int               `json:"count" example:"1"`
}

// ClusterResponse contains single cluster data
type ClusterResponse struct {
	Cluster *models.Cluster `json:"cluster"`
}

// InfobasesResponse contains list of infobases
type InfobasesResponse struct {
	Infobases []*models.Infobase `json:"infobases"`
	Count     int                `json:"count" example:"5"`
}

// InfobaseResponse contains single infobase data
type InfobaseResponse struct {
	Infobase *models.Infobase `json:"infobase"`
}

// CreateInfobaseResponse contains newly created infobase ID
type CreateInfobaseResponse struct {
	Success    bool   `json:"success" example:"true"`
	InfobaseID string `json:"infobase_id" example:"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`
	Message    string `json:"message" example:"Infobase created successfully"`
}

// SessionsResponse contains list of sessions
type SessionsResponse struct {
	Sessions []*models.Session `json:"sessions"`
	Count    int               `json:"count" example:"10"`
}

// TerminateSessionResponse contains termination result
type TerminateSessionResponse struct {
	Success   bool   `json:"success" example:"true"`
	Message   string `json:"message" example:"Session terminated successfully"`
	SessionID string `json:"session_id,omitempty" example:"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`
}

// TerminateSessionsResponse contains bulk termination results
type TerminateSessionsResponse struct {
	TerminatedCount int      `json:"terminated_count" example:"8"`
	FailedCount     int      `json:"failed_count" example:"2"`
	FailedSessions  []string `json:"failed_sessions,omitempty" example:"session-1,session-2"`
}
