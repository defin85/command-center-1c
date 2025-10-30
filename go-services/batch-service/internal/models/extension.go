package models

// InstallExtensionRequest represents a request to install extension
type InstallExtensionRequest struct {
	Server         string `json:"server" binding:"required"`          // "localhost:1541"
	InfobaseName   string `json:"infobase_name" binding:"required"`   // "dev"
	Username       string `json:"username" binding:"required"`
	Password       string `json:"password" binding:"required"`
	ExtensionPath  string `json:"extension_path" binding:"required"`  // "/path/to/extension.cfe"
	ExtensionName  string `json:"extension_name" binding:"required"`  // "ODataAutoConfig"
	UpdateDBConfig bool   `json:"update_db_config"`                   // Update database configuration
}

// InstallExtensionResponse represents the response from extension installation
type InstallExtensionResponse struct {
	Success         bool    `json:"success"`
	Message         string  `json:"message"`
	DurationSeconds float64 `json:"duration_seconds"`
	Log             string  `json:"log,omitempty"`
}

// BatchInstallRequest represents a request to install extension on multiple bases
type BatchInstallRequest struct {
	Infobases      []InstallExtensionRequest `json:"infobases" binding:"required,min=1"`
	ParallelWorkers int                      `json:"parallel_workers,omitempty"` // default: 10
}

// InstallResult represents the result of a single installation
type InstallResult struct {
	Infobase        string  `json:"infobase"`
	Status          string  `json:"status"` // "success", "failed"
	Error           string  `json:"error,omitempty"`
	DurationSeconds float64 `json:"duration_seconds"`
}

// BatchInstallResponse represents the response from batch installation
type BatchInstallResponse struct {
	Total   int             `json:"total"`
	Success int             `json:"success"`
	Failed  int             `json:"failed"`
	Results []InstallResult `json:"results"`
}
