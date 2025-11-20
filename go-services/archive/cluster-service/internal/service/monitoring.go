package service

import (
	"context"
	"fmt"
	"net"

	"github.com/command-center-1c/cluster-service/internal/grpc"
	"github.com/command-center-1c/cluster-service/internal/models"

	apiv1 "github.com/v8platform/protos/gen/ras/service/api/v1"
	messagesv1 "github.com/v8platform/protos/gen/ras/messages/v1"
	"go.uber.org/zap"
)

type MonitoringService struct {
	grpcClient *grpc.Client
	logger     *zap.Logger
}

func validateServerAddr(addr string) error {
	if addr == "" {
		return ErrInvalidServer
	}

	// Проверяем формат host:port
	_, _, err := net.SplitHostPort(addr)
	if err != nil {
		return &ServiceError{
			Code:    "INVALID_SERVER",
			Message: fmt.Sprintf("invalid server address format (expected host:port): %s", addr),
			Err:     err,
		}
	}

	return nil
}

func NewMonitoringService(client *grpc.Client, logger *zap.Logger) *MonitoringService {
	return &MonitoringService{
		grpcClient: client,
		logger:     logger,
	}
}

func (s *MonitoringService) GetClusters(ctx context.Context, serverAddr string) ([]models.Cluster, error) {
	// Валидация
	if err := validateServerAddr(serverAddr); err != nil {
		return nil, err
	}

	// Создаем gRPC client stub
	client := apiv1.NewClustersServiceClient(s.grpcClient.GetConnection())

	// Вызываем gRPC метод
	req := &messagesv1.GetClustersRequest{}

	resp, err := client.GetClusters(ctx, req)
	if err != nil {
		s.logger.Error("failed to get clusters", zap.Error(err))
		return nil, fmt.Errorf("get clusters failed: %w", err)
	}

	// Конвертируем protobuf → domain models
	clusters := make([]models.Cluster, 0, len(resp.Clusters))
	for _, c := range resp.Clusters {
		clusters = append(clusters, models.Cluster{
			UUID: c.Uuid,
			Name: c.Name,
			Host: c.Host,
			Port: c.Port,
		})
	}

	return clusters, nil
}

func (s *MonitoringService) GetInfobases(ctx context.Context, serverAddr, clusterUUID string) ([]models.Infobase, error) {
	if err := validateServerAddr(serverAddr); err != nil {
		return nil, err
	}

	// Аутентификация кластера (требуется даже при security-level: 0)
	authClient := apiv1.NewAuthServiceClient(s.grpcClient.GetConnection())

	authReq := &messagesv1.ClusterAuthenticateRequest{
		ClusterId: clusterUUID,
		User:      "", // пустой при security-level: 0
		Password:  "", // пустой при security-level: 0
	}

	_, err := authClient.AuthenticateCluster(ctx, authReq)
	if err != nil {
		s.logger.Error("cluster authentication failed",
			zap.String("cluster_id", clusterUUID),
			zap.Error(err))
		return nil, fmt.Errorf("cluster authentication failed: %w", err)
	}

	s.logger.Debug("cluster authenticated successfully",
		zap.String("cluster_id", clusterUUID))

	// Создаем gRPC client stub
	client := apiv1.NewInfobasesServiceClient(s.grpcClient.GetConnection())

	// Вызываем gRPC метод
	req := &messagesv1.GetInfobasesShortRequest{
		ClusterId: clusterUUID,
	}

	resp, err := client.GetShortInfobases(ctx, req)
	if err != nil {
		s.logger.Error("failed to get infobases", zap.Error(err))
		return nil, fmt.Errorf("get infobases failed: %w", err)
	}

	// Конвертируем protobuf → domain models
	// Примечание: GetInfobasesShortResponse возвращает Sessions []*InfobaseSummaryInfo
	// InfobaseSummaryInfo содержит только UUID, Name, Descr
	infobases := make([]models.Infobase, 0, len(resp.Sessions))
	for _, ib := range resp.Sessions {
		infobases = append(infobases, models.Infobase{
			UUID: ib.Uuid,
			Name: ib.Name,
			// Остальные поля недоступны в ShortResponse, оставляем пустыми
			DBMS:     "",
			DBServer: "",
			DBName:   "",
		})
	}

	return infobases, nil
}
