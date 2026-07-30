# THTWAAT Core API (Version 1.0.0)

Welcome to the **THTWAAT Core API** repository. This project is a multi-tenant enterprise AI platform backend for the THTWAAT SaaS ecosystem.

> **v1.0.0 production readiness:** [`docs/release/v1.0.0/`](docs/release/v1.0.0/README.md) · **Changelog:** [`CHANGELOG.md`](CHANGELOG.md) · **VPS bootstrap:** [`docs/ops/VPS_BOOTSTRAP.md`](docs/ops/VPS_BOOTSTRAP.md) · **VPS deploy:** [`docs/ops/DEPLOYMENT.md`](docs/ops/DEPLOYMENT.md)

## 🚀 Technologies

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL (SQLAlchemy 2.0, Alembic)
- **Validation**: Pydantic v2
- **Authentication**: JWT access + refresh (bcrypt password hashing)
- **Security**: Enterprise RBAC permissions, security headers, rate limiting
- **Observability**: Prometheus Instrumentator (`/metrics`)

## 🏗️ Architecture

The project strictly adheres to an Enterprise Layered Architecture:

- `Router Layer`: Handles HTTP requests, dependencies (`Depends`), status codes, and delegates logic.
- `Service Layer`: Contains all business logic. Orchestrates calls between repositories and other modules.
- `Repository Layer`: Handles all database operations (`select`, `update`, `insert`), hiding SQLAlchemy complexity from the business logic.
- `Schema Layer`: Pydantic definitions for Request/Response validation.
- `Model Layer`: SQLAlchemy declarative models.

### Core Modules
1. **Companies / Users / Auth / RBAC** — multi-tenant identity and permissions.
2. **Apps, Products, Storage, Notifications, Payments, AI Gateway**
3. **Agents, Knowledge, Publish, Domains, Marketplace, Product Generator, Branding**
4. **Enterprise, Onboarding, Monitoring/Ops, AI Copilot** — orchestration facades over existing services.

## 💻 Local Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL server running locally or via Docker.
- Redis (required for rate limiting and full TestClient)

### 1. Environment Setup

```bash
# Create a virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate
# Activate it (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env`)
Create a `.env` file in the root directory:
```ini
APP_NAME="THTWAAT Core API"
APP_ENV="development"
JWT_SECRET_KEY="your-super-secret-jwt-key"
JWT_REFRESH_SECRET_KEY="your-super-secret-refresh-key"

# Database
DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/thtwaat_db"

# Redis
REDIS_HOST="localhost"
REDIS_PORT=6379

# Storage
STORAGE_PROVIDER="local"
LOCAL_STORAGE_DIR="data/uploads"

# Production: set explicit origins (never *)
# CORS_ORIGINS=["https://app.example.com"]
```

### 3. Database Migrations
We use Alembic for schema migrations. Make sure your database exists, then run:

```bash
alembic upgrade head
```

Current head (v1.0.0): `a7b8c9d0e1f2`

### 4. Run the Server
```bash
uvicorn main:app --reload
```
The API will be available at `http://localhost:8000`.

## 📖 API Documentation (Swagger/OpenAPI)

In **development**, FastAPI generates interactive documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

In **production** (`APP_ENV=production`), docs and OpenAPI are disabled.

### Testing in Postman
You can directly import the OpenAPI specification into Postman to automatically generate a collection:
1. Open Postman.
2. Click **Import** -> **Link**.
3. Paste `http://localhost:8000/openapi.json` and import.

## 🧪 Verification Script
We have provided an end-to-end integration test script that acts as a client:
```bash
python verify.py
```
This script creates a dummy company, registers an admin user, logs in to obtain a JWT, and exercises the CRUD endpoints across all core modules.

## CI/CD

### GitHub Actions
This repository uses GitHub Actions for continuous integration and delivery. The workflows are defined in `.github/workflows/`. They include tests, docker validation, security scans, and **production VPS deploy** (`deploy-production.yml`).

### Production VPS (one command)
```bash
# Fresh Ubuntu 24.04 host
sudo THTWAAT_SSH_PUBKEY="$(cat ~/.ssh/id_ed25519.pub)" ./bootstrap.sh

# Then configure secrets and deploy
sudo -u thtwaat -H bash
cd /opt/thtwaat/current
nano /opt/thtwaat/shared/.env.prod
ENV_FILE=/opt/thtwaat/shared/.env.prod ./deploy/validate-env.sh
./deploy.sh
```
See [docs/ops/VPS_BOOTSTRAP.md](docs/ops/VPS_BOOTSTRAP.md), [DEPLOYMENT.md](docs/ops/DEPLOYMENT.md), [OPERATIONS_RUNBOOK.md](docs/ops/OPERATIONS_RUNBOOK.md), [RECOVERY_GUIDE.md](docs/ops/RECOVERY_GUIDE.md).

### Running tests
Install test tooling once: `pip install -r requirements-dev.txt`

```bash
./scripts/test-unit.sh            # no Docker
./scripts/test-integration.sh     # Docker Postgres + Redis
./scripts/test-e2e.sh             # deployed API (E2E_BASE_URL)
./scripts/test-all.sh             # unit + integration
```

See [docs/testing/TESTING.md](docs/testing/TESTING.md), [CI.md](docs/testing/CI.md), and [DEVELOPER_WORKFLOW.md](docs/testing/DEVELOPER_WORKFLOW.md).

### Docker Build
To validate the docker compose configuration:
```bash
docker compose config
```

Test stack only:
```bash
docker compose -f docker-compose.test.yml up -d db redis
```
## Monitoring

### Prometheus & Grafana
This project uses a production-grade Prometheus and Grafana monitoring stack.
- **Prometheus**: Scrapes FastAPI metrics, Node Exporter, cAdvisor, and health endpoints. Available at `http://localhost:9090`.
- **Grafana**: Auto-provisioned with Prometheus datasource and default dashboards. Available at `http://localhost:3000`.

To start the monitoring stack:
```bash
docker compose -f docker-compose.monitoring.yml up -d
```

## Performance Testing

This repository includes enterprise-grade load testing infrastructure using Locust and k6.

### Run Tests

**Locust:**
```bash
docker compose -f docker-compose.performance.yml run --rm locust -f /mnt/locust/locustfile.py --host http://api:8000
```

**k6:**
```bash
docker compose -f docker-compose.performance.yml run --rm k6 run /scripts/k6/auth.js
```
