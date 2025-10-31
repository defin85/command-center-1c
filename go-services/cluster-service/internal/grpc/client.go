package grpc

import (
	"context"
	"fmt"
	"time"

	grpc_retry "github.com/grpc-ecosystem/go-grpc-middleware/retry"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	"github.com/command-center-1c/cluster-service/internal/grpc/interceptors"
)

type Client struct {
	conn                *grpc.ClientConn
	logger              *zap.Logger
	endpointInterceptor *interceptors.EndpointInterceptor
}

func NewClient(ctx context.Context, addr string, logger *zap.Logger) (*Client, error) {
	// Создаём endpoint interceptor для автоматического управления endpoint_id
	endpointInterceptor := interceptors.NewEndpointInterceptor()

	opts := []grpc.DialOption{
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                10 * time.Second,
			Timeout:             3 * time.Second,
			PermitWithoutStream: true,
		}),
		grpc.WithUnaryInterceptor(grpc_retry.UnaryClientInterceptor(
			grpc_retry.WithMax(3),
			grpc_retry.WithBackoff(grpc_retry.BackoffLinear(100 * time.Millisecond)),
		)),
		grpc.WithChainUnaryInterceptor(
			endpointInterceptor.UnaryClientInterceptor(), // ПЕРВЫМ - добавляет endpoint_id
			loggingInterceptor(logger),                    // ВТОРЫМ - логирует уже с endpoint_id
		),
	}

	conn, err := grpc.DialContext(ctx, addr, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to gRPC server: %w", err)
	}

	logger.Info("gRPC client created", zap.String("addr", addr))

	return &Client{
		conn:                conn,
		logger:              logger,
		endpointInterceptor: endpointInterceptor,
	}, nil
}

func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

func (c *Client) GetConnection() *grpc.ClientConn {
	return c.conn
}

// GetEndpointID возвращает текущий endpoint_id для debugging
func (c *Client) GetEndpointID() string {
	return c.endpointInterceptor.GetEndpointID()
}

// ResetEndpoint сбрасывает endpoint_id для новой сессии
func (c *Client) ResetEndpoint() {
	c.endpointInterceptor.Reset()
}
