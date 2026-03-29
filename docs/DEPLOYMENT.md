# Helix Integration Deployment Guide

Production deployment guide for the Helix Integration Meta-Package.

## Prerequisites

- Python 3.9+
- Docker & Docker Compose
- Kubernetes 1.20+
- Redis 6.0+
- PostgreSQL 12+

## Installation

### From PyPI

```bash
pip install helix-integration
```

### From Source

```bash
git clone https://github.com/Deathcharge/helix-integration.git
cd helix-integration
pip install -e .
```

## Single-Node Deployment

### Development

```bash
pip install -e ".[dev]"
python -m helix_integration --mode=development --debug
```

### Production

```bash
pip install helix-integration
python -m helix_integration --config config.yaml
```

## Docker Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: helix
      POSTGRES_USER: helix
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
  helix:
    build: .
    ports:
      - "8000:8000"
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://helix:secure_password@postgres:5432/helix
      MODE: production
    depends_on:
      - redis
      - postgres
```

## Kubernetes Deployment

### Prerequisites

```bash
kubectl create namespace helix
kubectl create secret generic helix-secrets \
  --from-literal=redis-url=redis://redis:6379 \
  --from-literal=database-url=postgresql://user:pass@postgres:5432/helix \
  -n helix
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: helix-integration
  namespace: helix
spec:
  replicas: 3
  selector:
    matchLabels:
      app: helix-integration
  template:
    metadata:
      labels:
        app: helix-integration
    spec:
      containers:
      - name: helix
        image: helix/integration:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: helix-secrets
              key: redis-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: helix-secrets
              key: database-url
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
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| MODE | deployment mode | development |
| HOST | server host | 0.0.0.0 |
| PORT | server port | 8000 |
| REDIS_URL | Redis connection | redis://localhost:6379 |
| DATABASE_URL | PostgreSQL connection | postgresql://localhost/helix |

## Health Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Monitoring

- Prometheus metrics at `:9090/metrics`
- Jaeger tracing at `localhost:16686`

## Scaling

```bash
kubectl scale deployment helix-integration --replicas=5 -n helix
```

## Backup

```bash
pg_dump postgresql://user:pass@localhost/helix > backup.sql
psql postgresql://user:pass@localhost/helix < backup.sql
```

---

**Version:** 1.0
