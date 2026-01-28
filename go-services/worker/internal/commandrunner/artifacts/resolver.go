package artifacts

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const ArtifactPrefix = "artifact://"

type Driver string

const (
	DriverCLI   Driver = "cli"
	DriverIBCMD Driver = "ibcmd"
)

type Meta struct {
	Driver      Driver
	OperationID string
	DatabaseID  string
}

func ResolvePath(ctx context.Context, value string, meta Meta) (string, func(), error) {
	raw := strings.TrimSpace(value)
	if raw == "" || !strings.HasPrefix(raw, ArtifactPrefix) {
		return value, func() {}, nil
	}
	resolved, cleanup, err := ResolveArgs(ctx, []string{raw}, meta)
	if err != nil {
		return "", cleanup, err
	}
	if len(resolved) != 1 {
		cleanup()
		return "", cleanup, fmt.Errorf("failed to resolve artifact path")
	}
	return resolved[0], cleanup, nil
}

func ResolveArgs(ctx context.Context, args []string, meta Meta) ([]string, func(), error) {
	if len(args) == 0 {
		return args, func() {}, nil
	}

	hasArtifact := false
	for _, arg := range args {
		if strings.HasPrefix(arg, ArtifactPrefix) {
			hasArtifact = true
			break
		}
		if key, _, ok := splitArtifactFlagArg(arg); ok && key != "" {
			hasArtifact = true
			break
		}
	}
	if !hasArtifact {
		return args, func() {}, nil
	}

	storage, err := NewStorageFromMinioEnv()
	if err != nil {
		return nil, func() {}, err
	}

	operationID := strings.TrimSpace(meta.OperationID)
	if operationID == "" {
		operationID = "unknown"
	}
	databaseID := strings.TrimSpace(meta.DatabaseID)
	if databaseID == "" {
		databaseID = "global"
	}

	baseDir := BaseDir(meta.Driver)
	tempDir := filepath.Join(baseDir, operationID, databaseID)

	cleanup := func() {
		_ = os.RemoveAll(tempDir)
	}

	resolved := make([]string, len(args))
	for idx, arg := range args {
		if strings.HasPrefix(arg, ArtifactPrefix) {
			key := strings.TrimPrefix(arg, ArtifactPrefix)
			key = strings.TrimLeft(key, "/")
			if key == "" {
				cleanup()
				return nil, cleanup, fmt.Errorf("artifact path is empty")
			}

			localPath, err := storage.DownloadToTempFile(ctx, key, tempDir)
			if err != nil {
				cleanup()
				return nil, cleanup, err
			}
			resolved[idx] = localPath
			continue
		}

		if key, prefix, ok := splitArtifactFlagArg(arg); ok {
			localPath, err := storage.DownloadToTempFile(ctx, key, tempDir)
			if err != nil {
				cleanup()
				return nil, cleanup, err
			}
			resolved[idx] = prefix + localPath
			continue
		}

		resolved[idx] = arg
	}

	if IsWindowsInterop(meta.Driver) {
		for idx, arg := range resolved {
			resolved[idx] = convertFlagPathToWindows(arg)
		}
	}

	return resolved, cleanup, nil
}

func BaseDir(driver Driver) string {
	if baseDir := strings.TrimSpace(os.Getenv(tmpDirEnvKey(driver))); baseDir != "" {
		return baseDir
	}
	if driver == DriverIBCMD {
		if baseDir := strings.TrimSpace(os.Getenv("CLI_ARTIFACT_TMP_DIR")); baseDir != "" {
			return baseDir
		}
	}

	if drive, ok := detectWindowsDrive(driver); ok {
		return filepath.Join("/mnt", drive, defaultBaseDirName(driver))
	}

	return filepath.Join(os.TempDir(), defaultBaseDirName(driver))
}

func tmpDirEnvKey(driver Driver) string {
	switch driver {
	case DriverIBCMD:
		return "IBCMD_ARTIFACT_TMP_DIR"
	case DriverCLI:
		return "CLI_ARTIFACT_TMP_DIR"
	default:
		return "CLI_ARTIFACT_TMP_DIR"
	}
}

func defaultBaseDirName(driver Driver) string {
	switch driver {
	case DriverIBCMD:
		return "cc1c-ibcmd-artifacts"
	case DriverCLI:
		return "cc1c-cli-artifacts"
	default:
		return "cc1c-artifacts"
	}
}

func detectWindowsDrive(driver Driver) (string, bool) {
	envKeys := []string{"PLATFORM_1C_BIN_PATH"}
	switch driver {
	case DriverIBCMD:
		envKeys = []string{"IBCMD_PATH", "PLATFORM_1C_BIN_PATH"}
	case DriverCLI:
		envKeys = []string{"PLATFORM_1C_BIN_PATH"}
	}

	for _, key := range envKeys {
		binPath := strings.TrimSpace(os.Getenv(key))
		if strings.HasPrefix(binPath, "/mnt/") && len(binPath) > 6 {
			return strings.ToLower(binPath[5:6]), true
		}
		if len(binPath) >= 2 && binPath[1] == ':' {
			return strings.ToLower(binPath[:1]), true
		}
	}
	return "", false
}

func IsWindowsInterop(driver Driver) bool {
	_, ok := detectWindowsDrive(driver)
	return ok
}

func ToWindowsPath(path string) string {
	if strings.HasPrefix(path, "/mnt/") && len(path) > 6 {
		drive := strings.ToUpper(path[5:6])
		rest := strings.TrimPrefix(path[6:], "/")
		rest = strings.ReplaceAll(rest, "/", "\\")
		if rest == "" {
			return drive + ":\\"
		}
		return drive + ":\\" + rest
	}
	return path
}

func FromWindowsPath(path string) string {
	raw := strings.TrimSpace(path)
	if len(raw) > 2 && raw[1] == ':' {
		drive := strings.ToLower(raw[:1])
		rest := strings.TrimPrefix(raw[2:], "\\")
		rest = strings.TrimPrefix(rest, "/")
		rest = strings.ReplaceAll(rest, "\\", "/")
		if rest == "" {
			return "/mnt/" + drive
		}
		return "/mnt/" + drive + "/" + rest
	}
	return raw
}

func splitArtifactFlagArg(arg string) (key string, prefix string, ok bool) {
	raw := strings.TrimSpace(arg)
	if raw == "" {
		return "", "", false
	}
	idx := strings.Index(raw, "=")
	if idx < 0 {
		return "", "", false
	}
	value := raw[idx+1:]
	if !strings.HasPrefix(value, ArtifactPrefix) {
		return "", "", false
	}
	key = strings.TrimPrefix(value, ArtifactPrefix)
	key = strings.TrimLeft(key, "/")
	if key == "" {
		return "", "", false
	}
	return key, raw[:idx+1], true
}

func convertFlagPathToWindows(arg string) string {
	raw := strings.TrimSpace(arg)
	if raw == "" {
		return raw
	}
	if strings.HasPrefix(raw, "/mnt/") {
		return ToWindowsPath(raw)
	}
	idx := strings.Index(raw, "=")
	if idx < 0 {
		return raw
	}
	prefix := raw[:idx+1]
	value := raw[idx+1:]
	if strings.HasPrefix(value, "/mnt/") {
		return prefix + ToWindowsPath(value)
	}
	return raw
}
