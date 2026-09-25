# Infrastructure Engineering Standards

> Docker, Kubernetes, Terraform, and infrastructure-as-code for MyWorld Central Portal.

## Table of Contents

1. [Container Strategy](#container-strategy)
2. [Dockerfile Best Practices](#dockerfile-best-practices)
3. [Docker Compose](#docker-compose)
4. [Kubernetes Manifests](#kubernetes-manifests)
5. [Infrastructure as Code (Terraform)](#infrastructure-as-code-terraform)
6. [Environment Management](#environment-management)
7. [Secrets Management](#secrets-management)
8. [Container Security](#container-security)
9. [Container Registries](#container-registries)
10. [Local Development](#local-development)

---

## Container Strategy

### Container Philosophy

- **One process per container** — Don't run multiple services in one container
- **Immutable infrastructure** — Containers should be replaceable, not modified
- **Stateless applications** — Store state in external services (DB, cache, object storage)
- **12-factor app compliant** — Config from env vars, logs to stdout, etc.

### When to Use Containers

✅ **Use containers for:**
- API servers (FastAPI, Node.js)
- Background workers (Celery)
- Web applications (Next.js)
- CLI tools and scripts

❌ **Don't containerize:**
- Database servers (use managed services like RDS)
- Stateful legacy applications
- System-level tools that need direct host access

---

## Dockerfile Best Practices

### Multi-Stage Builds (Python)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser ./src/myworld ./myworld
COPY --chown=appuser:appuser ./alembic ./alembic
COPY --chown=appuser:appuser ./alembic.ini ./

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with gunicorn for production
CMD ["gunicorn", "myworld.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### Multi-Stage Builds (Node.js / Next.js)

```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies
COPY package.json pnpm-lock.yaml ./
COPY packages/*/package.json ./packages/
RUN corepack enable && pnpm install --frozen-lockfile

# Stage 2: Builder
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build Next.js
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && pnpm build

# Stage 3: Runner (production)
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### Dockerfile Best Practices

```dockerfile
# ✅ GOOD: Use specific base image versions
FROM python:3.12.5-slim

# ❌ BAD: Use latest tag
FROM python:latest

# ✅ GOOD: Use slim/alpine variants
FROM python:3.12-slim

# ❌ BAD: Use full image (larger attack surface)
FROM python:3.12


# ✅ GOOD: Pin specific versions
RUN pip install fastapi==0.115.0

# ❌ BAD: Unpinned versions
RUN pip install fastapi


# ✅ GOOD: Combine RUN commands to reduce layers
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        package1 \
        package2 \
    && rm -rf /var/lib/apt/lists/*

# ❌ BAD: Multiple RUN commands
RUN apt-get update
RUN apt-get install -y package1
RUN rm -rf /var/lib/apt/lists/*


# ✅ GOOD: Use .dockerignore
# Create .dockerignore file:
# .git
# .github
# .vscode
# .env
# .env.local
# node_modules
# .next
# dist
# build
# __pycache__
# *.pyc
# .pytest_cache
# .coverage
# README.md
# docs/


# ✅ GOOD: Copy dependency files first (better layer caching)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Then copy source (changes more frequently)
COPY . .


# ✅ GOOD: Use exec form for CMD (proper signal handling)
CMD ["gunicorn", "app:app"]

# ❌ BAD: Shell form (doesn't handle signals)
CMD gunicorn app:app
```

### .dockerignore

```gitignore
# .dockerignore
.git
.gitignore
.github
.gitattributes

# Node
node_modules
.next
.nuxt
dist
build
coverage
*.log

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
.venv
venv
ENV
.pytest_cache
.coverage
htmlcov
*.egg-info
dist
build

# IDE
.vscode
.idea
*.swp
*.swo
.DS_Store

# Environment
.env
.env.local
.env.*.local

# Documentation
README.md
docs/
*.md

# CI/CD
.gitlab-ci.yml
.github/
.circleci/
```

---

## Docker Compose

### Development Stack

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    container_name: myworld-api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://myworld:myworld@db:5432/myworld
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: development
      DEBUG: "true"
      LOG_LEVEL: DEBUG
    volumes:
      - ./src:/app/src  # Hot reload in dev
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - myworld-net
    restart: unless-stopped

  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
      target: runtime
    container_name: myworld-web
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    volumes:
      - ./apps/web/src:/app/src
    depends_on:
      - api
    networks:
      - myworld-net
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    container_name: myworld-db
    environment:
      POSTGRES_USER: myworld
      POSTGRES_PASSWORD: myworld
      POSTGRES_DB: myworld
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myworld"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - myworld-net
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: myworld-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - myworld-net
    restart: unless-stopped

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    container_name: myworld-worker
    command: celery -A myworld.tasks.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://myworld:myworld@db:5432/myworld
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: development
    volumes:
      - ./src:/app/src
    depends_on:
      - db
      - redis
    networks:
      - myworld-net
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  myworld-net:
    driver: bridge
```

### Production Override

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  api:
    build:
      target: runtime
    environment:
      ENVIRONMENT: production
      DEBUG: "false"
    volumes: []  # No source code mounting in prod
    restart: always

  web:
    environment:
      NODE_ENV: production
    restart: always
```

### Useful Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f api
docker compose logs --tail=100 api

# Run migrations
docker compose exec api alembic upgrade head

# Open shell in container
docker compose exec api /bin/bash

# Restart single service
docker compose restart api

# Stop all services
docker compose down

# Stop and remove volumes (DESTRUCTIVE)
docker compose down -v

# Check resource usage
docker compose stats

# Run one-off command
docker compose run --rm api pytest
```

---

## Kubernetes Manifests

### Deployment

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: myworld
  labels:
    app: api
    version: v1
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: api
          image: myregistry/myworld-api:1.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: redis-url
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: secret-key
            - name: ENVIRONMENT
              value: "production"
            - name: LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      securityContext:
        fsGroup: 1000
      imagePullSecrets:
        - name: myregistry-credentials
```

### Service

```yaml
# k8s/api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: myworld
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
    - name: http
      port: 80
      targetPort: http
      protocol: TCP
```

### HorizontalPodAutoscaler

```yaml
# k8s/api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
  namespace: myworld
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 20
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
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
        - type: Pods
          value: 4
          periodSeconds: 30
      selectPolicy: Max
```

### ConfigMap and Secret

```yaml
# k8s/api-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: myworld
data:
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
  CORS_ORIGINS: '["https://myworld.example.com"]'
  DATABASE_POOL_SIZE: "20"
  DATABASE_MAX_OVERFLOW: "10"

---
# k8s/api-secret.yaml (use external secrets operator in real deployments)
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
  namespace: myworld
type: Opaque
stringData:
  database-url: "postgresql+asyncpg://user:pass@db:5432/myworld"
  redis-url: "redis://redis:6379/0"
  secret-key: "REPLACE_WITH_SECURE_RANDOM_VALUE"
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myworld
  namespace: myworld
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.myworld.example.com
      secretName: myworld-tls
  rules:
    - host: api.myworld.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

### Kustomize for Multiple Environments

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: myworld

resources:
  - ../../base

replicas:
  - name: api
    count: 5

patchesStrategicMerge:
  - api-deployment-patch.yaml

configMapGenerator:
  - name: api-config
    behavior: merge
    literals:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING
```

---

## Infrastructure as Code (Terraform)

### Project Structure

```
terraform/
├── modules/
│   ├── networking/
│   ├── database/
│   ├── compute/
│   └── monitoring/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── production/
└── shared/
```

### Module Example (RDS)

```hcl
# modules/database/main.tf
resource "aws_db_instance" "main" {
  identifier = var.identifier

  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_id

  db_name  = var.db_name
  username = var.username
  password = var.password  # Use AWS Secrets Manager in production
  port     = 5432

  vpc_security_group_ids = var.vpc_security_group_ids
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = var.backup_retention
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:00:00-Mon:03:00"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_arn             = var.monitoring_role_arn

  deletion_protection = var.deletion_protection
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.identifier}-final"

  tags = var.tags
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.identifier}-subnet-group"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}
```

```hcl
# modules/database/variables.tf
variable "identifier" {
  type        = string
  description = "Database instance identifier"
}

variable "instance_class" {
  type        = string
  default     = "db.t3.medium"
  description = "RDS instance class"
}

variable "allocated_storage" {
  type        = number
  default     = 20
  description = "Allocated storage in GB"
}

# ... more variables
```

```hcl
# modules/database/outputs.tf
output "endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "arn" {
  value = aws_db_instance.main.arn
}
```

### Environment Configuration

```hcl
# environments/production/main.tf
terraform {
  backend "s3" {
    bucket         = "myworld-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "myworld-terraform-locks"
  }
}

provider "aws" {
  region = "us-east-1"
  
  default_tags {
    tags = {
      Environment = "production"
      Project     = "myworld"
      ManagedBy   = "terraform"
    }
  }
}

module "vpc" {
  source      = "../../modules/networking"
  environment = "production"
  cidr_block  = "10.0.0.0/16"
}

module "database" {
  source                = "../../modules/database"
  identifier            = "myworld-prod-db"
  instance_class        = "db.r6g.large"
  allocated_storage     = 100
  max_allocated_storage = 1000
  db_name               = "myworld"
  username              = "myworld_admin"
  password              = data.aws_secretsmanager_secret_version.db_password.secret_string
  vpc_security_group_ids = [module.vpc.database_sg_id]
  subnet_ids            = module.vpc.private_subnet_ids
  deletion_protection   = true
  backup_retention      = 30
}
```

---

## Environment Management

### Environment Hierarchy

| Environment | Purpose | Data | Deploy Frequency |
|-------------|---------|------|------------------|
| **Local** | Developer machines | Synthetic | N/A |
| **Dev** | Shared dev environment | Synthetic | Every commit |
| **Staging** | Pre-production testing | Anonymized prod data | Every release |
| **Production** | Live users | Real data | Approved releases only |

### Environment Variables

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost/myworld_dev
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-not-for-production
CORS_ORIGINS=["http://localhost:3000"]

# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=${SECRET_DATABASE_URL}
REDIS_URL=${SECRET_REDIS_URL}
SECRET_KEY=${SECRET_JWT_SECRET}
CORS_ORIGINS=["https://myworld.example.com"]
```

### Never Commit Secrets

```gitignore
# .gitignore
.env
.env.local
.env.*.local
*.pem
*.key
secrets/
```

---

## Secrets Management

### Strategy by Environment

| Environment | Tool |
|-------------|------|
| **Local** | .env file (not committed) |
| **Dev/Staging** | AWS Secrets Manager / Doppler |
| **Production** | AWS Secrets Manager + KMS encryption |

### Using Secrets in K8s (External Secrets Operator)

```yaml
# k8s/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-secrets
  namespace: myworld
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-secrets
    creationPolicy: Owner
  data:
    - secretKey: database-url
      remoteRef:
        key: myworld/production/database
        property: url
    - secretKey: secret-key
      remoteRef:
        key: myworld/production/jwt
        property: secret
```

### Application Code (Python)

```python
# GOOD: Load from environment
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    
    class Config:
        env_file = ".env"


settings = Settings()


# GOOD: Use secrets manager for sensitive data in production
import boto3
import json


def get_secret(secret_name: str) -> dict:
    """Fetch secret from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name="us-east-1")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


# In production
if settings.is_production:
    secrets = get_secret("myworld/production/api")
    database_url = secrets["DATABASE_URL"]
else:
    database_url = settings.database_url
```

---

## Container Security

### Image Scanning

```yaml
# .github/workflows/security-scan.yml
name: Container Security Scan

on:
  push:
    branches: [main]
  pull_request:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build image
        run: docker build -t myworld-api:${{ github.sha }} .
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myworld-api:${{ github.sha }}
          format: "sarif"
          output: "trivy-results.sarif"
          severity: "CRITICAL,HIGH"
      
      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: "trivy-results.sarif"
```

### Security Best Practices

```dockerfile
# ✅ GOOD: Use distroless or minimal base images
FROM gcr.io/distroless/python3-debian12

# ✅ GOOD: Run as non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# ✅ GOOD: Read-only root filesystem
# In Kubernetes pod spec:
# securityContext:
#   readOnlyRootFilesystem: true
#   runAsNonRoot: true
#   allowPrivilegeEscalation: false
#   capabilities:
#     drop: [ALL]

# ✅ GOOD: Pin package versions
RUN apt-get install -y package=1.2.3

# ✅ GOOD: Clean up package manager cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# ✅ GOOD: Use multi-stage builds (smaller final image)
FROM python:3.12-slim AS builder
# ... build stuff
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /opt/venv /opt/venv
```

### Image Size Optimization

```dockerfile
# ✅ GOOD: Use .dockerignore (see above)
# ✅ GOOD: Multi-stage builds
# ✅ GOOD: Use slim/alpine base images
# ✅ GOOD: Combine RUN commands
# ✅ GOOD: Clean up after package install

# ❌ AVOID: Installing build tools in final image
# ❌ AVOID: Copying unnecessary files
# ❌ AVOID: Using full base images (ubuntu, debian)
```

---

## Container Registries

### AWS ECR

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build and tag
docker build -t myworld-api:1.0.0 .
docker tag myworld-api:1.0.0 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0.0

# Push
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0.0

# Lifecycle policy (keep last 10 images)
# In ECR console: Settings → Lifecycle policy
```

### Image Tagging Strategy

```bash
# GOOD: Semantic versioning + Git SHA
myworld-api:1.2.3              # Release version
myworld-api:1.2                # Minor version (latest 1.2.x)
myworld-api:1                  # Major version (latest 1.x.x)
myworld-api:latest             # Most recent build
myworld-api:abc1234            # Git SHA (immutable)

# BAD: Only "latest" tag (no version history)
myworld-api:latest
```

---

## Local Development

### Developer Setup

```bash
# Clone and setup
git clone https://github.com/myworld/api.git
cd api

# Create .env file
cp .env.example .env
# Edit .env with local values

# Start services
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head

# Seed test data
docker compose exec api python -m myworld.scripts.seed

# View logs
docker compose logs -f

# Run tests
docker compose exec api pytest

# Stop everything
docker compose down
```

### Hot Reload (Development)

```yaml
# docker-compose.yml (dev)
services:
  api:
    command: uvicorn myworld.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./src:/app/src  # Mount source for hot reload
```

### Database Migrations (Local)

```bash
# Create a new migration
docker compose exec api alembic revision --autogenerate -m "add user table"

# Apply migrations
docker compose exec api alembic upgrade head

# Rollback one migration
docker compose exec api alembic downgrade -1

# View migration history
docker compose exec api alembic history
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use multi-stage builds | Include build tools in final image |
| Use specific image tags | Use :latest in production |
| Run as non-root user | Run as root |
| Use .dockerignore | Copy node_modules or .git |
| Pin package versions | Use unpinned dependencies |
| Scan images for vulnerabilities | Deploy unscanned images |
| Use managed databases (RDS) | Run databases in containers |
| Mount config via env vars or volumes | Hardcode config in image |
| Use health checks | Skip health checks |
| Use secrets manager | Commit secrets to git |
| Use slim/distroless base images | Use full OS images |
| Clean up package manager cache | Leave cache in final image |
| Use exec form for CMD | Use shell form |
| One process per container | Run multiple services in one container |
| Use immutable infrastructure | Modify running containers |

---

## References

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [12-Factor App](https://12factor.net/)
- [OWASP Docker Security](https://owasp.org/www-project-docker-top-10/)
- [Trivy Security Scanner](https://github.com/aquasecurity/trivy)
- [External Secrets Operator](https://external-secrets.io/)
- [Kustomize](https://kustomize.io/)
