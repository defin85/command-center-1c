package version

var (
	// Version is set at build time via -ldflags
	Version = "dev"

	// Commit is the git commit hash, set at build time
	Commit = "unknown"

	// BuildTime is the build timestamp, set at build time
	BuildTime = "unknown"
)

// Info returns version information as a map
func Info() map[string]string {
	return map[string]string{
		"version":    Version,
		"commit":     Commit,
		"build_time": BuildTime,
	}
}
