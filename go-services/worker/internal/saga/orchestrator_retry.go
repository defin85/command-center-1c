package saga

// isRetryable checks if an error should be retried.
func isRetryable(err error, policy *RetryPolicy) bool {
	if policy == nil || err == nil {
		return false
	}

	// If no specific retryable errors defined, retry all errors
	if len(policy.RetryableErrors) == 0 {
		return true
	}

	// Check if error matches any retryable error
	for _, retryable := range policy.RetryableErrors {
		if err == retryable {
			return true
		}
	}

	return false
}
