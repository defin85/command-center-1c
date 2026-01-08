// go-services/worker/internal/drivers/ibcmdops/storage.go
package ibcmdops

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	runnerartifacts "github.com/commandcenter1c/commandcenter/worker/internal/commandrunner/artifacts"
)

type storage interface {
	ResolveInput(ctx context.Context, inputPath string) (string, func(), error)
	PrepareOutput(ctx context.Context, outputPath, databaseID, ext string) (string, string, func(ctx context.Context) error, func(), error)
}

type localStorage struct {
	basePath string
}

type s3Storage struct {
	client  *runnerartifacts.Storage
	bucket  string
	prefix  string
	tempDir string
}

func newStorageFromEnv() (storage, error) {
	backend := strings.ToLower(os.Getenv("IBCMD_STORAGE_BACKEND"))
	if backend == "" {
		backend = "local"
	}

	switch backend {
	case "local":
		base := os.Getenv("IBCMD_STORAGE_PATH")
		if base == "" {
			base = defaultStoragePath
		}
		absBase, err := filepath.Abs(base)
		if err != nil {
			return nil, fmt.Errorf("failed to resolve storage path: %w", err)
		}
		if err := os.MkdirAll(absBase, 0755); err != nil {
			return nil, fmt.Errorf("failed to create storage directory: %w", err)
		}
		return &localStorage{basePath: absBase}, nil
	case "s3":
		return newS3StorageFromEnv()
	default:
		return nil, fmt.Errorf("unsupported storage backend: %s", backend)
	}
}

func (s *localStorage) ResolveInput(_ context.Context, inputPath string) (string, func(), error) {
	resolved, err := resolveLocalPath(s.basePath, inputPath)
	if err != nil {
		return "", nil, err
	}
	return resolved, func() {}, nil
}

func (s *localStorage) PrepareOutput(_ context.Context, outputPath, databaseID, ext string) (string, string, func(ctx context.Context) error, func(), error) {
	resolved, err := resolveLocalOutputPath(outputPath, s.basePath, databaseID, ext)
	if err != nil {
		return "", "", nil, nil, err
	}
	return resolved, resolved, func(context.Context) error { return nil }, func() {}, nil
}

func newS3StorageFromEnv() (*s3Storage, error) {
	endpoint := os.Getenv("IBCMD_S3_ENDPOINT")
	bucket := os.Getenv("IBCMD_S3_BUCKET")
	accessKey := os.Getenv("IBCMD_S3_ACCESS_KEY")
	secretKey := os.Getenv("IBCMD_S3_SECRET_KEY")
	region := os.Getenv("IBCMD_S3_REGION")
	prefix := strings.Trim(os.Getenv("IBCMD_S3_PREFIX"), "/")

	if endpoint == "" {
		return nil, fmt.Errorf("IBCMD_S3_ENDPOINT is required")
	}
	if bucket == "" {
		return nil, fmt.Errorf("IBCMD_S3_BUCKET is required")
	}
	if accessKey == "" || secretKey == "" {
		return nil, fmt.Errorf("IBCMD_S3_ACCESS_KEY and IBCMD_S3_SECRET_KEY are required")
	}

	useSSL := true
	if raw := os.Getenv("IBCMD_S3_USE_SSL"); raw != "" {
		useSSL = raw != "false"
	}

	client, err := runnerartifacts.NewStorage(runnerartifacts.StorageConfig{
		Endpoint:  endpoint,
		AccessKey: accessKey,
		SecretKey: secretKey,
		Bucket:    bucket,
		Secure:    useSSL,
		Region:    region,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to init S3 client: %w", err)
	}

	tempDir := filepath.Join(os.TempDir(), "cc1c-ibcmd")
	if err := os.MkdirAll(tempDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %w", err)
	}

	return &s3Storage{
		client:  client,
		bucket:  bucket,
		prefix:  prefix,
		tempDir: tempDir,
	}, nil
}

func (s *s3Storage) ResolveInput(ctx context.Context, inputPath string) (string, func(), error) {
	_, key, err := s.normalizeInputKey(inputPath)
	if err != nil {
		return "", nil, err
	}

	localPath, err := s.client.DownloadToTempFile(ctx, key, s.tempDir)
	if err != nil {
		return "", nil, fmt.Errorf("failed to download s3 object: %w", err)
	}

	cleanup := func() {
		_ = os.Remove(localPath)
	}

	return localPath, cleanup, nil
}

func (s *s3Storage) PrepareOutput(ctx context.Context, outputPath, databaseID, ext string) (string, string, func(ctx context.Context) error, func(), error) {
	key, err := s.normalizeOutputKey(outputPath, databaseID, ext)
	if err != nil {
		return "", "", nil, nil, err
	}

	tempFile, err := os.CreateTemp(s.tempDir, "ibcmd-output-*"+ext)
	if err != nil {
		return "", "", nil, nil, fmt.Errorf("failed to create temp file: %w", err)
	}
	localPath := tempFile.Name()
	if err := tempFile.Close(); err != nil {
		_ = os.Remove(localPath)
		return "", "", nil, nil, fmt.Errorf("failed to close temp file: %w", err)
	}

	artifactPath := fmt.Sprintf("s3://%s/%s", s.bucket, key)

	finalize := func(ctx context.Context) error {
		if err := s.client.UploadFile(ctx, key, localPath, ""); err != nil {
			return fmt.Errorf("failed to upload to s3: %w", err)
		}
		return nil
	}

	cleanup := func() {
		_ = os.Remove(localPath)
	}

	return localPath, artifactPath, finalize, cleanup, nil
}

func (s *s3Storage) normalizeInputKey(inputPath string) (string, string, error) {
	bucket, key, err := parseS3Path(inputPath)
	if err != nil {
		return "", "", err
	}
	if bucket != "" && bucket != s.bucket {
		return "", "", fmt.Errorf("s3 bucket mismatch: %s", bucket)
	}
	key = strings.TrimLeft(key, "/")
	if key == "" {
		return "", "", fmt.Errorf("s3 key is required")
	}
	return s.bucket, applyPrefix(s.prefix, key), nil
}

func (s *s3Storage) normalizeOutputKey(outputPath, databaseID, ext string) (string, error) {
	if outputPath != "" {
		bucket, key, err := parseS3Path(outputPath)
		if err != nil {
			return "", err
		}
		if bucket != "" && bucket != s.bucket {
			return "", fmt.Errorf("s3 bucket mismatch: %s", bucket)
		}
		key = strings.TrimLeft(key, "/")
		if key == "" {
			return "", fmt.Errorf("output_path is invalid")
		}
		return applyPrefix(s.prefix, key), nil
	}

	timestamp := time.Now().UTC().Format("20060102_150405")
	filename := fmt.Sprintf("%s_%s_%s%s", "infobase_dump", sanitizeFilePart(databaseID), timestamp, ext)
	key := filepath.ToSlash(filepath.Join(databaseID, filename))
	return applyPrefix(s.prefix, key), nil
}

func applyPrefix(prefix, key string) string {
	if prefix == "" {
		return key
	}
	return strings.Trim(prefix, "/") + "/" + strings.TrimLeft(key, "/")
}

func parseS3Path(value string) (string, string, error) {
	if value == "" {
		return "", "", nil
	}
	if strings.HasPrefix(value, "s3://") {
		parsed, err := url.Parse(value)
		if err != nil {
			return "", "", fmt.Errorf("invalid s3 path: %w", err)
		}
		bucket := parsed.Host
		key := strings.TrimLeft(parsed.Path, "/")
		return bucket, key, nil
	}
	return "", value, nil
}

func resolveLocalPath(basePath, inputPath string) (string, error) {
	if inputPath == "" {
		return "", fmt.Errorf("path is required")
	}

	baseClean := filepath.Clean(basePath)
	var resolved string
	if filepath.IsAbs(inputPath) {
		resolved = filepath.Clean(inputPath)
		if resolved != baseClean && !strings.HasPrefix(resolved, baseClean+string(os.PathSeparator)) {
			return "", fmt.Errorf("path is outside storage base")
		}
	} else {
		resolved = filepath.Clean(filepath.Join(baseClean, inputPath))
		if resolved != baseClean && !strings.HasPrefix(resolved, baseClean+string(os.PathSeparator)) {
			return "", fmt.Errorf("path is outside storage base")
		}
	}

	return resolved, nil
}

func resolveLocalOutputPath(outputPath, basePath, databaseID, ext string) (string, error) {
	if outputPath == "" {
		outputName := fmt.Sprintf("%s_%s_%s%s", "infobase_dump", sanitizeFilePart(databaseID), time.Now().UTC().Format("20060102_150405"), ext)
		outputPath = filepath.Join(databaseID, outputName)
	}

	if !strings.HasSuffix(strings.ToLower(outputPath), ext) {
		outputPath += ext
	}

	resolved, err := resolveLocalPath(basePath, outputPath)
	if err != nil {
		return "", err
	}

	if err := os.MkdirAll(filepath.Dir(resolved), 0755); err != nil {
		return "", fmt.Errorf("failed to create output directory: %w", err)
	}

	return resolved, nil
}

func sanitizeFilePart(value string) string {
	replacer := strings.NewReplacer(
		"/", "_",
		"\\", "_",
		":", "_",
		"..", "_",
		" ", "_",
	)
	return replacer.Replace(value)
}
