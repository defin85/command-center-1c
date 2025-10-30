package models

// Infobase represents a 1C infobase (database)
type Infobase struct {
	UUID              string `json:"uuid"`
	Name              string `json:"name"`
	Description       string `json:"description,omitempty"`
	DBMS              string `json:"dbms"`
	DBServer          string `json:"db_server"`
	DBName            string `json:"db_name"`
	DBUser            string `json:"db_user,omitempty"`
	SecurityLevel     int    `json:"security_level"`
	DateOffset        int    `json:"date_offset"`
	Locale            string `json:"locale"`
	ConnectionString  string `json:"connection_string,omitempty"`
	ScheduledJobsDeny bool   `json:"scheduled_jobs_denied"`
	SessionsDeny      bool   `json:"sessions_denied"`
	ClusterID         string `json:"cluster_id,omitempty"`
}

// InfobaseListResponse represents the response for GET /infobases
type InfobaseListResponse struct {
	Infobases []Infobase `json:"infobases"`
}
