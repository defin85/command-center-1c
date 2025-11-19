package main

import (
	"context"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// MockRASService - мок RAS сервиса для E2E тестов
type MockRASService struct {
	mu            sync.RWMutex
	lockedBases   map[string]bool
	lockBehavior  string // "success", "fail"
	sessions      map[string]int
}

func NewMockRASService() *MockRASService {
	return &MockRASService{
		lockedBases:  make(map[string]bool),
		lockBehavior: "success",
		sessions:     make(map[string]int),
	}
}

// IsLocked - проверка блокировки базы
func (m *MockRASService) IsLocked(dbID string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.lockedBases[dbID]
}

// Lock - блокировка базы
// FIXED: Issue #3 - Thread safety - initialize session count for testing
func (m *MockRASService) Lock(dbID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.lockBehavior == "fail" {
		log.Printf("[MOCK RAS] Lock FAILED (configured behavior): %s", dbID)
		return status.Error(codes.Internal, "mock lock failure")
	}

	if m.lockedBases[dbID] {
		log.Printf("[MOCK RAS] Database already locked: %s", dbID)
		return status.Error(codes.FailedPrecondition, "database already locked")
	}

	m.lockedBases[dbID] = true

	// Initialize session count for testing (if not exists)
	if _, ok := m.sessions[dbID]; !ok {
		m.sessions[dbID] = 5 // Mock: 5 active sessions for testing
	}

	log.Printf("[MOCK RAS] Locked database: %s (sessions: %d)", dbID, m.sessions[dbID])
	return nil
}

// Unlock - разблокировка базы
func (m *MockRASService) Unlock(dbID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	delete(m.lockedBases, dbID)
	log.Printf("[MOCK RAS] Unlocked database: %s", dbID)
	return nil
}

// TerminateSessions - завершение сессий
func (m *MockRASService) TerminateSessions(dbID string) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	count := m.sessions[dbID]
	m.sessions[dbID] = 0
	log.Printf("[MOCK RAS] Terminated %d sessions for database: %s", count, dbID)
	return count, nil
}

// SetLockBehavior - установка поведения mock для тестов
func (m *MockRASService) SetLockBehavior(behavior string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.lockBehavior = behavior
}

func setupHTTPServer(mockService *MockRASService) *http.Server {
	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	// Health check endpoint
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"service": "ras-mock",
			"status":  "healthy",
			"mode":    "mock",
		})
	})

	// Mock Lock endpoint
	r.POST("/api/v1/lock", func(c *gin.Context) {
		var req struct {
			DatabaseID string `json:"database_id"`
		}
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		if err := mockService.Lock(req.DatabaseID); err != nil {
			c.JSON(500, gin.H{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		c.JSON(200, gin.H{
			"status": "success",
			"locked": true,
		})
	})

	// Mock Unlock endpoint
	r.POST("/api/v1/unlock", func(c *gin.Context) {
		var req struct {
			DatabaseID string `json:"database_id"`
		}
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		if err := mockService.Unlock(req.DatabaseID); err != nil {
			c.JSON(500, gin.H{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		c.JSON(200, gin.H{
			"status":   "success",
			"unlocked": true,
		})
	})

	// Mock Terminate Sessions endpoint
	r.POST("/api/v1/sessions/terminate", func(c *gin.Context) {
		var req struct {
			DatabaseID string `json:"database_id"`
		}
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		count, err := mockService.TerminateSessions(req.DatabaseID)
		if err != nil {
			c.JSON(500, gin.H{
				"status": "error",
				"error":  err.Error(),
			})
			return
		}

		c.JSON(200, gin.H{
			"status":          "success",
			"sessions_closed": count,
		})
	})

	// Control endpoint для установки поведения в тестах
	r.POST("/api/v1/mock/set-behavior", func(c *gin.Context) {
		var req struct {
			LockBehavior string `json:"lock_behavior"` // "success" or "fail"
		}
		if err := c.BindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": err.Error()})
			return
		}

		mockService.SetLockBehavior(req.LockBehavior)
		c.JSON(200, gin.H{
			"status":        "success",
			"lock_behavior": req.LockBehavior,
		})
	})

	return &http.Server{
		Addr:    ":8081",
		Handler: r,
	}
}

func setupGRPCServer(mockService *MockRASService) *grpc.Server {
	// Простой gRPC сервер для совместимости
	// В реальности E2E тесты будут использовать HTTP endpoints
	grpcServer := grpc.NewServer()
	return grpcServer
}

func main() {
	mockService := NewMockRASService()

	// HTTP server для HTTP endpoints
	httpServer := setupHTTPServer(mockService)

	// gRPC server (минимальный для совместимости)
	grpcServer := setupGRPCServer(mockService)
	lis, err := net.Listen("tcp", ":9999")
	if err != nil {
		log.Fatalf("Failed to listen on :9999: %v", err)
	}

	// Запуск серверов
	go func() {
		log.Println("[MOCK RAS] Starting HTTP server on :8081")
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server failed: %v", err)
		}
	}()

	go func() {
		log.Println("[MOCK RAS] Starting gRPC server on :9999")
		if err := grpcServer.Serve(lis); err != nil {
			log.Fatalf("gRPC server failed: %v", err)
		}
	}()

	log.Println("[MOCK RAS] Mock RAS service started successfully")

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[MOCK RAS] Shutting down servers...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("HTTP server shutdown error: %v", err)
	}

	grpcServer.GracefulStop()

	log.Println("[MOCK RAS] Servers stopped")
}
