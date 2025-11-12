package eventhandlers

// InstallCommandPayload represents the payload for install extension commands
type InstallCommandPayload struct {
	DatabaseID    string `json:"database_id"`
	Server        string `json:"server"`
	InfobaseName  string `json:"infobase_name"`
	Username      string `json:"username"`
	Password      string `json:"password"`
	ExtensionPath string `json:"extension_path"`
	ExtensionName string `json:"extension_name"`
}

// InstallStartedPayload represents the payload when installation starts
type InstallStartedPayload struct {
	DatabaseID    string `json:"database_id"`
	InfobaseName  string `json:"infobase_name"`
	ExtensionName string `json:"extension_name"`
	Message       string `json:"message"`
}

// InstallSuccessPayload represents the success response for install commands
type InstallSuccessPayload struct {
	DatabaseID      string  `json:"database_id"`
	InfobaseName    string  `json:"infobase_name"`
	ExtensionName   string  `json:"extension_name"`
	DurationSeconds float64 `json:"duration_seconds"`
	Message         string  `json:"message"`
}

// ErrorPayload represents an error response
type ErrorPayload struct {
	DatabaseID   string `json:"database_id,omitempty"`
	InfobaseName string `json:"infobase_name,omitempty"`
	Error        string `json:"error"`
	Message      string `json:"message,omitempty"`
}
