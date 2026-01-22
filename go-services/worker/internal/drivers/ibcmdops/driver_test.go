package ibcmdops

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

type fakeStorage struct {
	resolveInputRequested string
	resolveInputResolved  string
	resolveInputCleanup   func()
	resolveInputErr       error

	prepareRequestedPath string
	prepareOutputPath    string
	prepareArtifactPath  string
	prepareFinalize      func(ctx context.Context) error
	prepareCleanup       func()
	prepareErr           error
}

func (s *fakeStorage) ResolveInput(_ context.Context, inputPath string) (string, func(), error) {
	s.resolveInputRequested = inputPath
	if s.resolveInputCleanup == nil {
		s.resolveInputCleanup = func() {}
	}
	return s.resolveInputResolved, s.resolveInputCleanup, s.resolveInputErr
}

func (s *fakeStorage) PrepareOutput(_ context.Context, outputPath, _ string, _ string) (string, string, func(ctx context.Context) error, func(), error) {
	s.prepareRequestedPath = outputPath
	if s.prepareFinalize == nil {
		s.prepareFinalize = func(context.Context) error { return nil }
	}
	if s.prepareCleanup == nil {
		s.prepareCleanup = func() {}
	}
	return s.prepareOutputPath, s.prepareArtifactPath, s.prepareFinalize, s.prepareCleanup, s.prepareErr
}

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
				"argv":  []string{"infobase", "dump"},
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

	expected := []string{"infobase", "dump", "--user=ibuser", "--password=ibpass"}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 2 {
		t.Fatalf("expected 2 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["target_ref"] != "flag:--user" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[1]["target_ref"] != "flag:--password" || req.RuntimeBindings[1]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[1])
	}
}

func TestBuildRequestIbcmdCliReplacesExistingInfobaseAuthArgs(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"argv": []string{
					"infobase",
					"restore",
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
	expected := []string{"infobase", "restore", "--user=ibuser", "--password=ibpass"}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 2 {
		t.Fatalf("expected 2 runtime bindings, got %#v", req.RuntimeBindings)
	}
}

func TestBuildRequestIbcmdCliRecordsNormalizeAndSkipsUnsupportedAuth(t *testing.T) {
	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
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
	expected := []string{"infobase", "config", "extension", "list"}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
	if len(req.RuntimeBindings) != 2 {
		t.Fatalf("expected 2 runtime bindings, got %#v", req.RuntimeBindings)
	}
	if req.RuntimeBindings[0]["source_ref"] != "worker.normalizeIbcmdArgv" || req.RuntimeBindings[0]["status"] != "applied" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[0])
	}
	if req.RuntimeBindings[1]["target_ref"] != "infobase_auth" || req.RuntimeBindings[1]["status"] != "skipped" {
		t.Fatalf("unexpected runtime binding: %#v", req.RuntimeBindings[1])
	}
	if req.RuntimeBindings[1]["reason"] != "unsupported_for_command" {
		t.Fatalf("unexpected runtime binding reason: %#v", req.RuntimeBindings[1])
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

func TestBuildRequestIbcmdCliInfobaseDumpUsesStoragePrepareOutput(t *testing.T) {
	store := &fakeStorage{
		prepareOutputPath:   "/tmp/out.dt",
		prepareArtifactPath: "s3://bucket/out.dt",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.dump",
				"argv": []string{
					"infobase",
					"dump",
					"--dbms=PostgreSQL",
					"--db-pwd=secret",
					"db-1/backup.dt",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if req.ArtifactPath != "s3://bucket/out.dt" {
		t.Fatalf("expected artifact path, got %q", req.ArtifactPath)
	}
	if store.prepareRequestedPath != "db-1/backup.dt" {
		t.Fatalf("expected PrepareOutput requested path to match argv positional, got %q", store.prepareRequestedPath)
	}
	expected := []string{
		"infobase",
		"dump",
		"--dbms=PostgreSQL",
		"--db-pwd=secret",
		"/tmp/out.dt",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}
}

func TestBuildRequestIbcmdCliInfobaseRestoreUsesStorageResolveInput(t *testing.T) {
	cleanupCalled := false
	store := &fakeStorage{
		resolveInputCleanup: func() { cleanupCalled = true },
		resolveInputResolved: "/tmp/input.dt",
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.restore",
				"argv": []string{
					"infobase",
					"restore",
					"--dbms=PostgreSQL",
					"--db-pwd=secret",
					"s3://bucket/db-1/input.dt",
				},
			},
		},
	}

	req, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		store,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if req == nil {
		t.Fatalf("expected request")
	}
	if store.resolveInputRequested != "s3://bucket/db-1/input.dt" {
		t.Fatalf("expected ResolveInput requested path, got %q", store.resolveInputRequested)
	}
	expected := []string{
		"infobase",
		"restore",
		"--dbms=PostgreSQL",
		"--db-pwd=secret",
		"/tmp/input.dt",
		"--user=ibuser",
		"--password=ibpass",
	}
	if !reflect.DeepEqual(req.Args, expected) {
		t.Fatalf("unexpected args: %#v", req.Args)
	}

	if req.inputCleanup == nil {
		t.Fatalf("expected input cleanup")
	}
	req.inputCleanup()
	if !cleanupCalled {
		t.Fatalf("expected cleanup to be called")
	}
}

func TestBuildRequestIbcmdCliInfobaseDumpRejectsArtifactOutput(t *testing.T) {
	store := &fakeStorage{prepareOutputPath: "/tmp/out.dt", prepareArtifactPath: "s3://bucket/out.dt"}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.dump",
				"argv": []string{
					"infobase",
					"dump",
					"artifact://out.dt",
				},
			},
		},
	}

	_, err := buildRequest(
		context.Background(),
		msg,
		"db-1",
		&credentials.DatabaseCredentials{IBUsername: "ibuser", IBPassword: "ibpass"},
		store,
	)
	if err == nil {
		t.Fatalf("expected error")
	}
	if !strings.Contains(err.Error(), "artifact:// output is not supported") {
		t.Fatalf("unexpected error: %v", err)
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
