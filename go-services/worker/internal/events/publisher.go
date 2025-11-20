package events

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// EventPublisher публикует workflow события в Redis PubSub
type EventPublisher struct {
	redisClient *redis.Client
}

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

// Publish публикует событие в Redis PubSub
func (p *EventPublisher) Publish(ctx context.Context, event WorkflowEvent) error {
	event.Version = "1.0"
	event.Timestamp = time.Now()
	event.Microservice = "worker"

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	channel := fmt.Sprintf("operation:%s:events", event.OperationID)
	if err := p.redisClient.Publish(ctx, channel, data).Err(); err != nil {
		return fmt.Errorf("publish to channel %s: %w", channel, err)
	}

	return nil
}

// PublishProcessing публикует событие PROCESSING
func (p *EventPublisher) PublishProcessing(ctx context.Context, operationID, databaseID, workerID string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "PROCESSING",
		Message:     fmt.Sprintf("Обработка базы %s", databaseID),
		Metadata: map[string]interface{}{
			"database_id": databaseID,
			"worker_id":   workerID,
		},
	})
}

// PublishUploading публикует событие UPLOADING
func (p *EventPublisher) PublishUploading(ctx context.Context, operationID, filename string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "UPLOADING",
		Message:     fmt.Sprintf("Загрузка файла %s", filename),
		Metadata: map[string]interface{}{
			"filename": filename,
		},
	})
}

// PublishInstalling публикует событие INSTALLING
func (p *EventPublisher) PublishInstalling(ctx context.Context, operationID, extensionName string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "INSTALLING",
		Message:     fmt.Sprintf("Установка расширения %s", extensionName),
		Metadata: map[string]interface{}{
			"extension_name": extensionName,
		},
	})
}

// PublishVerifying публикует событие VERIFYING
func (p *EventPublisher) PublishVerifying(ctx context.Context, operationID string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "VERIFYING",
		Message:     "Проверка установки расширения",
	})
}

// PublishSuccess публикует событие SUCCESS
func (p *EventPublisher) PublishSuccess(ctx context.Context, operationID string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "SUCCESS",
		Message:     "Операция успешно завершена",
	})
}

// PublishFailed публикует событие FAILED
func (p *EventPublisher) PublishFailed(ctx context.Context, operationID, errorMsg string) error {
	return p.Publish(ctx, WorkflowEvent{
		OperationID: operationID,
		State:       "FAILED",
		Message:     fmt.Sprintf("Ошибка: %s", errorMsg),
		Metadata: map[string]interface{}{
			"error": errorMsg,
		},
	})
}
