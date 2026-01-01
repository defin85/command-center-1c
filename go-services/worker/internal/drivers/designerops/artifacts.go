package designerops

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
		if !strings.HasPrefix(arg, artifactPrefix) {
			resolved[idx] = arg
			continue
		}
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
	}

	if isWindowsInterop() {
		for idx, arg := range resolved {
			resolved[idx] = toWindowsPath(arg)
		}
	}

	return resolved, cleanup, nil
}

func resolveArtifactBaseDir() string {
	baseDir := strings.TrimSpace(os.Getenv("CLI_ARTIFACT_TMP_DIR"))
	if baseDir != "" {
		return baseDir
	}

	if drive, ok := detectWindowsDrive(); ok {
		return filepath.Join("/mnt", drive, "cc1c-cli-artifacts")
	}

	return filepath.Join(os.TempDir(), "cc1c-cli-artifacts")
}

func detectWindowsDrive() (string, bool) {
	binPath := strings.TrimSpace(os.Getenv("PLATFORM_1C_BIN_PATH"))
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

func fromWindowsPath(path string) string {
	if len(path) > 2 && path[1] == ':' {
		drive := strings.ToLower(path[:1])
		rest := strings.TrimPrefix(path[2:], "\\")
		rest = strings.ReplaceAll(rest, "\\", "/")
		if rest == "" {
			return "/mnt/" + drive
		}
		return "/mnt/" + drive + "/" + rest
	}
	return path
}
