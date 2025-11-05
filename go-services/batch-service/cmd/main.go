package main

import (
	"context"
	"flag"
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

var (
	// These variables are set by -ldflags during build
	Version   = "dev"
	Commit    = "unknown"
	BuildTime = "unknown"
)

var showVersion bool

func init() {
	// Register version flag
	flag.BoolVar(&showVersion, "version", false, "Show version information and exit")
}

func main() {
	flag.Parse()

	if showVersion {
		fmt.Printf("Service: cc1c-batch-service\n")
		fmt.Printf("Version: %s\n", Version)
		fmt.Printf("Commit: %s\n", Commit)
		fmt.Printf("Built: %s\n", BuildTime)
		os.Exit(0)
	}

	// Load configuration
	cfg := config.Load()

	log.Printf("Starting batch-service (cc1c-batch-service)")
	log.Printf("Version: %s, Commit: %s, Built: %s", Version, Commit, BuildTime)
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
