package executor

// Task represents an installation task received from Redis queue
type Task struct {
	TaskID           string `json:"task_id"`
	DatabaseID       int    `json:"database_id"`
	DatabaseName     string `json:"database_name"`
	ConnectionString string `json:"connection_string"`
	Username         string `json:"username"`
	Password         string `json:"password"`
	ExtensionPath    string `json:"extension_path"`
	ExtensionName    string `json:"extension_name"`
	RetryCount       int    `json:"retry_count"`
	CreatedAt        string `json:"created_at"`
}

// TaskResult represents the result of task execution
type TaskResult struct {
	TaskID          string
	DatabaseID      int
	DatabaseName    string
	Status          string // "success" or "failed"
	DurationSeconds int
	ErrorMessage    string
}
