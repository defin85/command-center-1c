package models

// Infobase represents a 1C infobase
type Infobase struct {
	// TODO: Define fields based on ras-grpc-gw protobuf schema
	UUID     string `json:"uuid"`
	Name     string `json:"name"`
	DBMS     string `json:"dbms"`
	DBServer string `json:"db_server"`
	DBName   string `json:"db_name"`
}
