package ibcmdops

import (
	"archive/zip"
	"context"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/models"
)

type fakeCredsFetcher struct {
	creds *credentials.DatabaseCredentials
	err   error
}

func (f *fakeCredsFetcher) Fetch(_ context.Context, _ string) (*credentials.DatabaseCredentials, error) {
	return f.creds, f.err
}

func TestDriverExecute_OnNonZeroExit_PreservesStdoutStderrInData(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("requires a unix-like shell for test helper script")
	}

	tmp := t.TempDir()
	scriptPath := filepath.Join(tmp, "fake-ibcmd.sh")
	script := "#!/bin/sh\n" +
		"echo \"out\"\n" +
		"echo \"err\" 1>&2\n" +
		"exit 2\n"
	if err := os.WriteFile(scriptPath, []byte(script), 0755); err != nil {
		t.Fatalf("failed to write helper script: %v", err)
	}

	t.Setenv("IBCMD_PATH", scriptPath)
	t.Setenv("IBCMD_STORAGE_BACKEND", "local")
	t.Setenv("IBCMD_STORAGE_PATH", filepath.Join(tmp, "storage"))

	driver := NewDriver(&fakeCredsFetcher{
		creds: &credentials.DatabaseCredentials{
			DBMS:       "PostgreSQL",
			DBServer:   "localhost",
			DBName:     "testdb",
			DBUser:     "dbuser",
			DBPassword: "dbpass",
			IBUsername: "user",
			IBPassword: "pass",
		},
	}, nil)

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "ibcmd_cli",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"command_id": "infobase.extension.list",
				"argv":       []string{"infobase", "extension", "list"},
				"stdin":      "",
			},
		},
		Metadata: models.MessageMetadata{CreatedBy: "tester"},
	}

	res, err := driver.Execute(context.Background(), msg, "db-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.Success {
		t.Fatalf("expected success=false")
	}
	if res.ErrorCode != "IBCMD_ERROR" {
		t.Fatalf("expected error_code=IBCMD_ERROR, got %q", res.ErrorCode)
	}
	if res.Data == nil {
		t.Fatalf("expected data to be present on failure")
	}
	if res.Data["exit_code"] != 2 {
		t.Fatalf("expected exit_code=2, got %#v", res.Data["exit_code"])
	}
	if res.Data["stdout"] != "out\n" {
		t.Fatalf("expected stdout to be preserved, got %#v", res.Data["stdout"])
	}
	if res.Data["stderr"] != "err\n" {
		t.Fatalf("expected stderr to be preserved, got %#v", res.Data["stderr"])
	}
}

func TestLoadBusinessConfigurationXML_FromArchive(t *testing.T) {
	tmp := t.TempDir()
	archivePath := filepath.Join(tmp, "Configuration.zip")
	archive, err := os.Create(archivePath)
	if err != nil {
		t.Fatalf("failed to create archive: %v", err)
	}

	zipWriter := zip.NewWriter(archive)
	entry, err := zipWriter.Create("Configuration.xml")
	if err != nil {
		t.Fatalf("failed to create archive entry: %v", err)
	}
	if _, err := entry.Write([]byte("<Configuration><Properties><Name>AccountingEnterprise</Name></Properties></Configuration>")); err != nil {
		t.Fatalf("failed to write archive entry: %v", err)
	}
	if err := zipWriter.Close(); err != nil {
		t.Fatalf("failed to close zip writer: %v", err)
	}
	if err := archive.Close(); err != nil {
		t.Fatalf("failed to close archive file: %v", err)
	}

	xmlPayload, err := loadBusinessConfigurationXML(archivePath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if xmlPayload == "" {
		t.Fatalf("expected xml payload")
	}
	if got := xmlPayload; got != "<Configuration><Properties><Name>AccountingEnterprise</Name></Properties></Configuration>" {
		t.Fatalf("unexpected xml payload: %q", got)
	}
}
