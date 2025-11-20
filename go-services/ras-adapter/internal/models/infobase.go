package models

// Infobase represents a 1C infobase
type Infobase struct {
	UUID     string `json:"uuid"`
	Name     string `json:"name"`
	DBMS     string `json:"dbms"`
	DBServer string `json:"db_server"`
	DBName   string `json:"db_name"`

	// Week 2: Lock/Unlock fields
	ScheduledJobsDeny bool `json:"scheduled_jobs_deny"` // Блокировка регламентных заданий
	SessionsDeny      bool `json:"sessions_deny"`        // Блокировка пользователей
}

// InfobasesResponse represents API response with list of infobases
type InfobasesResponse struct {
	Infobases []Infobase `json:"infobases"`
}
