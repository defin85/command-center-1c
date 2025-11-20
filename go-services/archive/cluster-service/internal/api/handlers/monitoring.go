package handlers

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/command-center-1c/cluster-service/internal/models"
	"github.com/command-center-1c/cluster-service/internal/service"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type MonitoringHandler struct {
	service        *service.MonitoringService
	logger         *zap.Logger
	requestTimeout time.Duration
}

func NewMonitoringHandler(svc *service.MonitoringService, requestTimeout time.Duration, logger *zap.Logger) *MonitoringHandler {
	return &MonitoringHandler{
		service:        svc,
		logger:         logger,
		requestTimeout: requestTimeout,
	}
}

func (h *MonitoringHandler) GetClusters(c *gin.Context) {
	server := c.Query("server")
	if server == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "query parameter 'server' is required",
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	clusters, err := h.service.GetClusters(ctx, server)
	if err != nil {
		statusCode, errResp := mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	c.JSON(http.StatusOK, models.ClustersResponse{
		Clusters: clusters,
	})
}

func (h *MonitoringHandler) GetInfobases(c *gin.Context) {
	server := c.Query("server")
	if server == "" {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "query parameter 'server' is required",
		})
		return
	}

	cluster := c.Query("cluster") // optional

	ctx, cancel := context.WithTimeout(c.Request.Context(), h.requestTimeout)
	defer cancel()

	infobases, err := h.service.GetInfobases(ctx, server, cluster)
	if err != nil {
		statusCode, errResp := mapErrorToHTTP(err)
		c.JSON(statusCode, errResp)
		return
	}

	c.JSON(http.StatusOK, models.InfobasesResponse{
		Infobases: infobases,
	})
}

func mapErrorToHTTP(err error) (int, models.ErrorResponse) {
	var svcErr *service.ServiceError
	if errors.As(err, &svcErr) {
		switch svcErr.Code {
		case "INVALID_SERVER":
			return http.StatusBadRequest, models.ErrorResponse{Error: svcErr.Message}
		case "GRPC_UNAVAILABLE":
			return http.StatusServiceUnavailable, models.ErrorResponse{Error: svcErr.Message}
		case "CLUSTER_NOT_FOUND":
			return http.StatusNotFound, models.ErrorResponse{Error: svcErr.Message}
		}
	}

	// gRPC errors
	if st, ok := status.FromError(err); ok {
		switch st.Code() {
		case codes.Unavailable:
			return http.StatusServiceUnavailable, models.ErrorResponse{Error: "upstream service unavailable"}
		case codes.DeadlineExceeded:
			return http.StatusGatewayTimeout, models.ErrorResponse{Error: "request timeout"}
		case codes.InvalidArgument:
			return http.StatusBadRequest, models.ErrorResponse{Error: st.Message()}
		case codes.PermissionDenied:
			return http.StatusForbidden, models.ErrorResponse{Error: "cluster authentication failed: " + st.Message()}
		}
	}

	return http.StatusInternalServerError, models.ErrorResponse{Error: "internal server error"}
}
