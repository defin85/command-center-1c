package models

// Cluster represents a 1C cluster
type Cluster struct {
	UUID string `json:"uuid"`
	Name string `json:"name"`
	Host string `json:"host"`
	Port int32  `json:"port"`
}

// ClustersResponse represents API response with list of clusters
type ClustersResponse struct {
	Clusters []Cluster `json:"clusters"`
}
