// go-services/worker/internal/credentials/interface.go
package credentials

import "context"

// Fetcher is an interface for fetching database credentials
type Fetcher interface {
	Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error)
}
