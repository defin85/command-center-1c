package events

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// EventPublisher публикует workflow события в Redis Streams
type EventPublisher struct {
	redisClient *redis.Client
}

const (
	// StreamMaxLen - максимальное количество записей в stream (approximate)
	StreamMaxLen = 1000
)

// NewEventPublisher создает новый publisher
func NewEventPublisher(redisClient *redis.Client) *EventPublisher {
	return &EventPublisher{
		redisClient: redisClient,
	}
}

// WorkflowEvent представляет событие workflow
type WorkflowEvent struct {
	Version      string                 `json:"version"`
	OperationID  string                 `json:"operation_id"`
	Timestamp    time.Time              `json:"timestamp"`
	State        string                 `json:"state"`
	Microservice string                 `json:"microservice"`
	Message      string                 `json:"message"`
	Metadata     map[string]interface{} `json:"metadata"`
}

// Publish публикует событие в Redis Streams (XADD)
func (p *EventPublisher) Publish(ctx context.Context, event WorkflowEvent) error {
	event.Version = "1.0"
	event.Timestamp = time.Now()
	event.Microservice = "worker"

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	// Stream name: events:operation:{operation_id}
	stream := fmt.Sprintf("events:operation:%s", event.OperationID)

	// XADD с MAXLEN для автоматического trimming
	if err := p.redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: stream,
		MaxLen: StreamMaxLen,
		Approx: true, // ~ для производительности
		Values: map[string]interface{}{
			"event_type":   event.State,
			"data":         string(data),
			"operation_id": event.OperationID,
		},
	}).Err(); err != nil {
		return fmt.Errorf("xadd to stream %s: %w", stream, err)
	}

	return nil
}

// PublishProcessing публикует событие PROCESSING
func (p *EventPublisher) PublishProcessing(ctx context.Context, operationID, databaseID, workerID string) error {
	return p.PublishProcessingWithMetadata(ctx, operationID, databaseID, workerID, nil)
}

// PublishProcessingWithMetadata публикует событие PROCESSING с доп. метаданными.
func (p *EventPublisher) PublishProcessingWithMetadata(
	ctx context.Context,
	operationID, databaseID, workerID string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "PROCESSING",
		Message:     fmt.Sprintf("Обработка базы %s", databaseID),
		Metadata: MergeMetadata(map[string]interface{}{
			"database_id": databaseID,
			"worker_id":   workerID,
		}, metadata),
	})
}

// PublishUploading публикует событие UPLOADING
func (p *EventPublisher) PublishUploading(ctx context.Context, operationID, filename string) error {
	return p.PublishUploadingWithMetadata(ctx, operationID, filename, nil)
}

// PublishUploadingWithMetadata публикует событие UPLOADING с доп. метаданными.
func (p *EventPublisher) PublishUploadingWithMetadata(
	ctx context.Context,
	operationID, filename string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "UPLOADING",
		Message:     fmt.Sprintf("Загрузка файла %s", filename),
		Metadata: MergeMetadata(map[string]interface{}{
			"filename": filename,
		}, metadata),
	})
}

// PublishInstalling публикует событие INSTALLING
func (p *EventPublisher) PublishInstalling(ctx context.Context, operationID, extensionName string) error {
	return p.PublishInstallingWithMetadata(ctx, operationID, extensionName, nil)
}

// PublishInstallingWithMetadata публикует событие INSTALLING с доп. метаданными.
func (p *EventPublisher) PublishInstallingWithMetadata(
	ctx context.Context,
	operationID, extensionName string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "INSTALLING",
		Message:     fmt.Sprintf("Установка расширения %s", extensionName),
		Metadata: MergeMetadata(map[string]interface{}{
			"extension_name": extensionName,
		}, metadata),
	})
}

// PublishVerifying публикует событие VERIFYING
func (p *EventPublisher) PublishVerifying(ctx context.Context, operationID string) error {
	return p.PublishVerifyingWithMetadata(ctx, operationID, nil)
}

// PublishVerifyingWithMetadata публикует событие VERIFYING с доп. метаданными.
func (p *EventPublisher) PublishVerifyingWithMetadata(
	ctx context.Context,
	operationID string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "VERIFYING",
		Message:     "Проверка установки расширения",
		Metadata:    MergeMetadata(nil, metadata),
	})
}

// PublishSuccess публикует событие SUCCESS
func (p *EventPublisher) PublishSuccess(ctx context.Context, operationID string) error {
	return p.PublishSuccessWithMetadata(ctx, operationID, nil)
}

// PublishSuccessWithMetadata публикует событие SUCCESS с доп. метаданными.
func (p *EventPublisher) PublishSuccessWithMetadata(
	ctx context.Context,
	operationID string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "SUCCESS",
		Message:     "Операция успешно завершена",
		Metadata:    MergeMetadata(nil, metadata),
	})
}

// PublishFailed публикует событие FAILED
func (p *EventPublisher) PublishFailed(ctx context.Context, operationID, errorMsg string) error {
	return p.PublishFailedWithMetadata(ctx, operationID, errorMsg, nil)
}

// PublishFailedWithMetadata публикует событие FAILED с доп. метаданными.
func (p *EventPublisher) PublishFailedWithMetadata(
	ctx context.Context,
	operationID, errorMsg string,
	metadata map[string]interface{},
) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "FAILED",
		Message:     fmt.Sprintf("Ошибка: %s", errorMsg),
		Metadata: MergeMetadata(map[string]interface{}{
			"error": errorMsg,
		}, metadata),
	})
}
