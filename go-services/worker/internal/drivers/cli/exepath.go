package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const err1cv8NotConfigured = "PLATFORM_1C_BIN_PATH is not configured"

// Resolve1cv8PathFromEnv returns a 1cv8 executable path based on env configuration.
// It uses PLATFORM_1C_BIN_PATH + {1cv8.exe,1cv8}.
func Resolve1cv8PathFromEnv() (string, error) {
	binPath := strings.TrimSpace(os.Getenv("PLATFORM_1C_BIN_PATH"))
	if binPath == "" {
		return "", fmt.Errorf(err1cv8NotConfigured)
	}

	candidates := []string{
		filepath.Join(binPath, "1cv8.exe"),
		filepath.Join(binPath, "1cv8"),
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		}
	}
	return candidates[0], nil
}
