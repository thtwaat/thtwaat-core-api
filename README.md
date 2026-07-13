# THTWAAT Core API (Version 1.0)

Welcome to the **THTWAAT Core API** repository. This project is a robust, multi-tenant enterprise backend built with modern Python technologies, intended to serve as the foundation for the THTWAAT SaaS ecosystem.

## 🚀 Technologies

- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL (SQLAlchemy 2.0, Alembic)
- **Validation**: Pydantic v2
- **Authentication**: JWT (JSON Web Tokens) with Argon2 hashing
- **Security**: Granular Role-Based Access Control (RBAC)

## 🏗️ Architecture

The project strictly adheres to an Enterprise Layered Architecture:

- `Router Layer`: Handles HTTP requests, dependencies (`Depends`), status codes, and delegates logic.
- `Service Layer`: Contains all business logic. Orchestrates calls between repositories and other modules.
- `Repository Layer`: Handles all database operations (`select`, `update`, `insert`), hiding SQLAlchemy complexity from the business logic.
- `Schema Layer`: Pydantic definitions for Request/Response validation.
- `Model Layer`: SQLAlchemy declarative models.

### Core Modules
1. **Companies**: Multi-tenant isolation.
2. **Users**: User management within companies.
3. **Auth**: JWT Login, registration.
4. **RBAC**: Static role-based policies (`admin`, `manager`, `user`).
5. **Apps**: Resource management demonstrating RBAC integration.
6. **Storage**: Asynchronous file uploads (Local stub, extensible to S3/MinIO).
7. **Notifications**: Pluggable provider strategy (Email, SMS, WhatsApp, Push).
8. **Payments**: Pluggable provider strategy (Stripe, Razorpay, PayPal, Manual).
9. **AI Gateway**: Unified enterprise gateway for AI models (OpenAI, Gemini, Anthropic, Ollama, OpenRouter).
10. **Products**: Central registry for all generated products (Websites, Apps, Agents, etc) with feature flags.

## 💻 Local Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL server running locally or via Docker.

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
SECRET_KEY="your-super-secret-jwt-key"

# Database
DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/thtwaat_db"

# Storage
STORAGE_PROVIDER="local"
LOCAL_STORAGE_DIR="data/uploads"

# Notifications & Payments (Currently Stubs)
EMAIL_PROVIDER="stub"
SMS_PROVIDER="stub"
```

### 3. Database Migrations
We use Alembic for schema migrations. Make sure your database exists, then run:

```bash
alembic upgrade head
```

### 4. Run the Server
```bash
uvicorn main:app --reload
```
The API will be available at `http://localhost:8000`.

## 📖 API Documentation (Swagger/OpenAPI)

Once the server is running, FastAPI automatically generates interactive documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

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
