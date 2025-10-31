package version

// Version будет подставляться через ldflags при сборке
// Example: go build -ldflags "-X github.com/command-center-1c/cluster-service/internal/version.Version=v1.0.0"
var Version = "dev"
