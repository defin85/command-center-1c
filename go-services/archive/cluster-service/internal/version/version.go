package version

// These variables are set by -ldflags during build
var (
	Version   = "dev"
	Commit    = "unknown"
	BuildTime = "unknown"
)
