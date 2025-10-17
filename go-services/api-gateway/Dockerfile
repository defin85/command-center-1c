# Stage 1: Build
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy shared module first
COPY shared/ ./shared/

# Copy api-gateway module
COPY api-gateway/go.mod api-gateway/go.sum ./api-gateway/
WORKDIR /build/api-gateway
RUN go mod download

# Copy source code
COPY api-gateway/ .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o api-gateway ./cmd/main.go

# Stage 2: Runtime
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/api-gateway/api-gateway .

# Copy config if exists
COPY --from=builder /build/api-gateway/configs/ ./configs/

EXPOSE 8080

CMD ["./api-gateway"]
