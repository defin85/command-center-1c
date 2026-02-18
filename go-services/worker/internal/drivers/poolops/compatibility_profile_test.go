package poolops

import (
	"path/filepath"
	"runtime"
	"testing"
)

func TestRunPublicationCompatibilityGate_GoForApprovedConfiguration(t *testing.T) {
	report, err := runPublicationCompatibilityGate(publicationCompatibilityInput{
		ProfilePath:           testCompatibilityProfilePath(t),
		ConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityMode:     "8.3.23",
		WriteContentType:      "application/json;odata=nometadata",
		ReleaseProfileVersion: "0.4.2-draft",
	})
	if err != nil {
		t.Fatalf("expected compatibility gate pass, got error: %v", err)
	}
	if report.ConfigurationID != "1c-accounting-3.0-standard-odata" {
		t.Fatalf("unexpected configuration id: %q", report.ConfigurationID)
	}
	if report.ProfileVersion != "0.4.2-draft" {
		t.Fatalf("unexpected profile version: %q", report.ProfileVersion)
	}
}

func TestRunPublicationCompatibilityGate_FailsForRejectedContentType(t *testing.T) {
	_, err := runPublicationCompatibilityGate(publicationCompatibilityInput{
		ProfilePath:           testCompatibilityProfilePath(t),
		ConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityMode:     "8.3.23",
		WriteContentType:      "application/json;odata=verbose",
		ReleaseProfileVersion: "0.4.2-draft",
	})
	if err == nil {
		t.Fatal("expected compatibility gate failure for rejected content type")
	}
}

func TestRunPublicationCompatibilityGate_FailsForLegacyModeWithoutPolicy(t *testing.T) {
	_, err := runPublicationCompatibilityGate(publicationCompatibilityInput{
		ProfilePath:           testCompatibilityProfilePath(t),
		ConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityMode:     "8.3.7",
		WriteContentType:      "application/json;odata=nometadata",
		ReleaseProfileVersion: "0.4.2-draft",
	})
	if err == nil {
		t.Fatal("expected compatibility gate failure for legacy mode")
	}
}

func TestRunPublicationCompatibilityGate_FailsForReleaseProfileVersionMismatch(t *testing.T) {
	_, err := runPublicationCompatibilityGate(publicationCompatibilityInput{
		ProfilePath:           testCompatibilityProfilePath(t),
		ConfigurationID:       "1c-accounting-3.0-standard-odata",
		CompatibilityMode:     "8.3.23",
		WriteContentType:      "application/json;odata=nometadata",
		ReleaseProfileVersion: "0.0.0-mismatch",
	})
	if err == nil {
		t.Fatal("expected compatibility gate failure for release profile mismatch")
	}
}

func testCompatibilityProfilePath(t *testing.T) string {
	t.Helper()
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("unable to resolve caller path")
	}
	repoRoot := filepath.Clean(filepath.Join(filepath.Dir(currentFile), "../../../../.."))
	return filepath.Join(
		repoRoot,
		"openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml",
	)
}
