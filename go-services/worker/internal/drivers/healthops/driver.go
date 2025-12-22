package healthops

import (
	"context"
	"errors"
	"fmt"
	"net"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/credentials"
	"github.com/commandcenter1c/commandcenter/shared/logger"
	"github.com/commandcenter1c/commandcenter/shared/models"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	workerodata "github.com/commandcenter1c/commandcenter/worker/internal/odata"
)

// Driver handles health_check operations via OData.
type Driver struct {
	credsClient credentials.Fetcher
	service     *workerodata.Service
	timeline    tracing.TimelineRecorder
}

func NewDriver(credsClient credentials.Fetcher, service *workerodata.Service, timeline tracing.TimelineRecorder) *Driver {
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}
	return &Driver{
		credsClient: credsClient,
		service:     service,
		timeline:    timeline,
	}
}

func (d *Driver) Name() string { return "health-check" }

func (d *Driver) OperationTypes() []string { return []string{"health_check"} }

func (d *Driver) Execute(ctx context.Context, msg *models.OperationMessage, databaseID string) (models.DatabaseResultV2, error) {
	start := time.Now()
	log := logger.GetLogger()
	eventBase := "health_check"

	d.timeline.Record(ctx, msg.OperationID, eventBase+".started", map[string]interface{}{
		"database_id": databaseID,
	})

	result := models.DatabaseResultV2{
		DatabaseID: databaseID,
	}

	if d.credsClient == nil {
		result.Success = false
		result.Error = "credentials client not configured"
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result, nil
	}

	creds, err := d.credsClient.Fetch(ctx, databaseID)
	if err != nil {
		result.Success = false
		result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
		result.ErrorCode = "CREDENTIALS_ERROR"
		result.Duration = time.Since(start).Seconds()
		return result, nil
	}
	if creds == nil || creds.ODataURL == "" {
		result.Success = false
		result.Error = "odata url not configured"
		result.ErrorCode = "MISSING_ODATA_URL"
		result.Duration = time.Since(start).Seconds()
		return result, nil
	}

	if d.service == nil {
		d.service = workerodata.NewService(workerodata.DefaultPool())
	}

	responseTimeMs, err := d.service.HealthCheck(ctx, sharedodata.ODataCredentials{
		BaseURL:  creds.ODataURL,
		Username: creds.Username,
		Password: creds.Password,
	})
	result.Data = map[string]interface{}{
		"response_time_ms": responseTimeMs,
	}

	if err != nil {
		errorCode := classifyHealthError(err)
		result.Success = false
		result.Error = err.Error()
		result.ErrorCode = errorCode
		result.Duration = time.Since(start).Seconds()
		log.Warn("health check failed",
			zap.String("operation_id", msg.OperationID),
			zap.String("database_id", databaseID),
			zap.String("error_code", errorCode),
			zap.Error(err),
		)
		d.timeline.Record(ctx, msg.OperationID, eventBase+".failed", map[string]interface{}{
			"database_id":     databaseID,
			"error":           result.Error,
			"error_code":      errorCode,
			"response_time":   responseTimeMs,
			"duration_ms":     time.Since(start).Milliseconds(),
			"operation_type":  msg.OperationType,
		})
		return result, nil
	}

	result.Success = true
	result.Duration = time.Since(start).Seconds()

	d.timeline.Record(ctx, msg.OperationID, eventBase+".completed", map[string]interface{}{
		"database_id":     databaseID,
		"response_time":   responseTimeMs,
		"duration_ms":     time.Since(start).Milliseconds(),
		"operation_type":  msg.OperationType,
	})

	return result, nil
}

func classifyHealthError(err error) string {
	if err == nil {
		return ""
	}

	var odataErr *workerodata.ODataError
	if errors.As(err, &odataErr) {
		if odataErr.Code != "" {
			return odataErr.Code
		}
		return "ODATA_ERROR"
	}

	if errors.Is(err, context.DeadlineExceeded) {
		return "TIMEOUT"
	}

	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return "TIMEOUT"
	}

	errMsg := strings.ToLower(err.Error())
	if strings.Contains(errMsg, "timeout") {
		return "TIMEOUT"
	}

	return "NETWORK_ERROR"
}
