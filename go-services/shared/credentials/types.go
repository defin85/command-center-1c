// go-services/shared/credentials/types.go
package credentials

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
