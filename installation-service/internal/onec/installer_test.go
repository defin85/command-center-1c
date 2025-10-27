package onec

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
)

func TestSanitizeArgs(t *testing.T) {
	installer := NewInstaller(&config.OneCConfig{})

	args := []string{
		"CONFIG",
		"/Sserver\\base",
		"/NUser",
		"/PSecretPassword123",
		"/LoadCfg", "file.cfe",
		"-Extension", "ODataAutoConfig",
	}

	safe := installer.sanitizeArgs(args)

	// Check that password is masked
	if safe[3] != "/P****" {
		t.Errorf("Expected password to be masked, got %s", safe[3])
	}

	// Check that other arguments are not changed
	if safe[0] != "CONFIG" {
		t.Errorf("Expected 'CONFIG', got %s", safe[0])
	}
	if safe[1] != "/Sserver\\base" {
		t.Errorf("Expected '/Sserver\\base', got %s", safe[1])
	}
	if safe[2] != "/NUser" {
		t.Errorf("Expected '/NUser', got %s", safe[2])
	}
	if safe[4] != "/LoadCfg" {
		t.Errorf("Expected '/LoadCfg', got %s", safe[4])
	}
}

func TestSanitizeArgsMultiplePasswords(t *testing.T) {
	installer := NewInstaller(&config.OneCConfig{})

	args := []string{
		"/PPassword1",
		"somearg",
		"/PPassword2",
	}

	safe := installer.sanitizeArgs(args)

	// Both passwords should be masked
	if safe[0] != "/P****" {
		t.Errorf("Expected first password to be masked, got %s", safe[0])
	}
	if safe[2] != "/P****" {
		t.Errorf("Expected second password to be masked, got %s", safe[2])
	}
	if safe[1] != "somearg" {
		t.Errorf("Expected 'somearg', got %s", safe[1])
	}
}

func TestSanitizeArgsNoPassword(t *testing.T) {
	installer := NewInstaller(&config.OneCConfig{})

	args := []string{
		"CONFIG",
		"/Sserver\\base",
		"/NUser",
		"/LoadCfg",
	}

	safe := installer.sanitizeArgs(args)

	// All arguments should remain the same
	for i, arg := range args {
		if safe[i] != arg {
			t.Errorf("Argument %d changed: expected %s, got %s", i, arg, safe[i])
		}
	}
}

func TestInstallExtensionWithRetryInvalidPath(t *testing.T) {
	// Create installer with invalid 1cv8.exe path
	installer := NewInstaller(&config.OneCConfig{
		PlatformPath:   "invalid_path_to_1cv8.exe",
		TimeoutSeconds: 1,
	})

	req := InstallRequest{
		TaskID:           "test-task-1",
		DatabaseID:       123,
		DatabaseName:     "TestBase",
		ConnectionString: "server1c\\TestBase",
		Username:         "testuser",
		Password:         "testpassword",
		ExtensionPath:    "test.cfe",
		ExtensionName:    "TestExtension",
	}

	ctx := context.Background()

	// This should fail because the path is invalid
	err := installer.InstallExtensionWithRetry(ctx, req, 2, 100*time.Millisecond)

	if err == nil {
		t.Error("Expected error with invalid path, got nil")
	}
}

func TestInstallExtensionWithRetryContextCancellation(t *testing.T) {
	// Create installer with invalid path
	installer := NewInstaller(&config.OneCConfig{
		PlatformPath:   "invalid_path",
		TimeoutSeconds: 10,
	})

	req := InstallRequest{
		TaskID:           "test-task-2",
		DatabaseID:       456,
		DatabaseName:     "TestBase2",
		ConnectionString: "server1c\\TestBase2",
		Username:         "testuser",
		Password:         "testpassword",
		ExtensionPath:    "test.cfe",
		ExtensionName:    "TestExtension",
	}

	// Create context that will be cancelled
	ctx, cancel := context.WithCancel(context.Background())

	// Cancel context after short delay
	go func() {
		time.Sleep(50 * time.Millisecond)
		cancel()
	}()

	// This should fail due to context cancellation
	err := installer.InstallExtensionWithRetry(ctx, req, 10, 200*time.Millisecond)

	if err == nil {
		t.Error("Expected context cancellation error, got nil")
	}

	if err != context.Canceled {
		t.Logf("Got error: %v (expected context.Canceled, but might be wrapped)", err)
	}
}

func TestNewInstaller(t *testing.T) {
	cfg := &config.OneCConfig{
		PlatformPath:   "C:\\Program Files\\1cv8\\bin\\1cv8.exe",
		TimeoutSeconds: 300,
		ServerName:     "server1c",
	}

	installer := NewInstaller(cfg)

	if installer == nil {
		t.Error("NewInstaller returned nil")
	}

	if installer.config != cfg {
		t.Error("Installer config does not match provided config")
	}
}

// BenchmarkSanitizeArgs benchmarks the sanitizeArgs function
func BenchmarkSanitizeArgs(b *testing.B) {
	installer := NewInstaller(&config.OneCConfig{})

	args := []string{
		"CONFIG",
		"/Sserver\\base",
		"/NUser",
		"/PSecretPassword",
		"/LoadCfg", "file.cfe",
		"-Extension", "ODataAutoConfig",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		installer.sanitizeArgs(args)
	}
}
