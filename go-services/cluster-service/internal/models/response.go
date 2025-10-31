package models

// ErrorResponse represents an API error response
type ErrorResponse struct {
	Error string `json:"error"`
}

// HealthResponse represents health check response
type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Version string `json:"version"`
}
