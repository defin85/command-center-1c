package credentials

import "context"

type requesterKey struct{}

// WithRequestedBy stores the CC username in context for credentials lookup.
func WithRequestedBy(ctx context.Context, username string) context.Context {
	if username == "" {
		return ctx
	}
	return context.WithValue(ctx, requesterKey{}, username)
}

// RequestedByFromContext returns the CC username stored in context, if any.
func RequestedByFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	value := ctx.Value(requesterKey{})
	if username, ok := value.(string); ok {
		return username
	}
	return ""
}
