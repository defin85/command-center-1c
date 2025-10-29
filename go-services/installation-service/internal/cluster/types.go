package cluster

import "time"

// InfobaseInfo represents information about a 1C infobase
type InfobaseInfo struct {
	UUID             string `json:"uuid"`
	Name             string `json:"name"`
	Description      string `json:"description"`
	DBMS             string `json:"dbms,omitempty"`
	DBServer         string `json:"db_server,omitempty"`
	DBName           string `json:"db_name,omitempty"`
	DBUser           string `json:"db_user,omitempty"`
	SecurityLevel    int    `json:"security_level,omitempty"`
	ConnectionString string `json:"connection_string,omitempty"`
	Locale           string `json:"locale,omitempty"`
}

// ClusterInfo represents information about a 1C cluster
type ClusterInfo struct {
	UUID string `json:"uuid"`
	Name string `json:"name"`
	Host string `json:"host"`
	Port int    `json:"port"`
}

// InfobaseListResponse represents the response for infobase list request
type InfobaseListResponse struct {
	Status      string         `json:"status"`
	ClusterID   string         `json:"cluster_id"`
	ClusterName string         `json:"cluster_name"`
	TotalCount  int            `json:"total_count"`
	Infobases   []InfobaseInfo `json:"infobases"`
	DurationMs  int64          `json:"duration_ms"`
	Timestamp   string         `json:"timestamp"`
}

// ErrorResponse represents an error response
type ErrorResponse struct {
	Status    string `json:"status"`
	Error     string `json:"error"`
	Message   string `json:"message"`
	Timestamp string `json:"timestamp"`
}

// NewErrorResponse creates a new error response
func NewErrorResponse(errorCode, message string) ErrorResponse {
	return ErrorResponse{
		Status:    "error",
		Error:     errorCode,
		Message:   message,
		Timestamp: time.Now().Format(time.RFC3339),
	}
}
