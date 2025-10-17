# Stage 1: Build
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy shared module first
COPY shared/ ./shared/

# Copy worker module
COPY worker/go.mod worker/go.sum ./worker/
WORKDIR /build/worker
RUN go mod download

# Copy source code
COPY worker/ .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o worker ./cmd/main.go

# Stage 2: Runtime
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/worker/worker .

# Copy config if exists
COPY --from=builder /build/worker/configs/ ./configs/

CMD ["./worker"]
