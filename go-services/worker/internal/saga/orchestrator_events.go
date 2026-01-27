package saga

import (
	"context"
	"time"

	"go.uber.org/zap"
)

// publishEvent publishes a saga event to Redis Streams.
func (o *orchestrator) publishEvent(
	ctx context.Context,
	eventType SagaEventType,
	executionID, sagaID, correlationID, stepID string,
	errorMsg interface{},
	duration time.Duration,
) {
	if !o.config.EnableEvents || o.publisher == nil {
		return
	}

	event := NewSagaEvent(eventType, executionID, sagaID, correlationID)
	event.StepID = stepID
	event.Duration = duration

	if errStr, ok := errorMsg.(string); ok && errStr != "" {
		event.Error = errStr
	}

	err := o.publisher.Publish(ctx, o.config.EventChannel, string(eventType), event, correlationID)
	if err != nil {
		o.logger.Warn("failed to publish saga event",
			zap.String("event_type", string(eventType)),
			zap.String("execution_id", executionID),
			zap.Error(err),
		)
	}
}
