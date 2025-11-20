package interceptors

import (
	"context"
	"log"
	"sync"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

// EndpointInterceptor автоматически управляет endpoint_id между вызовами
type EndpointInterceptor struct {
	mu         sync.RWMutex
	endpointID string
}

// NewEndpointInterceptor создаёт новый interceptor для управления endpoint_id
// Не генерирует endpoint_id при создании - позволяет ras-grpc-gw создать первый endpoint
func NewEndpointInterceptor() *EndpointInterceptor {
	log.Printf("[EndpointInterceptor] Created without initial endpoint_id (will be assigned by ras-grpc-gw)")
	return &EndpointInterceptor{
		endpointID: "", // Пустой до первого response от ras-grpc-gw
	}
}

// UnaryClientInterceptor перехватывает вызовы и управляет endpoint_id
func (e *EndpointInterceptor) UnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		// Получаем или создаём outgoing metadata
		md, ok := metadata.FromOutgoingContext(ctx)
		if !ok {
			md = metadata.New(nil)
		}

		// Добавляем endpoint_id только если он уже был получен от ras-grpc-gw
		e.mu.RLock()
		endpointID := e.endpointID
		e.mu.RUnlock()

		if endpointID != "" {
			log.Printf("[EndpointInterceptor] Adding endpoint_id to request: %s (method: %s)", endpointID, method)
			md = md.Copy()
			md.Set("endpoint_id", endpointID)
			ctx = metadata.NewOutgoingContext(ctx, md)
		} else {
			log.Printf("[EndpointInterceptor] No endpoint_id yet, letting ras-grpc-gw create new endpoint (method: %s)", method)
			// НЕ добавляем endpoint_id - ras-grpc-gw создаст новый endpoint и вернет его ID
		}

		// Создаём header для получения response headers
		var header metadata.MD
		opts = append(opts, grpc.Header(&header))

		// Вызываем метод
		err := invoker(ctx, method, req, reply, cc, opts...)

		// Извлекаем endpoint_id из response headers (если сервер вернул новый)
		if vals := header.Get("endpoint_id"); len(vals) > 0 {
			newEndpointID := vals[0]
			e.mu.Lock()
			if e.endpointID != newEndpointID {
				log.Printf("[EndpointInterceptor] Received new endpoint_id from server: %s (replacing %s)", newEndpointID, e.endpointID)
				e.endpointID = newEndpointID
			}
			e.mu.Unlock()
		}

		return err
	}
}

// Reset сбрасывает сохранённый endpoint_id (для новых сессий с RAS)
// После reset следующий запрос к ras-grpc-gw создаст новый endpoint
func (e *EndpointInterceptor) Reset() {
	e.mu.Lock()
	e.endpointID = ""
	e.mu.Unlock()
	log.Printf("[EndpointInterceptor] Reset endpoint_id (will be reassigned by ras-grpc-gw on next request)")
}

// GetEndpointID возвращает текущий endpoint_id
func (e *EndpointInterceptor) GetEndpointID() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.endpointID
}
