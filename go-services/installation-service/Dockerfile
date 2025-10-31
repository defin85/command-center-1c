# Build stage
FROM golang:1.24-windowsservercore-ltsc2022 AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
COPY ../shared /app/shared

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN go build -o bin/installation-service.exe ./cmd

# Runtime stage
FROM mcr.microsoft.com/windows/servercore:ltsc2022

WORKDIR /app

# Copy binary and config
COPY --from=builder /app/bin/installation-service.exe .
COPY --from=builder /app/configs/config.yaml ./configs/

# Expose API port
EXPOSE 8085

# Run the service
CMD ["installation-service.exe"]
