package eventhandlers

import (
	"context"
	"fmt"

	"go.uber.org/zap"
)

// FetchCredentialsForRAS fetches database credentials for RAS operations.
// Returns empty strings if client is nil or databaseID is empty (no-auth mode).
//
// Usage:
//
//	dbUser, dbPassword, err := FetchCredentialsForRAS(ctx, h.credsClient, cmd.DatabaseID, h.logger)
//	if err != nil {
//	    return h.publishError(ctx, correlationID, &cmd, fmt.Errorf("failed to fetch credentials: %w", err))
//	}
func FetchCredentialsForRAS(
	ctx context.Context,
	client CredentialsFetcher,
	databaseID string,
	logger *zap.Logger,
) (dbUser, dbPassword string, err error) {
	// No credentials needed if client is nil or databaseID is empty
	if client == nil || databaseID == "" {
		logger.Debug("no credentials client or database_id, using no-auth mode")
		return "", "", nil
	}

	creds, err := client.Fetch(ctx, databaseID)
	if err != nil {
		return "", "", fmt.Errorf("fetch failed: %w", err)
	}

	logger.Debug("credentials fetched",
		zap.String("database_id", databaseID),
		zap.Bool("has_credentials", creds.Username != ""))

	return creds.Username, creds.Password, nil
}
