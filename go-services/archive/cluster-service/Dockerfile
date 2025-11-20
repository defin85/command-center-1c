# Multi-stage build для минимизации размера image

# Stage 1: Build
FROM golang:1.24-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build binary with version
ARG VERSION=dev
RUN go build -ldflags "-X github.com/command-center-1c/cluster-service/internal/version.Version=${VERSION}" \
    -o cluster-service cmd/main.go

# Stage 2: Runtime
FROM alpine:latest

# Install ca-certificates for HTTPS and wget for health checks
RUN apk --no-cache add ca-certificates wget

WORKDIR /root/

# Copy binary from builder
COPY --from=builder /app/cluster-service .

# Expose HTTP port
EXPOSE 8088

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8088/health || exit 1

# Run
CMD ["./cluster-service"]
