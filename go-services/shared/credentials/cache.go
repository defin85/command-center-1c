package credentials

import "time"

type cacheEntry struct {
	credentials *DatabaseCredentials
	expiresAt   time.Time
}
