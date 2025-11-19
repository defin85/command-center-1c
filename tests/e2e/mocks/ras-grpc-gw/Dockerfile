FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy mock service code
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Build mock binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o /ras-mock main.go

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates wget

WORKDIR /root/

COPY --from=builder /ras-mock .

EXPOSE 8081 9999

CMD ["./ras-mock"]
