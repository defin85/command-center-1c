package ibcmdops

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
)

func TestExtractDBConfigMissingFields(t *testing.T) {
	_, err := extractDBConfig(map[string]interface{}{}, &credentials.DatabaseCredentials{})
	if err == nil {
		t.Fatalf("expected error for missing fields")
	}
}

func TestResolveStoragePathRejectsTraversal(t *testing.T) {
	base := t.TempDir()
	_, err := resolveLocalPath(base, "../secret.txt")
	if err == nil {
		t.Fatalf("expected error for traversal path")
	}
}

func TestResolveOutputPathUsesStorageBase(t *testing.T) {
	base := t.TempDir()
	path, err := resolveLocalOutputPath("", base, "db-123", ".dt")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if filepath.Ext(path) != ".dt" {
		t.Fatalf("expected .dt extension, got %s", filepath.Ext(path))
	}

	if _, err := os.Stat(filepath.Dir(path)); err != nil {
		t.Fatalf("expected directory to exist: %v", err)
	}

	if path == base {
		t.Fatalf("expected output path to include filename")
	}
}
