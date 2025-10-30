package models

// Cluster represents a 1C cluster
type Cluster struct {
	// TODO: Define fields based on ras-grpc-gw protobuf schema
	UUID string `json:"uuid"`
	Name string `json:"name"`
	Host string `json:"host"`
	Port int    `json:"port"`
}
