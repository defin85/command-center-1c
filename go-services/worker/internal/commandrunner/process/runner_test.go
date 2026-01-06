package process

import (
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func TestRun_TruncatesStdoutTail(t *testing.T) {
	bash, err := exec.LookPath("bash")
	if err != nil {
		t.Skip("bash not found")
	}

	res, runErr := Run(context.Background(), Spec{
		ExePath:        bash,
		Args:           []string{"-c", "printf '0123456789'"},
		StdoutMaxBytes: 4,
		StderrMaxBytes: 4,
		WaitDelay:      10 * time.Millisecond,
	})
	if runErr != nil {
		t.Fatalf("unexpected error: %v", runErr)
	}
	if res.Stdout != "6789" {
		t.Fatalf("expected tail stdout %q, got %q", "6789", res.Stdout)
	}
	if !res.StdoutTruncated {
		t.Fatalf("expected stdout truncated=true")
	}
}

func TestRun_TimeoutReturnsCancelledError(t *testing.T) {
	bash, err := exec.LookPath("bash")
	if err != nil {
		t.Skip("bash not found")
	}

	res, runErr := Run(context.Background(), Spec{
		ExePath:   bash,
		Args:      []string{"-c", "sleep 2"},
		Timeout:   50 * time.Millisecond,
		WaitDelay: 50 * time.Millisecond,
	})
	if runErr == nil {
		t.Fatalf("expected error, got nil (res=%+v)", res)
	}
	if !strings.Contains(runErr.Error(), "operation cancelled") {
		t.Fatalf("expected cancelled error, got %v", runErr)
	}
}
