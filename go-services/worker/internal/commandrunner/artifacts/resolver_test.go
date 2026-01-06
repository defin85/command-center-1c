package artifacts

import (
	"context"
	"os"
	"strings"
	"testing"
)

func TestBaseDir_CLI_UsesExplicitEnv(t *testing.T) {
	t.Setenv("CLI_ARTIFACT_TMP_DIR", "/tmp/cc1c-cli-test")
	t.Setenv("IBCMD_ARTIFACT_TMP_DIR", "")
	got := BaseDir(DriverCLI)
	if got != "/tmp/cc1c-cli-test" {
		t.Fatalf("expected CLI base dir from env, got %q", got)
	}
}

func TestBaseDir_IBCMD_FallsBackToCliEnv(t *testing.T) {
	t.Setenv("CLI_ARTIFACT_TMP_DIR", "/tmp/cc1c-cli-fallback")
	t.Setenv("IBCMD_ARTIFACT_TMP_DIR", "")
	got := BaseDir(DriverIBCMD)
	if got != "/tmp/cc1c-cli-fallback" {
		t.Fatalf("expected IBCMD base dir from CLI env, got %q", got)
	}
}

func TestToWindowsPath_ConvertsMntPaths(t *testing.T) {
	got := ToWindowsPath("/mnt/c/Program Files/1cv8")
	if got != "C:\\Program Files\\1cv8" {
		t.Fatalf("expected converted path, got %q", got)
	}
}

func TestFromWindowsPath_ConvertsWindowsPaths(t *testing.T) {
	got := FromWindowsPath("C:\\Temp\\file.txt")
	if got != "/mnt/c/Temp/file.txt" {
		t.Fatalf("expected converted path, got %q", got)
	}
}

func TestResolveArgs_NoArtifacts_ReturnsNoopCleanup(t *testing.T) {
	t.Setenv("MINIO_ENDPOINT", "")
	t.Setenv("MINIO_ACCESS_KEY", "")
	t.Setenv("MINIO_SECRET_KEY", "")
	args := []string{"--file=/tmp/a.txt", "x"}
	resolved, cleanup, err := ResolveArgs(context.Background(), args, Meta{Driver: DriverCLI, OperationID: "op", DatabaseID: "db"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(resolved) != len(args) {
		t.Fatalf("expected same args length, got %d", len(resolved))
	}
	for i := range args {
		if resolved[i] != args[i] {
			t.Fatalf("expected arg %d unchanged, got %q", i, resolved[i])
		}
	}
	if cleanup == nil {
		t.Fatalf("expected non-nil cleanup")
	}
	cleanup()
}

func TestResolveArgs_InvalidArtifactKey_ReturnsError(t *testing.T) {
	// Ensure we fail before any download attempt due to empty key.
	t.Setenv("MINIO_ENDPOINT", "minio:9000")
	t.Setenv("MINIO_ACCESS_KEY", "x")
	t.Setenv("MINIO_SECRET_KEY", "y")
	t.Setenv("MINIO_BUCKET", "cc1c-artifacts")

	resolved, cleanup, err := ResolveArgs(context.Background(), []string{ArtifactPrefix}, Meta{Driver: DriverCLI, OperationID: "op", DatabaseID: "db"})
	if cleanup == nil {
		t.Fatalf("expected non-nil cleanup")
	}
	cleanup()
	if err == nil {
		t.Fatalf("expected error, got nil (resolved=%v)", resolved)
	}
}

func TestIsWindowsInterop_DetectsDriveFromEnv(t *testing.T) {
	t.Setenv("PLATFORM_1C_BIN_PATH", "/mnt/c/Program Files/1cv8")
	if !IsWindowsInterop(DriverCLI) {
		t.Fatalf("expected windows interop true")
	}
	t.Setenv("PLATFORM_1C_BIN_PATH", "")
	if IsWindowsInterop(DriverCLI) {
		t.Fatalf("expected windows interop false")
	}
}

func TestBaseDir_UsesTempDirFallback(t *testing.T) {
	t.Setenv("CLI_ARTIFACT_TMP_DIR", "")
	t.Setenv("PLATFORM_1C_BIN_PATH", "")
	got := BaseDir(DriverCLI)
	if got == "" {
		t.Fatalf("expected non-empty base dir")
	}
	// should be under os.TempDir when no envs and no windows interop
	if !strings.HasPrefix(got, os.TempDir()) {
		t.Fatalf("expected base dir under os.TempDir, got %q", got)
	}
}
