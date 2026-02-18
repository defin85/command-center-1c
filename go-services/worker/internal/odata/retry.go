package odata

import (
	"crypto/rand"
	"math/big"
	"time"
)

const defaultRetryBaseDelay = 500 * time.Millisecond

// ComputeExponentialBackoffWithJitter returns bounded exponential backoff for retry attempt.
// Attempt is 1-based for the first retry after initial request.
func ComputeExponentialBackoffWithJitter(baseDelay time.Duration, attempt int) time.Duration {
	if baseDelay <= 0 {
		baseDelay = defaultRetryBaseDelay
	}
	if attempt <= 0 {
		attempt = 1
	}

	backoff := baseDelay * time.Duration(1<<uint(attempt-1))
	if backoff <= 0 {
		return baseDelay
	}

	jitterBound := backoff / 4
	if jitterBound <= 0 {
		return backoff
	}

	// Add random jitter in [0, jitterBound]. On entropy failures keep deterministic backoff.
	rnd, err := rand.Int(rand.Reader, big.NewInt(int64(jitterBound)+1))
	if err != nil {
		return backoff
	}
	return backoff + time.Duration(rnd.Int64())
}
