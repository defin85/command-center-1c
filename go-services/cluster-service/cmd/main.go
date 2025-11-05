package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/command-center-1c/cluster-service/internal/api"
	"github.com/command-center-1c/cluster-service/internal/api/handlers"
	"github.com/command-center-1c/cluster-service/internal/config"
	"github.com/command-center-1c/cluster-service/internal/grpc"
	"github.com/command-center-1c/cluster-service/internal/server"
	"github.com/command-center-1c/cluster-service/internal/service"
	"github.com/command-center-1c/cluster-service/internal/version"

	"go.uber.org/zap"
)

var showVersion bool

func init() {
	// Register version flag
	flag.BoolVar(&showVersion, "version", false, "Show version information and exit")
}

func main() {
	flag.Parse()

	if showVersion {
		fmt.Printf("Service: cc1c-cluster-service\n")
		fmt.Printf("Version: %s\n", version.Version)
		fmt.Printf("Commit: %s\n", version.Commit)
		fmt.Printf("Built: %s\n", version.BuildTime)
		os.Exit(0)
	}

	// Load config
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	// Initialize logger
	logger, err := initLogger(cfg.Log.Level)
	if err != nil {
		log.Fatalf("failed to initialize logger: %v", err)
	}
	defer logger.Sync()

	logger.Info("starting cluster-service",
		zap.String("service", "cc1c-cluster-service"),
		zap.String("version", version.Version),
		zap.String("commit", version.Commit),
		zap.String("buildTime", version.BuildTime),
		zap.String("grpc_gateway", cfg.GRPC.GatewayAddr),
	)

	// Initialize gRPC client
	grpcClient, err := grpc.NewClient(context.Background(), cfg.GRPC.GatewayAddr, logger)
	if err != nil {
		logger.Fatal("failed to create gRPC client", zap.Error(err))
	}
	defer grpcClient.Close()

	logger.Info("gRPC client initialized", zap.String("addr", cfg.GRPC.GatewayAddr))

	// Service layer
	monitoringService := service.NewMonitoringService(grpcClient, logger)

	// Handlers
	monitoringHandler := handlers.NewMonitoringHandler(
		monitoringService,
		cfg.GRPC.RequestTimeout,
		logger,
	)

	// Router
	router := api.SetupRouter(monitoringHandler, logger)

	// HTTP server
	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	srv := server.NewServer(
		router,
		addr,
		cfg.Server.ReadTimeout,
		cfg.Server.WriteTimeout,
		cfg.Server.ShutdownTimeout,
		logger,
	)

	// Start (blocks until shutdown)
	if err := srv.Start(); err != nil {
		logger.Fatal("server error", zap.Error(err))
	}
}

func initLogger(level string) (*zap.Logger, error) {
	var zapConfig zap.Config

	if level == "debug" {
		zapConfig = zap.NewDevelopmentConfig()
	} else {
		zapConfig = zap.NewProductionConfig()
	}

	zapLevel, err := zap.ParseAtomicLevel(level)
	if err != nil {
		return nil, fmt.Errorf("invalid log level: %w", err)
	}
	zapConfig.Level = zapLevel

	return zapConfig.Build()
}
