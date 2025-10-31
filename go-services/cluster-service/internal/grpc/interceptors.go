package grpc

import (
	"context"
	"time"

	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

func loggingInterceptor(logger *zap.Logger) grpc.UnaryClientInterceptor {
	return func(
		ctx context.Context,
		method string,
		req, reply interface{},
		cc *grpc.ClientConn,
		invoker grpc.UnaryInvoker,
		opts ...grpc.CallOption,
	) error {
		start := time.Now()

		// Debug: проверяем наличие endpoint_id в metadata
		if md, ok := metadata.FromOutgoingContext(ctx); ok {
			if endpointIDs := md.Get("endpoint_id"); len(endpointIDs) > 0 {
				logger.Debug("gRPC outgoing metadata",
					zap.String("method", method),
					zap.String("endpoint_id", endpointIDs[0]),
				)
			} else {
				logger.Warn("endpoint_id NOT found in outgoing metadata",
					zap.String("method", method),
				)
			}
		} else {
			logger.Warn("NO outgoing metadata in context",
				zap.String("method", method),
			)
		}

		err := invoker(ctx, method, req, reply, cc, opts...)

		duration := time.Since(start)

		if err != nil {
			logger.Error("gRPC call failed",
				zap.String("method", method),
				zap.Duration("duration", duration),
				zap.Error(err),
			)
		} else {
			logger.Debug("gRPC call succeeded",
				zap.String("method", method),
				zap.Duration("duration", duration),
			)
		}

		return err
	}
}
