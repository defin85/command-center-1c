package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/command-center-1c/batch-service/internal/api"
	"github.com/command-center-1c/batch-service/internal/config"
	"github.com/command-center-1c/batch-service/internal/service"
)

func main() {
	// Load configuration
	cfg := config.Load()

	log.Printf("Starting batch-service...")
	log.Printf("Server: %s:%s", cfg.Server.Host, cfg.Server.Port)
	log.Printf("gRPC Gateway: %s", cfg.GRPC.GatewayAddr)
	log.Printf("1cv8.exe: %s", cfg.V8.ExePath)

	// Initialize services
	extensionInstaller := service.NewExtensionInstaller(
		cfg.V8.ExePath,
		cfg.V8.DefaultTimeout,
	)

	// Setup router
	router := api.SetupRouter(extensionInstaller)

	// Create HTTP server
	server := &http.Server{
		Addr:         fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port),
		Handler:      router,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	// Start server in a goroutine
	go func() {
		log.Printf("Server listening on %s", server.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown with 5 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
}
