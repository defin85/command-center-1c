package eventhandlers

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Mock Redis client for testing
type mockRedisClient struct {
	setNXCalled bool
	setNXResult bool
	setNXError  error
}

func (m *mockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	m.setNXCalled = true
	cmd := redis.NewBoolCmd(ctx)
	if m.setNXError != nil {
		cmd.SetErr(m.setNXError)
	} else {
		cmd.SetVal(m.setNXResult)
	}
	return cmd
}

func TestContainsError(t *testing.T) {
	tests := []struct {
		name   string
		output string
		want   bool
	}{
		{
			name:   "empty output",
			output: "",
			want:   false,
		},
		{
			name:   "success output",
			output: "Configuration loaded successfully",
			want:   false,
		},
		{
			name:   "error keyword",
			output: "Error: Failed to load configuration",
			want:   true,
		},
		{
			name:   "russian error",
			output: "Ошибка: Не удалось загрузить конфигурацию",
			want:   true,
		},
		{
			name:   "failed keyword",
			output: "Operation failed",
			want:   true,
		},
		{
			name:   "exception keyword",
			output: "Exception occurred during processing",
			want:   true,
		},
		{
			name:   "critical error",
			output: "Critical error in database",
			want:   true,
		},
		{
			name:   "fatal error",
			output: "Fatal: cannot continue",
			want:   true,
		},
		{
			name:   "result failed",
			output: "Result: Failed",
			want:   true,
		},
		{
			name:   "невозможно",
			output: "Невозможно выполнить операцию",
			want:   true,
		},
		{
			name:   "не удалось",
			output: "Не удалось подключиться к базе",
			want:   true,
		},
		{
			name:   "mixed case error",
			output: "Some text\nERROR: Database connection failed\nMore text",
			want:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ContainsError(tt.output)
			if got != tt.want {
				t.Errorf("ContainsError() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestExtractError(t *testing.T) {
	tests := []struct {
		name   string
		output string
		want   string
	}{
		{
			name:   "empty output",
			output: "",
			want:   "unknown error",
		},
		{
			name:   "error line",
			output: "Some text\nError: Failed to connect\nMore text",
			want:   "Error: Failed to connect",
		},
		{
			name:   "russian error",
			output: "Текст\nОшибка: Соединение прервано\nДругой текст",
			want:   "Ошибка: Соединение прервано",
		},
		{
			name:   "failed line",
			output: "Step 1 completed\nFailed: Step 2\nSkipping step 3",
			want:   "Failed: Step 2",
		},
		{
			name:   "no error indicator",
			output: "Line 1\nLine 2\nLine 3",
			want:   "Line 1; Line 2; Line 3",
		},
		{
			name:   "multiple error lines",
			output: "Error: First error\nWarning: Something\nError: Second error",
			want:   "Error: First error",
		},
		{
			name:   "whitespace lines",
			output: "   \nError: Test error\n   \n",
			want:   "Error: Test error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ExtractError(tt.output)
			if got != tt.want {
				t.Errorf("ExtractError() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestParseProgressPercent(t *testing.T) {
	tests := []struct {
		name string
		line string
		want int
	}{
		{
			name: "percentage format",
			line: "Processing: 50%",
			want: 50,
		},
		{
			name: "percentage at start",
			line: "25% completed",
			want: 25,
		},
		{
			name: "percentage at end",
			line: "Loading configuration... 75%",
			want: 75,
		},
		{
			name: "progress of format",
			line: "Progress: 30 of 100",
			want: 30,
		},
		{
			name: "russian progress",
			line: "Прогресс: 45 из 100",
			want: 45,
		},
		{
			name: "progress bar with percentage",
			line: "[==========          ] 50%",
			want: 50,
		},
		{
			name: "no percentage",
			line: "Loading configuration...",
			want: -1,
		},
		{
			name: "invalid percentage over 100",
			line: "150%",
			want: -1,
		},
		{
			name: "100 percent",
			line: "Done: 100%",
			want: 100,
		},
		{
			name: "zero percent",
			line: "Starting: 0%",
			want: 0,
		},
		{
			name: "complex progress",
			line: "Downloading files: 50 of 200 files",
			want: 25,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ParseProgressPercent(tt.line)
			if got != tt.want {
				t.Errorf("ParseProgressPercent() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestParsePhase(t *testing.T) {
	tests := []struct {
		name string
		line string
		want string
	}{
		{
			name: "loading config english",
			line: "Loading configuration from file...",
			want: "loading_config",
		},
		{
			name: "loading config russian",
			line: "Загрузка конфигурации из файла...",
			want: "loading_config",
		},
		{
			name: "dumping config",
			line: "Dumping configuration to directory",
			want: "dumping_config",
		},
		{
			name: "updating config",
			line: "Updating configuration database",
			want: "updating_config",
		},
		{
			name: "restructuring",
			line: "Database restructuring in progress",
			want: "restructuring",
		},
		{
			name: "checking",
			line: "Checking configuration validity",
			want: "checking",
		},
		{
			name: "compiling",
			line: "Compiling modules...",
			want: "compiling",
		},
		{
			name: "loading extension",
			line: "Loading extension from file",
			want: "loading_extension",
		},
		{
			name: "removing extension",
			line: "Removing extension from database",
			want: "removing_extension",
		},
		{
			name: "exporting metadata",
			line: "Exporting metadata to XML",
			want: "exporting_metadata",
		},
		{
			name: "updating database",
			line: "Updating database structure",
			want: "updating_database",
		},
		{
			name: "synchronizing",
			line: "Synchronizing with server",
			want: "synchronizing",
		},
		{
			name: "preparing",
			line: "Preparing operation...",
			want: "preparing",
		},
		{
			name: "finalizing",
			line: "Finalizing changes",
			want: "finalizing",
		},
		{
			name: "starting",
			line: "Starting designer mode",
			want: "starting",
		},
		{
			name: "initializing",
			line: "Initializing connection",
			want: "initializing",
		},
		{
			name: "no phase",
			line: "Some random text",
			want: "",
		},
		{
			name: "russian compilation",
			line: "Компиляция модулей",
			want: "compiling",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ParsePhase(tt.line)
			if got != tt.want {
				t.Errorf("ParsePhase() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestIsSuccess(t *testing.T) {
	tests := []struct {
		name     string
		output   string
		exitCode int
		want     bool
	}{
		{
			name:     "success with exit code 0",
			output:   "Operation completed successfully",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "result success",
			output:   "Result: Success",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "done message",
			output:   "Done",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "russian success",
			output:   "Успешно выполнено",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "non-zero exit code",
			output:   "Operation completed successfully",
			exitCode: 1,
			want:     false,
		},
		{
			name:     "error in output",
			output:   "Error: Failed to complete",
			exitCode: 0,
			want:     false,
		},
		{
			name:     "no explicit success but no error",
			output:   "Processing completed\nAll files processed",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "completed successfully",
			output:   "Completed successfully",
			exitCode: 0,
			want:     true,
		},
		{
			name:     "завершено успешно",
			output:   "Завершено успешно",
			exitCode: 0,
			want:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsSuccess(tt.output, tt.exitCode)
			if got != tt.want {
				t.Errorf("IsSuccess() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGetStringOption(t *testing.T) {
	tests := []struct {
		name         string
		options      map[string]interface{}
		key          string
		defaultValue string
		want         string
	}{
		{
			name: "string value exists",
			options: map[string]interface{}{
				"key": "value",
			},
			key:          "key",
			defaultValue: "default",
			want:         "value",
		},
		{
			name:         "key not found",
			options:      map[string]interface{}{},
			key:          "missing",
			defaultValue: "default",
			want:         "default",
		},
		{
			name:         "nil options",
			options:      nil,
			key:          "key",
			defaultValue: "default",
			want:         "default",
		},
		{
			name: "empty string value",
			options: map[string]interface{}{
				"key": "",
			},
			key:          "key",
			defaultValue: "default",
			want:         "default",
		},
		{
			name: "non-string value",
			options: map[string]interface{}{
				"key": 123,
			},
			key:          "key",
			defaultValue: "default",
			want:         "default",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := GetStringOption(tt.options, tt.key, tt.defaultValue)
			if got != tt.want {
				t.Errorf("GetStringOption() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGetIntOption(t *testing.T) {
	tests := []struct {
		name         string
		options      map[string]interface{}
		key          string
		defaultValue int
		want         int
	}{
		{
			name: "int value exists",
			options: map[string]interface{}{
				"key": 42,
			},
			key:          "key",
			defaultValue: 10,
			want:         42,
		},
		{
			name: "float64 value (JSON)",
			options: map[string]interface{}{
				"key": 42.0,
			},
			key:          "key",
			defaultValue: 10,
			want:         42,
		},
		{
			name:         "key not found",
			options:      map[string]interface{}{},
			key:          "missing",
			defaultValue: 10,
			want:         10,
		},
		{
			name:         "nil options",
			options:      nil,
			key:          "key",
			defaultValue: 10,
			want:         10,
		},
		{
			name: "non-numeric value",
			options: map[string]interface{}{
				"key": "not a number",
			},
			key:          "key",
			defaultValue: 10,
			want:         10,
		},
		{
			name: "zero value",
			options: map[string]interface{}{
				"key": 0,
			},
			key:          "key",
			defaultValue: 10,
			want:         0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := GetIntOption(tt.options, tt.key, tt.defaultValue)
			if got != tt.want {
				t.Errorf("GetIntOption() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGetBoolOption(t *testing.T) {
	tests := []struct {
		name         string
		options      map[string]interface{}
		key          string
		defaultValue bool
		want         bool
	}{
		{
			name: "bool true value",
			options: map[string]interface{}{
				"key": true,
			},
			key:          "key",
			defaultValue: false,
			want:         true,
		},
		{
			name: "bool false value",
			options: map[string]interface{}{
				"key": false,
			},
			key:          "key",
			defaultValue: true,
			want:         false,
		},
		{
			name:         "key not found",
			options:      map[string]interface{}{},
			key:          "missing",
			defaultValue: true,
			want:         true,
		},
		{
			name:         "nil options",
			options:      nil,
			key:          "key",
			defaultValue: true,
			want:         true,
		},
		{
			name: "non-bool value",
			options: map[string]interface{}{
				"key": "true",
			},
			key:          "key",
			defaultValue: false,
			want:         false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := GetBoolOption(tt.options, tt.key, tt.defaultValue)
			if got != tt.want {
				t.Errorf("GetBoolOption() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCheckIdempotency(t *testing.T) {
	ctx := context.Background()
	logger := zap.NewNop()

	t.Run("empty correlation ID", func(t *testing.T) {
		isFirst, err := CheckIdempotency(ctx, nil, "", "test-operation", logger)
		if err != nil {
			t.Errorf("CheckIdempotency() error = %v, want nil", err)
		}
		if !isFirst {
			t.Error("CheckIdempotency() should return true for empty correlation ID")
		}
	})

	t.Run("nil redis client", func(t *testing.T) {
		isFirst, err := CheckIdempotency(ctx, nil, "corr-123", "test-operation", logger)
		if err != nil {
			t.Errorf("CheckIdempotency() error = %v, want nil", err)
		}
		if !isFirst {
			t.Error("CheckIdempotency() should return true when Redis client is nil")
		}
	})

	t.Run("first time processing", func(t *testing.T) {
		mockClient := &mockRedisClient{
			setNXResult: true,
		}
		isFirst, err := CheckIdempotency(ctx, mockClient, "corr-123", "test-operation", logger)
		if err != nil {
			t.Errorf("CheckIdempotency() error = %v, want nil", err)
		}
		if !isFirst {
			t.Error("CheckIdempotency() should return true for first time processing")
		}
		if !mockClient.setNXCalled {
			t.Error("SetNX should be called")
		}
	})

	t.Run("duplicate processing", func(t *testing.T) {
		mockClient := &mockRedisClient{
			setNXResult: false,
		}
		isFirst, err := CheckIdempotency(ctx, mockClient, "corr-123", "test-operation", logger)
		if err != nil {
			t.Errorf("CheckIdempotency() error = %v, want nil", err)
		}
		if isFirst {
			t.Error("CheckIdempotency() should return false for duplicate processing")
		}
	})

	t.Run("redis error - fail open", func(t *testing.T) {
		mockClient := &mockRedisClient{
			setNXError: context.DeadlineExceeded,
		}
		isFirst, err := CheckIdempotency(ctx, mockClient, "corr-123", "test-operation", logger)
		if err != nil {
			t.Errorf("CheckIdempotency() error = %v, want nil", err)
		}
		if !isFirst {
			t.Error("CheckIdempotency() should fail-open and return true on Redis error")
		}
	})
}
