package models

// Cluster represents a 1C cluster
type Cluster struct {
	UUID              string `json:"uuid"`
	Name              string `json:"name"`
	Host              string `json:"host"`
	Port              int    `json:"port"`
	LifetimeLimit     int    `json:"lifetime_limit"`
	SecurityLevel     int    `json:"security_level"`
	SessionFaultToler int    `json:"session_fault_tolerance_level"`
}

// ClusterListResponse represents the response for GET /clusters
type ClusterListResponse struct {
	Clusters []Cluster `json:"clusters"`
}
