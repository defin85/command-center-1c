package ibcmdops

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

func TestExtractDBConfigMissingFields(t *testing.T) {
	_, err := extractDBConfig(map[string]interface{}{}, &credentials.DatabaseCredentials{})
	if err == nil {
		t.Fatalf("expected error for missing fields")
	}
}

func TestBuildRequestIbcmdCliInjectsInfobaseAuthArgs(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv":  []string{"server", "config", "init"},
				"stdin": "hello",
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.Stdin != "hello" {
		t.Fatalf("expected stdin=hello, got %q", req.Stdin)
	}

	expected := []string{"server", "config", "init", "--user=ibuser", "--password=ibpass"}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliReplacesExistingInfobaseAuthArgs(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv": []string{
					"server",
					"config",
					"init",
					"--user=old",
					"--password=old",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := []string{"server", "config", "init", "--user=ibuser", "--password=ibpass"}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliRejectsEmptyArgv(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv": []string{},
			},
		},
	}

	_, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		nil,
	)
	if err == nil {
		t.Fatalf("expected error")
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
