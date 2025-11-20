package models

// Session represents an active 1C session
type Session struct {
	UUID        string `json:"uuid"`         // RAS internal UUID
	SessionID   string `json:"session_id"`   // Legacy alias for UUID
	UserName    string `json:"user_name"`
	Application string `json:"application"`
	StartedAt   string `json:"started_at"`
}

// SessionsResponse represents API response with list of sessions
type SessionsResponse struct {
	Sessions []Session `json:"sessions"`
	Count    int       `json:"count"`
}

// TerminateSessionsRequest represents a request to terminate sessions
type TerminateSessionsRequest struct {
	InfobaseID string   `json:"infobase_id" binding:"required"`
	SessionIDs []string `json:"session_ids" binding:"required,min=1"`
}

// TerminateSessionsResponse represents the response from session termination
type TerminateSessionsResponse struct {
	TerminatedCount int      `json:"terminated_count"`
	FailedSessions  []string `json:"failed_sessions,omitempty"`
}
