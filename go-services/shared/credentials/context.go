package credentials

import "context"

type requesterKey struct{}

type ibAuthStrategyKey struct{}

type dbmsAuthStrategyKey struct{}

// WithRequestedBy stores the CC username in context for credentials lookup.
func WithRequestedBy(ctx context.Context, username string) context.Context {
	if username == "" {
		return ctx
	}
	return context.WithValue(ctx, requesterKey{}, username)
}

// WithIbAuthStrategy stores infobase auth strategy (actor|service|none) in context for credentials lookup.
func WithIbAuthStrategy(ctx context.Context, strategy string) context.Context {
	if ctx == nil {
		return ctx
	}
	s := strategy
	if s == "" {
		return ctx
	}
	return context.WithValue(ctx, ibAuthStrategyKey{}, s)
}

// WithDbmsAuthStrategy stores DBMS auth strategy (actor|service) in context for credentials lookup.
func WithDbmsAuthStrategy(ctx context.Context, strategy string) context.Context {
	if ctx == nil {
		return ctx
	}
	s := strategy
	if s == "" {
		return ctx
	}
	return context.WithValue(ctx, dbmsAuthStrategyKey{}, s)
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

// IbAuthStrategyFromContext returns the stored infobase auth strategy (actor|service|none), if any.
func IbAuthStrategyFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	value := ctx.Value(ibAuthStrategyKey{})
	if s, ok := value.(string); ok {
		return s
	}
	return ""
}

// DbmsAuthStrategyFromContext returns the stored DBMS auth strategy (actor|service), if any.
func DbmsAuthStrategyFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	value := ctx.Value(dbmsAuthStrategyKey{})
	if s, ok := value.(string); ok {
		return s
	}
	return ""
}
