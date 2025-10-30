# Production Deployment Guide

Руководство по развёртыванию `ras-grpc-gw` в production окружении.

**Service:** ras-grpc-gw
**Repository:** https://github.com/command-center-1c/ras-grpc-gw
**Version:** v1.0.0-cc+
**Document Version:** 1.0
**Last Updated:** 2025-01-17

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Deployment Options](#deployment-options)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Configuration](#configuration)
7. [Monitoring](#monitoring)
8. [Security](#security)
9. [High Availability](#high-availability)
10. [Troubleshooting](#troubleshooting)
11. [Upgrade Procedure](#upgrade-procedure)
12. [Rollback Procedure](#rollback-procedure)

---

## Prerequisites

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 2 GB
- Storage: 10 GB
- Network: 100 Mbps

**Recommended (Production):**
- CPU: 4 cores
- RAM: 4 GB
- Storage: 50 GB (для логов и метрик)
- Network: 1 Gbps

### Software Requirements

| Component | Version | Required |
|-----------|---------|----------|
| Kubernetes | 1.27+ | Рекомендуется |
| Docker | 20.10+ | Да |
| 1C RAC CLI | 8.3.18+ | Да (должен быть установлен) |
| PostgreSQL | 14+ | Нет (для хранения состояния, опционально) |
| Redis | 7.0+ | Нет (для кеширования, опционально) |

### Network Requirements

**Inbound:**
- `50051/tcp` - gRPC API (от клиентов)
- `8080/tcp` - HTTP metrics + health checks (от Prometheus, LB)

**Outbound:**
- `1545/tcp` - 1C RAS Server (агент администрирования)
- `443/tcp` - Internet (для pull образов, обновлений)

**DNS:**
- Имя сервиса: `ras-grpc-gw.example.com`
- Internal DNS: `ras-grpc-gw.default.svc.cluster.local` (Kubernetes)

---

## Architecture Overview

### Production Topology

```
                   Internet
                      │
                      ▼
              ┌───────────────┐
              │  Load         │
              │  Balancer     │
              │  (L4/L7)      │
              └───────┬───────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌────────┐   ┌────────┐   ┌────────┐
   │ ras-   │   │ ras-   │   │ ras-   │
   │ grpc-  │   │ grpc-  │   │ grpc-  │
   │ gw-1   │   │ gw-2   │   │ gw-3   │
   └───┬────┘   └───┬────┘   └───┬────┘
       │            │            │
       └────────────┼────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  1C RAS       │
            │  Server       │
            │  :1545        │
            └───────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    ┌──────┐   ┌──────┐   ┌──────┐
    │ 1C   │   │ 1C   │   │ 1C   │
    │ DB 1 │   │ DB 2 │   │ DB N │
    └──────┘   └──────┘   └──────┘
```

### Component Responsibilities

| Component | Responsibility | Scaling Strategy |
|-----------|----------------|------------------|
| ras-grpc-gw | gRPC API gateway | Horizontal (3+ replicas) |
| Load Balancer | Traffic distribution | Managed service (AWS ELB, GCP LB) |
| 1C RAS Server | Database cluster management | Single instance (1С limitation) |
| Prometheus | Metrics collection | Single instance + federation |
| Grafana | Visualization | Single instance + HA (optional) |

---

## Deployment Options

### Option 1: Kubernetes (Recommended)

**Pros:**
- Auto-scaling (HPA)
- Self-healing (liveness/readiness probes)
- Rolling updates
- Resource management
- Service discovery

**Cons:**
- Требует Kubernetes expertise
- Overhead для небольших deployments

**Use case:** Production окружение с > 3 replicas

### Option 2: Docker Compose

**Pros:**
- Простая настройка
- Быстрый старт
- Подходит для небольших окружений

**Cons:**
- Нет auto-scaling
- Ручное управление replicas
- Limited orchestration

**Use case:** Staging, development, небольшие production (< 3 replicas)

### Option 3: Standalone Binary

**Pros:**
- Минимальные зависимости
- Прямой контроль

**Cons:**
- Нет containerization benefits
- Ручное управление зависимостями
- Сложнее scaling

**Use case:** Testing, POC, legacy systems

---

## Docker Deployment

### Quick Start

```bash
# 1. Pull latest image
docker pull ghcr.io/command-center-1c/ras-grpc-gw:v1.0.0-cc

# 2. Create config file
mkdir -p /opt/ras-grpc-gw/config
cat > /opt/ras-grpc-gw/config/config.yaml <<'EOF'
server:
  grpc_port: 50051
  http_port: 8080
  shutdown_timeout: 30s

rac:
  cli_path: /usr/bin/rac
  server_address: localhost:1545
  timeout: 30s
  max_connections: 10

logging:
  level: info
  format: json
  output: stdout

metrics:
  enabled: true
  path: /metrics
EOF

# 3. Run container
docker run -d \
  --name ras-grpc-gw \
  --restart unless-stopped \
  -p 50051:50051 \
  -p 8080:8080 \
  -v /opt/ras-grpc-gw/config:/app/config:ro \
  -v /usr/bin/rac:/usr/bin/rac:ro \
  --health-cmd="wget -q --spider http://localhost:8080/health || exit 1" \
  --health-interval=30s \
  --health-timeout=5s \
  --health-retries=3 \
  ghcr.io/command-center-1c/ras-grpc-gw:v1.0.0-cc

# 4. Verify deployment
docker ps | grep ras-grpc-gw
docker logs ras-grpc-gw
curl http://localhost:8080/health
```

### Docker Compose

```yaml
# docker-compose.yaml
version: '3.8'

services:
  ras-grpc-gw:
    image: ghcr.io/command-center-1c/ras-grpc-gw:v1.0.0-cc
    container_name: ras-grpc-gw
    restart: unless-stopped

    ports:
      - "50051:50051"  # gRPC
      - "8080:8080"    # HTTP (metrics, health)

    volumes:
      - ./config:/app/config:ro
      - /usr/bin/rac:/usr/bin/rac:ro

    environment:
      - RAC_SERVER_ADDRESS=ras-server:1545
      - LOG_LEVEL=info
      - LOG_FORMAT=json

    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  # Optional: Prometheus для метрик
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'

  # Optional: Grafana для визуализации
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  prometheus-data:
  grafana-data:
```

**Usage:**
```bash
docker-compose up -d
docker-compose logs -f ras-grpc-gw
docker-compose ps
```

---

## Kubernetes Deployment

### Namespace Setup

```bash
# Create namespace
kubectl create namespace ras-grpc-gw

# Set context
kubectl config set-context --current --namespace=ras-grpc-gw
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ras-grpc-gw-config
  namespace: ras-grpc-gw
data:
  config.yaml: |
    server:
      grpc_port: 50051
      http_port: 8080
      shutdown_timeout: 30s

    rac:
      cli_path: /usr/bin/rac
      server_address: ras-server.1c-system.svc.cluster.local:1545
      timeout: 30s
      max_connections: 10
      retry:
        max_attempts: 3
        initial_backoff: 1s
        max_backoff: 10s

    logging:
      level: info
      format: json
      output: stdout

    metrics:
      enabled: true
      path: /metrics
```

### Secret (if needed)

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ras-grpc-gw-secret
  namespace: ras-grpc-gw
type: Opaque
stringData:
  rac-username: "admin"
  rac-password: "secure-password"
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ras-grpc-gw
  namespace: ras-grpc-gw
  labels:
    app: ras-grpc-gw
    version: v1.0.0-cc
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0

  selector:
    matchLabels:
      app: ras-grpc-gw

  template:
    metadata:
      labels:
        app: ras-grpc-gw
        version: v1.0.0-cc
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"

    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      containers:
      - name: ras-grpc-gw
        image: ghcr.io/command-center-1c/ras-grpc-gw:v1.0.0-cc
        imagePullPolicy: IfNotPresent

        ports:
        - name: grpc
          containerPort: 50051
          protocol: TCP
        - name: http
          containerPort: 8080
          protocol: TCP

        env:
        - name: CONFIG_FILE
          value: /app/config/config.yaml
        - name: LOG_LEVEL
          value: info

        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: rac-cli
          mountPath: /usr/bin/rac
          subPath: rac
          readOnly: true

        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi

        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 15
          periodSeconds: 20
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3

        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]

      volumes:
      - name: config
        configMap:
          name: ras-grpc-gw-config
      - name: rac-cli
        hostPath:
          path: /usr/bin/rac
          type: File

      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: ras-grpc-gw
              topologyKey: kubernetes.io/hostname
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ras-grpc-gw
  namespace: ras-grpc-gw
  labels:
    app: ras-grpc-gw
spec:
  type: ClusterIP
  ports:
  - name: grpc
    port: 50051
    targetPort: grpc
    protocol: TCP
  - name: http
    port: 8080
    targetPort: http
    protocol: TCP
  selector:
    app: ras-grpc-gw

---
# External LoadBalancer (optional)
apiVersion: v1
kind: Service
metadata:
  name: ras-grpc-gw-external
  namespace: ras-grpc-gw
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
spec:
  type: LoadBalancer
  ports:
  - name: grpc
    port: 50051
    targetPort: grpc
    protocol: TCP
  selector:
    app: ras-grpc-gw
```

### HorizontalPodAutoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ras-grpc-gw-hpa
  namespace: ras-grpc-gw
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ras-grpc-gw

  minReplicas: 3
  maxReplicas: 10

  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70

  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 2
        periodSeconds: 30
      selectPolicy: Max
```

### Deploy Commands

```bash
# Apply all manifests
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Wait for rollout
kubectl rollout status deployment/ras-grpc-gw -n ras-grpc-gw

# Verify deployment
kubectl get pods -n ras-grpc-gw
kubectl get svc -n ras-grpc-gw
kubectl get hpa -n ras-grpc-gw

# Check logs
kubectl logs -l app=ras-grpc-gw -n ras-grpc-gw --tail=100 -f
```

---

## Configuration

### Configuration Hierarchy

Конфигурация загружается в следующем порядке (последующие override предыдущие):

1. Default values (hardcoded)
2. Config file (`/app/config/config.yaml`)
3. Environment variables (prefix: `RAS_`)

### Environment Variables

```bash
# Server
RAS_SERVER_GRPC_PORT=50051
RAS_SERVER_HTTP_PORT=8080
RAS_SERVER_SHUTDOWN_TIMEOUT=30s

# RAC
RAS_RAC_CLI_PATH=/usr/bin/rac
RAS_RAC_SERVER_ADDRESS=localhost:1545
RAS_RAC_TIMEOUT=30s
RAS_RAC_MAX_CONNECTIONS=10

# Logging
RAS_LOGGING_LEVEL=info          # debug, info, warn, error
RAS_LOGGING_FORMAT=json         # json, console
RAS_LOGGING_OUTPUT=stdout       # stdout, file

# Metrics
RAS_METRICS_ENABLED=true
RAS_METRICS_PATH=/metrics
```

### Advanced Configuration

```yaml
# config/config.yaml (full)
server:
  grpc_port: 50051
  http_port: 8080
  shutdown_timeout: 30s
  max_connections: 1000
  keepalive:
    time: 60s
    timeout: 20s

rac:
  cli_path: /usr/bin/rac
  server_address: localhost:1545
  timeout: 30s
  max_connections: 10
  retry:
    max_attempts: 3
    initial_backoff: 1s
    max_backoff: 10s
    multiplier: 2
  auth:
    username: ${RAC_USERNAME}  # from env or secret
    password: ${RAC_PASSWORD}

logging:
  level: info
  format: json
  output: stdout
  fields:
    service: ras-grpc-gw
    version: v1.0.0-cc
    environment: production

metrics:
  enabled: true
  path: /metrics
  namespace: ras_grpc
  subsystem: server

health:
  liveness_path: /health
  readiness_path: /ready
  rac_check: true

security:
  tls:
    enabled: false
    cert_file: /app/certs/tls.crt
    key_file: /app/certs/tls.key
    ca_file: /app/certs/ca.crt
  rate_limit:
    enabled: true
    requests_per_minute: 100
    burst: 200
```

---

## Monitoring

### Prometheus Metrics

**Метрики сервиса:**

```promql
# Request rate (QPS)
rate(ras_grpc_requests_total[1m])

# Error rate
rate(ras_grpc_errors_total[1m]) / rate(ras_grpc_requests_total[1m])

# Latency (99th percentile)
histogram_quantile(0.99, rate(ras_grpc_request_duration_seconds_bucket[5m]))

# RAC CLI calls
rate(rac_cli_calls_total[1m])

# RAC CLI latency
histogram_quantile(0.99, rate(rac_cli_duration_seconds_bucket[5m]))
```

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ras-grpc-gw'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - ras-grpc-gw
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+):(.+)
        replacement: $1:$2
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
```

### Grafana Dashboard

**Импорт готового dashboard:**
```bash
# Dashboard JSON в репозитории
curl -o dashboard.json https://raw.githubusercontent.com/command-center-1c/ras-grpc-gw/main/grafana/dashboard.json

# Импорт через UI
# Grafana → Dashboards → Import → Upload JSON file
```

**Основные панели:**
- Request rate (QPS)
- Error rate (%)
- Latency (p50, p95, p99)
- Active connections
- RAC CLI calls
- Pod CPU/Memory usage

### Alerting Rules

```yaml
# alerts.yml
groups:
  - name: ras-grpc-gw
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: |
          (rate(ras_grpc_errors_total[5m]) / rate(ras_grpc_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate (>5%)"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.99, rate(ras_grpc_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency (p99 > 1s)"
          description: "p99 latency is {{ $value }}s"

      - alert: ServiceDown
        expr: up{job="ras-grpc-gw"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "ras-grpc-gw is not responding"

      - alert: PodCrashLooping
        expr: |
          rate(kube_pod_container_status_restarts_total{namespace="ras-grpc-gw"}[5m]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pod is crash looping"
          description: "Pod {{ $labels.pod }} is restarting"
```

---

## Security

### TLS Configuration

**Включить TLS для gRPC:**

```yaml
# config.yaml
security:
  tls:
    enabled: true
    cert_file: /app/certs/tls.crt
    key_file: /app/certs/tls.key
    ca_file: /app/certs/ca.crt
    client_auth: require  # none, request, require
```

**Генерация self-signed сертификатов (dev only):**
```bash
# НЕ используйте в production!
openssl req -x509 -newkey rsa:4096 -keyout tls.key -out tls.crt -days 365 -nodes \
  -subj "/CN=ras-grpc-gw.example.com"
```

**Production: Использовать cert-manager в Kubernetes:**
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ras-grpc-gw-tls
  namespace: ras-grpc-gw
spec:
  secretName: ras-grpc-gw-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - ras-grpc-gw.example.com
```

### Network Policies

```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ras-grpc-gw-policy
  namespace: ras-grpc-gw
spec:
  podSelector:
    matchLabels:
      app: ras-grpc-gw

  policyTypes:
    - Ingress
    - Egress

  ingress:
    # Allow from load balancer
    - from:
      - namespaceSelector:
          matchLabels:
            name: ingress-nginx
      ports:
      - protocol: TCP
        port: 50051

    # Allow from Prometheus
    - from:
      - namespaceSelector:
          matchLabels:
            name: monitoring
      ports:
      - protocol: TCP
        port: 8080

  egress:
    # Allow to RAS server
    - to:
      - namespaceSelector:
          matchLabels:
            name: 1c-system
      ports:
      - protocol: TCP
        port: 1545

    # Allow to DNS
    - to:
      - namespaceSelector:
          matchLabels:
            name: kube-system
      ports:
      - protocol: UDP
        port: 53
```

### RBAC (Kubernetes)

```yaml
# k8s/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ras-grpc-gw
  namespace: ras-grpc-gw

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ras-grpc-gw-role
  namespace: ras-grpc-gw
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ras-grpc-gw-rolebinding
  namespace: ras-grpc-gw
subjects:
  - kind: ServiceAccount
    name: ras-grpc-gw
    namespace: ras-grpc-gw
roleRef:
  kind: Role
  name: ras-grpc-gw-role
  apiGroup: rbac.authorization.k8s.io
```

---

## High Availability

### Multi-Region Deployment

```
Region 1 (Primary)          Region 2 (DR)
┌─────────────────┐         ┌─────────────────┐
│ ras-grpc-gw     │         │ ras-grpc-gw     │
│ replicas: 3     │ <-----> │ replicas: 3     │
└────────┬────────┘         └────────┬────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ RAS Server 1    │         │ RAS Server 2    │
└─────────────────┘         └─────────────────┘
```

**DNS Failover:**
```
ras-grpc-gw.example.com
  → 10.0.1.100 (Region 1) - Primary
  → 10.0.2.100 (Region 2) - Failover (TTL: 60s)
```

### Load Balancing Strategies

**Round Robin (default):**
```yaml
# AWS NLB example
annotations:
  service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
  service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
```

**Least Connections:**
```nginx
# Nginx ingress example
upstream ras-grpc-gw {
    least_conn;
    server 10.0.1.1:50051;
    server 10.0.1.2:50051;
    server 10.0.1.3:50051;
}
```

### Health Check Configuration

**Aggressive (быстрый failover):**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5       # Каждые 5 секунд
  timeoutSeconds: 2
  failureThreshold: 2    # 2 неудачи = restart
```

**Conservative (стабильность):**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30      # Каждые 30 секунд
  timeoutSeconds: 5
  failureThreshold: 5    # 5 неудач = restart
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Pods CrashLooping

**Symptoms:**
```bash
kubectl get pods -n ras-grpc-gw
# NAME                           READY   STATUS             RESTARTS   AGE
# ras-grpc-gw-5d7f9c8b4f-abc12   0/1     CrashLoopBackOff   5          3m
```

**Diagnosis:**
```bash
# Check logs
kubectl logs ras-grpc-gw-5d7f9c8b4f-abc12 -n ras-grpc-gw

# Check events
kubectl describe pod ras-grpc-gw-5d7f9c8b4f-abc12 -n ras-grpc-gw
```

**Common Causes:**
1. **RAC CLI не найден:**
   ```
   Error: exec: "/usr/bin/rac": stat /usr/bin/rac: no such file or directory
   ```
   **Fix:** Убедитесь что `/usr/bin/rac` примонтирован в pod
   ```yaml
   volumeMounts:
   - name: rac-cli
     mountPath: /usr/bin/rac
     subPath: rac
     readOnly: true
   ```

2. **Неверный config:**
   ```
   Error: failed to load config: yaml: unmarshal errors
   ```
   **Fix:** Проверьте синтаксис YAML в ConfigMap

3. **Недоступен RAS server:**
   ```
   Error: failed to connect to RAS: dial tcp 10.0.1.100:1545: connect: connection refused
   ```
   **Fix:** Проверьте сетевую доступность

#### Issue 2: High Latency

**Symptoms:**
```promql
# p99 latency > 1s
histogram_quantile(0.99, rate(ras_grpc_request_duration_seconds_bucket[5m])) > 1
```

**Diagnosis:**
```bash
# Check RAC CLI latency
kubectl logs -l app=ras-grpc-gw -n ras-grpc-gw | grep "rac_cli_duration"

# Check pod resources
kubectl top pods -n ras-grpc-gw
```

**Common Causes:**
1. **RAC server перегружен:**
   - Scale out: добавить replicas
   - Optimize: уменьшить `max_connections`

2. **CPU throttling:**
   ```bash
   kubectl describe pod <pod-name> -n ras-grpc-gw | grep -A 5 "Limits"
   ```
   **Fix:** Увеличить CPU limits

3. **Network latency:**
   ```bash
   # Ping RAS server из pod
   kubectl exec -it <pod-name> -n ras-grpc-gw -- ping ras-server.1c-system.svc.cluster.local
   ```

#### Issue 3: Service Unavailable (503)

**Symptoms:**
```bash
curl http://ras-grpc-gw.example.com:50051
# HTTP 503 Service Unavailable
```

**Diagnosis:**
```bash
# Check service endpoints
kubectl get endpoints ras-grpc-gw -n ras-grpc-gw

# Should show ready pods:
# NAME           ENDPOINTS                                           AGE
# ras-grpc-gw    10.0.1.1:50051,10.0.1.2:50051,10.0.1.3:50051        1d
```

**Common Causes:**
1. **All pods failing readiness probe:**
   ```bash
   kubectl get pods -n ras-grpc-gw
   # READY 0/1 means readiness probe failing
   ```
   **Fix:** Check `/ready` endpoint logs

2. **No healthy backends:**
   ```bash
   kubectl describe service ras-grpc-gw -n ras-grpc-gw
   ```
   **Fix:** Investigate pod health

### Debug Commands

```bash
# Get comprehensive pod info
kubectl describe pod <pod-name> -n ras-grpc-gw

# Live logs
kubectl logs -f <pod-name> -n ras-grpc-gw

# Previous container logs (after restart)
kubectl logs <pod-name> -n ras-grpc-gw --previous

# Exec into pod
kubectl exec -it <pod-name> -n ras-grpc-gw -- /bin/sh

# Test RAC CLI from pod
kubectl exec -it <pod-name> -n ras-grpc-gw -- /usr/bin/rac cluster list --server=localhost:1545

# Check network connectivity
kubectl exec -it <pod-name> -n ras-grpc-gw -- nc -zv ras-server.1c-system.svc.cluster.local 1545

# Profiling (if enabled)
kubectl port-forward <pod-name> 6060:6060 -n ras-grpc-gw
go tool pprof http://localhost:6060/debug/pprof/heap
```

---

## Upgrade Procedure

### Pre-Upgrade Checklist

- [ ] Review release notes for breaking changes
- [ ] Backup current configuration (ConfigMap, Secrets)
- [ ] Notify users of maintenance window
- [ ] Verify rollback procedure
- [ ] Test upgrade in staging environment

### Rolling Update (Zero Downtime)

```bash
# 1. Update image version
kubectl set image deployment/ras-grpc-gw \
  ras-grpc-gw=ghcr.io/command-center-1c/ras-grpc-gw:v1.1.0-cc \
  -n ras-grpc-gw

# 2. Watch rollout progress
kubectl rollout status deployment/ras-grpc-gw -n ras-grpc-gw

# 3. Verify new pods
kubectl get pods -n ras-grpc-gw -l app=ras-grpc-gw

# 4. Check logs for errors
kubectl logs -l app=ras-grpc-gw -n ras-grpc-gw --tail=100

# 5. Validate functionality
grpcurl -plaintext ras-grpc-gw.example.com:50051 list
```

### Blue-Green Deployment

```bash
# 1. Create green deployment
kubectl apply -f k8s/deployment-green.yaml

# 2. Wait for ready
kubectl wait --for=condition=ready pod -l app=ras-grpc-gw,version=green -n ras-grpc-gw --timeout=300s

# 3. Switch service to green
kubectl patch service ras-grpc-gw -n ras-grpc-gw -p '{"spec":{"selector":{"version":"green"}}}'

# 4. Validate traffic
# Monitor metrics for 15 minutes

# 5. Delete blue deployment
kubectl delete deployment ras-grpc-gw-blue -n ras-grpc-gw
```

---

## Rollback Procedure

### Kubernetes Rollback

```bash
# 1. Immediate rollback to previous version
kubectl rollout undo deployment/ras-grpc-gw -n ras-grpc-gw

# 2. Rollback to specific revision
kubectl rollout history deployment/ras-grpc-gw -n ras-grpc-gw
kubectl rollout undo deployment/ras-grpc-gw --to-revision=3 -n ras-grpc-gw

# 3. Verify rollback
kubectl rollout status deployment/ras-grpc-gw -n ras-grpc-gw
kubectl get pods -n ras-grpc-gw

# 4. Confirm functionality
curl http://ras-grpc-gw.example.com:8080/health
```

### Docker Compose Rollback

```bash
# 1. Stop current version
docker-compose down

# 2. Update image version in docker-compose.yaml
sed -i 's/v1.1.0-cc/v1.0.0-cc/g' docker-compose.yaml

# 3. Start previous version
docker-compose up -d

# 4. Verify
docker-compose ps
docker-compose logs -f ras-grpc-gw
```

---

## Appendix

### Resource Sizing Guide

| Workload | Pods | CPU/pod | Memory/pod | Total CPU | Total Memory |
|----------|------|---------|------------|-----------|--------------|
| Dev/Test | 1 | 500m | 512Mi | 500m | 512Mi |
| Staging | 2 | 1 | 1Gi | 2 | 2Gi |
| Production (Small) | 3 | 2 | 2Gi | 6 | 6Gi |
| Production (Medium) | 5 | 2 | 2Gi | 10 | 10Gi |
| Production (Large) | 10 | 4 | 4Gi | 40 | 40Gi |

### Performance Benchmarks

**Target Metrics (v1.0.0-cc):**
- **Throughput:** 1000 RPS per pod
- **Latency (p99):** < 100ms
- **Error Rate:** < 0.1%
- **CPU Usage:** < 70% under load
- **Memory Usage:** < 80% under load

**Load Testing:**
```bash
# k6 load test
k6 run --vus 100 --duration 5m tests/load/benchmark.js
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Next Review:** 2025-02-17
**Owner:** CommandCenter1C Team
