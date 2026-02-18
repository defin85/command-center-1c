package odata

import (
	"testing"
	"time"
)

func TestComputeExponentialBackoffWithJitter_UsesDefaultsForInvalidInput(t *testing.T) {
	wait := ComputeExponentialBackoffWithJitter(0, 0)
	if wait < defaultRetryBaseDelay {
		t.Fatalf("expected wait >= defaultRetryBaseDelay, got %s", wait)
	}
}

func TestComputeExponentialBackoffWithJitter_GrowsByAttempt(t *testing.T) {
	base := 200 * time.Millisecond
	wait1 := ComputeExponentialBackoffWithJitter(base, 1)
	wait2 := ComputeExponentialBackoffWithJitter(base, 2)
	wait3 := ComputeExponentialBackoffWithJitter(base, 3)

	if wait1 < base {
		t.Fatalf("expected wait1 >= %s, got %s", base, wait1)
	}
	if wait2 < base*2 {
		t.Fatalf("expected wait2 >= %s, got %s", base*2, wait2)
	}
	if wait3 < base*4 {
		t.Fatalf("expected wait3 >= %s, got %s", base*4, wait3)
	}
}

func TestComputeExponentialBackoffWithJitter_RespectsJitterUpperBound(t *testing.T) {
	base := 200 * time.Millisecond
	wait := ComputeExponentialBackoffWithJitter(base, 3) // backoff=800ms, jitter<=200ms
	min := 800 * time.Millisecond
	max := 1000 * time.Millisecond

	if wait < min {
		t.Fatalf("expected wait >= %s, got %s", min, wait)
	}
	if wait > max {
		t.Fatalf("expected wait <= %s, got %s", max, wait)
	}
}
