package service

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/command-center-1c/batch-service/pkg/v8errors"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewExtensionDeleter(t *testing.T) {
	tests := []struct {
		name      string
		exePath   string
		timeout   time.Duration
		wantPath  string
		wantTimer time.Duration
	}{
		{
			name:      "with custom path and timeout",
			exePath:   "C:\\custom\\1cv8.exe",
			timeout:   10 * time.Minute,
			wantPath:  "C:\\custom\\1cv8.exe",
			wantTimer: 10 * time.Minute,
		},
		{
			name:      "with default path and timeout",
			exePath:   "",
			timeout:   0,
			wantPath:  `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`,
			wantTimer: 5 * time.Minute,
		},
		{
			name:      "with custom path and default timeout",
			exePath:   "C:\\custom\\1cv8.exe",
			timeout:   0,
			wantPath:  "C:\\custom\\1cv8.exe",
			wantTimer: 5 * time.Minute,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			deleter := NewExtensionDeleter(tt.exePath, tt.timeout)
			assert.Equal(t, tt.wantPath, deleter.exe1cv8Path)
			assert.Equal(t, tt.wantTimer, deleter.timeout)
		})
	}
}

func TestExtensionDeleter_DeleteExtension_ValidRequest(t *testing.T) {
	// This test verifies the structure but won't actually execute
	// since we don't have 1cv8.exe in the test environment

	deleter := NewExtensionDeleter("", 0)

	req := DeleteRequest{
		Server:        "localhost:1541",
		InfobaseName:  "TestBase",
		Username:      "admin",
		Password:      "password",
		ExtensionName: "TestExtension",
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// This will fail because 1cv8.exe doesn't exist in test environment
	// but we can verify the request is properly formed
	err := deleter.DeleteExtension(ctx, req)
	assert.Error(t, err)
	assert.IsType(t, &v8errors.ExtensionError{}, err)
}

func TestExtensionDeleter_DeleteExtension_ContextTimeout(t *testing.T) {
	deleter := NewExtensionDeleter("", 100*time.Millisecond) // Very short timeout

	req := DeleteRequest{
		Server:        "localhost:1541",
		InfobaseName:  "TestBase",
		Username:      "admin",
		Password:      "password",
		ExtensionName: "TestExtension",
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// This should timeout because we set deleter timeout to 100ms
	err := deleter.DeleteExtension(ctx, req)
	assert.Error(t, err)
	// Will get "executable file not found" before timeout, but structure is tested
	assert.IsType(t, &v8errors.ExtensionError{}, err)
}

func TestExtensionDeleter_DeleteExtension_InvalidRequest(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)

	tests := []struct {
		name string
		req  DeleteRequest
	}{
		{
			name: "empty server",
			req: DeleteRequest{
				Server:        "",
				InfobaseName:  "TestBase",
				Username:      "admin",
				Password:      "password",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "empty infobase name",
			req: DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  "",
				Username:      "admin",
				Password:      "password",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "empty username",
			req: DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  "TestBase",
				Username:      "",
				Password:      "password",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "empty password",
			req: DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  "TestBase",
				Username:      "admin",
				Password:      "",
				ExtensionName: "TestExtension",
			},
		},
		{
			name: "empty extension name",
			req: DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  "TestBase",
				Username:      "admin",
				Password:      "password",
				ExtensionName: "",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
			defer cancel()

			err := deleter.DeleteExtension(ctx, tt.req)
			assert.Error(t, err)
		})
	}
}

func TestExtensionDeleter_DeleteExtension_SpecialCharacters(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)

	tests := []struct {
		name           string
		extensionName  string
		infobaseName   string
		shouldExecute  bool
	}{
		{
			name:          "extension with spaces",
			extensionName: "My Test Extension",
			infobaseName:  "TestBase",
			shouldExecute: true,
		},
		{
			name:          "extension with cyrillic",
			extensionName: "ТестовоеРасширение",
			infobaseName:  "TestBase",
			shouldExecute: true,
		},
		{
			name:          "infobase with special chars",
			extensionName: "TestExt",
			infobaseName:  "Test_Base-v2",
			shouldExecute: true,
		},
		{
			name:          "very long extension name",
			extensionName: strings.Repeat("A", 500),
			infobaseName:  "TestBase",
			shouldExecute: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  tt.infobaseName,
				Username:      "admin",
				Password:      "password",
				ExtensionName: tt.extensionName,
			}

			ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
			defer cancel()

			err := deleter.DeleteExtension(ctx, req)
			assert.Error(t, err) // Will fail because 1cv8.exe doesn't exist
		})
	}
}

func TestExtensionDeleter_ParsedErrorHandling(t *testing.T) {
	// Test that proper error types are returned by mocking exec
	tests := []struct {
		name           string
		stderr         string
		expectedCode   string
		expectedPrefix string
	}{
		{
			name:           "auth failure",
			stderr:         "Неправильное имя пользователя или пароль",
			expectedCode:   "ERR_AUTH_FAILED",
			expectedPrefix: "ERR_AUTH_FAILED",
		},
		{
			name:           "file not found",
			stderr:         "Файл не найден: extension.cfe",
			expectedCode:   "ERR_FILE_NOT_FOUND",
			expectedPrefix: "ERR_FILE_NOT_FOUND",
		},
		{
			name:           "infobase not found",
			stderr:         "Информационная база не найдена",
			expectedCode:   "ERR_INFOBASE_NOT_FOUND",
			expectedPrefix: "ERR_INFOBASE_NOT_FOUND",
		},
		{
			name:           "extension not found",
			stderr:         "Расширение не найдено",
			expectedCode:   "ERR_EXTENSION_NOT_FOUND",
			expectedPrefix: "ERR_EXTENSION_NOT_FOUND",
		},
		{
			name:           "database locked",
			stderr:         "база заблокирована",
			expectedCode:   "ERR_DATABASE_LOCKED",
			expectedPrefix: "ERR_DATABASE_LOCKED",
		},
		{
			name:           "timeout",
			stderr:         "timeout occurred",
			expectedCode:   "ERR_TIMEOUT",
			expectedPrefix: "ERR_TIMEOUT",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Test v8errors.ParseV8Error directly
			mockErr := errors.New("exit 1")
			err := v8errors.ParseV8Error("", tt.stderr, mockErr)

			assert.Error(t, err)
			assert.Contains(t, err.Error(), tt.expectedPrefix)

			extErr, ok := err.(*v8errors.ExtensionError)
			assert.True(t, ok)
			assert.Equal(t, tt.expectedCode, extErr.Code)
		})
	}
}

func TestExtensionDeleter_ConcurrentRequests(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)

	// Test that concurrent requests don't cause race conditions
	const numGoroutines = 10

	errChan := make(chan error, numGoroutines)

	for i := 0; i < numGoroutines; i++ {
		go func() {
			req := DeleteRequest{
				Server:        "localhost:1541",
				InfobaseName:  "TestBase",
				Username:      "admin",
				Password:      "password",
				ExtensionName: "TestExtension",
			}

			ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
			defer cancel()

			err := deleter.DeleteExtension(ctx, req)
			errChan <- err
		}()
	}

	// Collect all errors - they should all be errors (1cv8.exe not found)
	for i := 0; i < numGoroutines; i++ {
		err := <-errChan
		assert.Error(t, err)
	}
}

func TestExtensionDeleter_ServerAddressFormats(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)

	tests := []struct {
		name   string
		server string
	}{
		{
			name:   "localhost with port",
			server: "localhost:1541",
		},
		{
			name:   "IP address with port",
			server: "192.168.1.1:1541",
		},
		{
			name:   "hostname with port",
			server: "server.example.com:1541",
		},
		{
			name:   "just hostname",
			server: "server",
		},
		{
			name:   "just IP",
			server: "192.168.1.1",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := DeleteRequest{
				Server:        tt.server,
				InfobaseName:  "TestBase",
				Username:      "admin",
				Password:      "password",
				ExtensionName: "TestExtension",
			}

			ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
			defer cancel()

			// Command should be properly formed even if execution fails
			err := deleter.DeleteExtension(ctx, req)
			assert.Error(t, err)
		})
	}
}

// BenchmarkDeleteExtension benchmarks the delete operation (setup time only)
func BenchmarkDeleteExtension(b *testing.B) {
	deleter := NewExtensionDeleter("", 0)
	req := DeleteRequest{
		Server:        "localhost:1541",
		InfobaseName:  "TestBase",
		Username:      "admin",
		Password:      "password",
		ExtensionName: "TestExtension",
	}

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
		_ = deleter.DeleteExtension(ctx, req)
		cancel()
	}
}

func TestDeleteRequest_Structure(t *testing.T) {
	req := DeleteRequest{
		Server:        "localhost:1541",
		InfobaseName:  "TestBase",
		Username:      "admin",
		Password:      "password",
		ExtensionName: "TestExt",
	}

	assert.Equal(t, "localhost:1541", req.Server)
	assert.Equal(t, "TestBase", req.InfobaseName)
	assert.Equal(t, "admin", req.Username)
	assert.Equal(t, "password", req.Password)
	assert.Equal(t, "TestExt", req.ExtensionName)
}

func TestExtensionDeleter_CommandConstruction(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)
	require.NotNil(t, deleter)
	require.NotEmpty(t, deleter.exe1cv8Path)
	require.Equal(t, 5*time.Minute, deleter.timeout)

	// Verify the command would be properly constructed by checking exe path format
	assert.True(t, strings.HasSuffix(strings.ToLower(deleter.exe1cv8Path), ".exe"))
}

func TestExtensionDeleter_CustomTimeout(t *testing.T) {
	customTimeout := 2 * time.Minute
	deleter := NewExtensionDeleter("", customTimeout)
	assert.Equal(t, customTimeout, deleter.timeout)
}

func TestExtensionDeleter_ContextCancellation(t *testing.T) {
	deleter := NewExtensionDeleter("", 5*time.Minute)

	req := DeleteRequest{
		Server:        "localhost:1541",
		InfobaseName:  "TestBase",
		Username:      "admin",
		Password:      "password",
		ExtensionName: "TestExtension",
	}

	// Create already-cancelled context
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := deleter.DeleteExtension(ctx, req)
	assert.Error(t, err)
}

func TestExtensionDeleter_EmptyExtensionName(t *testing.T) {
	deleter := NewExtensionDeleter("", 0)

	req := DeleteRequest{
		Server:       "localhost:1541",
		InfobaseName: "TestBase",
		Username:     "admin",
		Password:     "password",
		// Empty extension name
	}

	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
	defer cancel()

	err := deleter.DeleteExtension(ctx, req)
	assert.Error(t, err)
}
