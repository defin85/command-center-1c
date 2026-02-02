// go-services/shared/credentials/types.go
package credentials

type IbcmdConnectionOfflineProfile struct {
	Config      string `json:"config,omitempty"`
	Data        string `json:"data,omitempty"`
	DBMS        string `json:"dbms,omitempty"`
	DBServer    string `json:"db_server,omitempty"`
	DBName      string `json:"db_name,omitempty"`
	DBPath      string `json:"db_path,omitempty"`
	Ftext2Data  string `json:"ftext2_data,omitempty"`
	FtextData   string `json:"ftext_data,omitempty"`
	Lock        string `json:"lock,omitempty"`
	LogData     string `json:"log_data,omitempty"`
	OpenidData  string `json:"openid_data,omitempty"`
	SessionData string `json:"session_data,omitempty"`
	SttData     string `json:"stt_data,omitempty"`
	System      string `json:"system,omitempty"`
	Temp        string `json:"temp,omitempty"`
	UsersData   string `json:"users_data,omitempty"`
}

type IbcmdConnectionProfile struct {
	Mode      string                         `json:"mode,omitempty"`
	RemoteURL string                         `json:"remote_url,omitempty"`
	Offline   *IbcmdConnectionOfflineProfile `json:"offline,omitempty"`
}

// DatabaseCredentials represents credentials for a 1C database
type DatabaseCredentials struct {
	DatabaseID string `json:"database_id"`
	// OData credentials
	ODataURL string `json:"odata_url"`
	Username string `json:"username"`
	Password string `json:"password"`
	// Infobase (DESIGNER) credentials, mapped per CC user
	IBUsername string `json:"ib_username,omitempty"`
	IBPassword string `json:"ib_password,omitempty"`
	// DBMS credentials + metadata (offline ibcmd connection)
	DBMS       string `json:"dbms,omitempty"`
	DBServer   string `json:"db_server,omitempty"`
	DBName     string `json:"db_name,omitempty"`
	DBUser     string `json:"db_user,omitempty"`
	DBPassword string `json:"db_password,omitempty"`
	// IBCMD connection profile (driver-level connection flags per database)
	IbcmdConnection *IbcmdConnectionProfile `json:"ibcmd_connection,omitempty"`
	// Legacy fields (for OData)
	Host     string `json:"host"`
	Port     int    `json:"port"`
	BaseName string `json:"base_name"`
	// NEW: Fields for DESIGNER connection (from 1C Server)
	ServerAddress string `json:"server_address"`
	ServerPort    int    `json:"server_port"`
	InfobaseName  string `json:"infobase_name"`
}

// EncryptedCredentialsResponse from Django Orchestrator (encrypted payload)
type EncryptedCredentialsResponse struct {
	EncryptedData     string `json:"encrypted_data"`
	Nonce             string `json:"nonce"`
	ExpiresAt         string `json:"expires_at"`
	EncryptionVersion string `json:"encryption_version"`
}
