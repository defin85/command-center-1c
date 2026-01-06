package ibcmdops

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

const artifactPrefix = "artifact://"

type artifactStorage struct {
	client *minio.Client
	bucket string
}

func newArtifactStorageFromEnv() (*artifactStorage, error) {
	endpoint := strings.TrimSpace(os.Getenv("MINIO_ENDPOINT"))
	accessKey := strings.TrimSpace(os.Getenv("MINIO_ACCESS_KEY"))
	secretKey := strings.TrimSpace(os.Getenv("MINIO_SECRET_KEY"))
	bucket := strings.TrimSpace(os.Getenv("MINIO_BUCKET"))
	if bucket == "" {
		bucket = "cc1c-artifacts"
	}

	if endpoint == "" || accessKey == "" || secretKey == "" {
		return nil, fmt.Errorf("artifact storage is not configured (MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY)")
	}

	secure := false
	if raw := strings.TrimSpace(os.Getenv("MINIO_SECURE")); raw != "" {
		if parsed, err := strconv.ParseBool(raw); err == nil {
			secure = parsed
		}
	}

	client, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: secure,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to init artifact storage client: %w", err)
	}

	return &artifactStorage{
		client: client,
		bucket: bucket,
	}, nil
}

func (s *artifactStorage) download(ctx context.Context, key, dir string) (string, error) {
	if key == "" {
		return "", fmt.Errorf("artifact key is required")
	}
	ext := filepath.Ext(key)
	pattern := "artifact-*"
	if ext != "" {
		pattern += ext
	}

	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("failed to create temp dir: %w", err)
	}

	tmpFile, err := os.CreateTemp(dir, pattern)
	if err != nil {
		return "", fmt.Errorf("failed to create temp file: %w", err)
	}
	localPath := tmpFile.Name()

	object, err := s.client.GetObject(ctx, s.bucket, key, minio.GetObjectOptions{})
	if err != nil {
		_ = tmpFile.Close()
		_ = os.Remove(localPath)
		return "", fmt.Errorf("failed to download artifact: %w", err)
	}
	defer object.Close()

	if _, err := io.Copy(tmpFile, object); err != nil {
		_ = tmpFile.Close()
		_ = os.Remove(localPath)
		return "", fmt.Errorf("failed to write artifact: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		_ = os.Remove(localPath)
		return "", fmt.Errorf("failed to close artifact file: %w", err)
	}

	return localPath, nil
}

func resolveArtifactArgs(
	ctx context.Context,
	args []string,
	operationID string,
	databaseID string,
) ([]string, func(), error) {
	if len(args) == 0 {
		return args, func() {}, nil
	}

	hasArtifact := false
	for _, arg := range args {
		if strings.HasPrefix(arg, artifactPrefix) {
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

	storage, err := newArtifactStorageFromEnv()
	if err != nil {
		return nil, func() {}, err
	}

	baseDir := resolveArtifactBaseDir()
	tempDir := filepath.Join(baseDir, operationID, databaseID)

	cleanup := func() {
		_ = os.RemoveAll(tempDir)
	}

	resolved := make([]string, len(args))
	for idx, arg := range args {
		if strings.HasPrefix(arg, artifactPrefix) {
			key := strings.TrimPrefix(arg, artifactPrefix)
			key = strings.TrimLeft(key, "/")
			if key == "" {
				cleanup()
				return nil, cleanup, fmt.Errorf("artifact path is empty")
			}

			localPath, err := storage.download(ctx, key, tempDir)
			if err != nil {
				cleanup()
				return nil, cleanup, err
			}
			resolved[idx] = localPath
			continue
		}

		if key, prefix, ok := splitArtifactFlagArg(arg); ok {
			localPath, err := storage.download(ctx, key, tempDir)
			if err != nil {
				cleanup()
				return nil, cleanup, err
			}
			resolved[idx] = prefix + localPath
			continue
		}

		resolved[idx] = arg
	}

	if isWindowsInterop() {
		for idx, arg := range resolved {
			resolved[idx] = convertFlagPathToWindows(arg)
		}
	}

	return resolved, cleanup, nil
}

func resolveArtifactPath(
	ctx context.Context,
	value string,
	operationID string,
	databaseID string,
) (string, func(), error) {
	raw := strings.TrimSpace(value)
	if raw == "" || !strings.HasPrefix(raw, artifactPrefix) {
		return value, func() {}, nil
	}
	resolved, cleanup, err := resolveArtifactArgs(ctx, []string{raw}, operationID, databaseID)
	if err != nil {
		return "", cleanup, err
	}
	if len(resolved) != 1 {
		cleanup()
		return "", cleanup, fmt.Errorf("failed to resolve artifact path")
	}
	return resolved[0], cleanup, nil
}

func resolveArtifactBaseDir() string {
	baseDir := strings.TrimSpace(os.Getenv("IBCMD_ARTIFACT_TMP_DIR"))
	if baseDir != "" {
		return baseDir
	}
	baseDir = strings.TrimSpace(os.Getenv("CLI_ARTIFACT_TMP_DIR"))
	if baseDir != "" {
		return baseDir
	}

	if drive, ok := detectWindowsDrive(); ok {
		return filepath.Join("/mnt", drive, "cc1c-ibcmd-artifacts")
	}

	return filepath.Join(os.TempDir(), "cc1c-ibcmd-artifacts")
}

func detectWindowsDrive() (string, bool) {
	binPath := strings.TrimSpace(os.Getenv("IBCMD_PATH"))
	if strings.HasPrefix(binPath, "/mnt/") && len(binPath) > 6 {
		return strings.ToLower(binPath[5:6]), true
	}
	if len(binPath) >= 2 && binPath[1] == ':' {
		return strings.ToLower(binPath[:1]), true
	}
	return "", false
}

func isWindowsInterop() bool {
	_, ok := detectWindowsDrive()
	return ok
}

func toWindowsPath(path string) string {
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
	if !strings.HasPrefix(value, artifactPrefix) {
		return "", "", false
	}
	key = strings.TrimPrefix(value, artifactPrefix)
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
		return toWindowsPath(raw)
	}
	idx := strings.Index(raw, "=")
	if idx < 0 {
		return raw
	}
	prefix := raw[:idx+1]
	value := raw[idx+1:]
	if strings.HasPrefix(value, "/mnt/") {
		return prefix + toWindowsPath(value)
	}
	return raw
}
