package artifacts

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

type StorageConfig struct {
	Endpoint  string
	AccessKey string
	SecretKey string
	Bucket    string
	Secure    bool
	Region    string
}

type Storage struct {
	client *minio.Client
	bucket string
}

func NewStorage(cfg StorageConfig) (*Storage, error) {
	endpoint := sanitizeEndpoint(cfg.Endpoint)
	accessKey := strings.TrimSpace(cfg.AccessKey)
	secretKey := strings.TrimSpace(cfg.SecretKey)
	bucket := strings.TrimSpace(cfg.Bucket)
	region := strings.TrimSpace(cfg.Region)

	if endpoint == "" || accessKey == "" || secretKey == "" || bucket == "" {
		return nil, fmt.Errorf("storage is not configured (endpoint/access_key/secret_key/bucket)")
	}

	client, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: cfg.Secure,
		Region: region,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to init storage client: %w", err)
	}

	return &Storage{
		client: client,
		bucket: bucket,
	}, nil
}

func NewStorageFromMinioEnv() (*Storage, error) {
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

	return NewStorage(StorageConfig{
		Endpoint:  endpoint,
		AccessKey: accessKey,
		SecretKey: secretKey,
		Bucket:    bucket,
		Secure:    secure,
	})
}

func (s *Storage) DownloadToTempFile(ctx context.Context, key, dir string) (string, error) {
	if s == nil || s.client == nil {
		return "", fmt.Errorf("storage client is not initialized")
	}
	key = strings.TrimLeft(strings.TrimSpace(key), "/")
	if key == "" {
		return "", fmt.Errorf("object key is required")
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
		return "", fmt.Errorf("failed to download object: %w", err)
	}
	defer object.Close()

	if _, err := io.Copy(tmpFile, object); err != nil {
		_ = tmpFile.Close()
		_ = os.Remove(localPath)
		return "", fmt.Errorf("failed to write object: %w", err)
	}
	if err := tmpFile.Close(); err != nil {
		_ = os.Remove(localPath)
		return "", fmt.Errorf("failed to close temp file: %w", err)
	}

	return localPath, nil
}

func (s *Storage) UploadFile(ctx context.Context, key, localPath, contentType string) error {
	if s == nil || s.client == nil {
		return fmt.Errorf("storage client is not initialized")
	}
	key = sanitizeKey(key)
	if key == "" {
		return fmt.Errorf("object key is required")
	}
	localPath = strings.TrimSpace(localPath)
	if localPath == "" {
		return fmt.Errorf("local path is required")
	}

	file, err := os.Open(localPath)
	if err != nil {
		return fmt.Errorf("failed to open local file: %w", err)
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return fmt.Errorf("failed to stat local file: %w", err)
	}

	opts := minio.PutObjectOptions{}
	if ct := strings.TrimSpace(contentType); ct != "" {
		opts.ContentType = ct
	}

	if _, err := s.client.PutObject(ctx, s.bucket, key, file, info.Size(), opts); err != nil {
		return fmt.Errorf("failed to upload object: %w", err)
	}
	return nil
}

func sanitizeEndpoint(value string) string {
	raw := strings.TrimSpace(value)
	raw = strings.TrimPrefix(raw, "http://")
	raw = strings.TrimPrefix(raw, "https://")
	raw = strings.TrimLeft(raw, "/")
	return raw
}

func sanitizeKey(value string) string {
	return strings.TrimLeft(strings.TrimSpace(value), "/")
}

func (s *Storage) DeleteObject(ctx context.Context, key string) error {
	if s == nil || s.client == nil {
		return fmt.Errorf("storage client is not initialized")
	}
	key = sanitizeKey(key)
	if key == "" {
		return fmt.Errorf("object key is required")
	}
	if err := s.client.RemoveObject(ctx, s.bucket, key, minio.RemoveObjectOptions{}); err != nil {
		return fmt.Errorf("failed to delete object: %w", err)
	}
	return nil
}

func (s *Storage) DeleteObjects(ctx context.Context, keys []string) (deleted int, failedKeys []string, err error) {
	if s == nil || s.client == nil {
		return 0, nil, fmt.Errorf("storage client is not initialized")
	}
	if len(keys) == 0 {
		return 0, nil, nil
	}

	objectsCh := make(chan minio.ObjectInfo, len(keys))
	sent := 0
	for _, key := range keys {
		clean := sanitizeKey(key)
		if clean == "" {
			continue
		}
		objectsCh <- minio.ObjectInfo{Key: clean}
		sent++
	}
	close(objectsCh)

	var firstErr error
	for rmErr := range s.client.RemoveObjects(ctx, s.bucket, objectsCh, minio.RemoveObjectsOptions{}) {
		failedKeys = append(failedKeys, rmErr.ObjectName)
		if firstErr == nil {
			firstErr = fmt.Errorf("failed to delete object %s: %w", rmErr.ObjectName, rmErr.Err)
		}
	}

	return sent - len(failedKeys), failedKeys, firstErr
}

func (s *Storage) DeleteByPrefix(ctx context.Context, prefix string, batchSize int) (deleted int, failed int, err error) {
	if s == nil || s.client == nil {
		return 0, 0, fmt.Errorf("storage client is not initialized")
	}
	prefix = sanitizeKey(prefix)
	if prefix == "" {
		return 0, 0, fmt.Errorf("prefix is required")
	}
	if batchSize <= 0 {
		batchSize = 1000
	}

	var batch []string
	for object := range s.client.ListObjects(ctx, s.bucket, minio.ListObjectsOptions{
		Prefix:    prefix,
		Recursive: true,
	}) {
		if object.Err != nil {
			return deleted, failed, fmt.Errorf("failed to list objects: %w", object.Err)
		}
		batch = append(batch, object.Key)
		if len(batch) >= batchSize {
			d, failedKeys, batchErr := s.DeleteObjects(ctx, batch)
			deleted += d
			failed += len(failedKeys)
			if batchErr != nil {
				return deleted, failed, batchErr
			}
			batch = batch[:0]
		}
	}

	if len(batch) > 0 {
		d, failedKeys, batchErr := s.DeleteObjects(ctx, batch)
		deleted += d
		failed += len(failedKeys)
		if batchErr != nil {
			return deleted, failed, batchErr
		}
	}

	return deleted, failed, nil
}
