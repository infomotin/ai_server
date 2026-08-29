# Self-Hosted AI API Server Specification

## Project Overview

**Project Name:** OpenLocalAI
**Project Type:** Self-hosted AI inference server with OpenAI-compatible API
**Core Functionality:** A complete self-hosted solution for running open-source language models with API key authentication, user management, and a web interface - serving as a drop-in replacement for commercial AI providers.
**Target Users:** Developers and organizations wanting to self-host AI capabilities without depending on external services.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ OpenAI CLI  │  │ Python SDK  │  │ cURL/HTTP   │  │ Web UI (Browser)    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway Layer                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    FastAPI REST Server (:8000)                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │ │
│  │  │ Auth Middleware│  │ Rate Limiter │  │ Request Logger│ │ API Router  │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
        ┌───────────────────┐ ┌──────────────┐ ┌──────────────┐
        │   User Service    │ │ Model Service │ │Usage Service │
        │  (Auth, Keys)     │ │ (Download,RUN)│ │ (Tracking)   │
        └───────────────────┘ └──────────────┘ └──────────────┘
                    │               │               │
                    ▼               ▼               ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                    SQLite Database                          │
        │  Tables: users, api_keys, usage_logs, models                │
        └─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Inference Layer                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │      OLLAMA         │  │     LM Studio       │  │   HuggingFace       │ │
│  │   (Primary)         │  │   (Secondary)       │  │   (Model Source)    │ │
│  │   :11434            │  │     :1234           │  │                     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## System Flow Diagrams

### 1. User Registration & API Key Generation Flow

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ Client │────▶│ Web UI │────▶│ FastAPI│────▶│  DB    │────▶│ Response│
└────────┘     └────────┘     └────────┘     └────────┘     └────────┘
                                │               │
                                │ Create User   │
                                │──────────────▶│
                                │               │
                                │ Hash Password │
                                │──────────────▶│
                                │               │
                                │ Generate Key  │
                                │──────────────▶│
```

### 2. API Request Flow

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ Client │────▶│ FastAPI│────▶│ Auth   │────▶│Router  │────▶│Inference│
└────────┘     │ Server │     │Middleware│   │        │     │ Engine  │
               └────────┘     └────────┘     └────────┘     └────────┘
                                │                               │
                                │ Validate API Key              │
                                │──────────────▶│              │
                                │               │              │
                                │ Check Rate Limit             │
                                │──────────────▶│              │
                                │               │              │
                                │ Log Usage     │              │
                                │──────────────▶│◀──────────────┘
                                │               │  Return Response
                                ▼               ▼
                          ┌────────┐     ┌────────┐
                          │Response│     │  DB    │
                          └────────┘     └────────┘
```

---

## Directory Structure

```
/www/AI_server/
├── SPEC.md
├── README.md
├── requirements.txt
├── config.yaml
├── docker-compose.yml
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration loader
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── engine.py           # Database engine setup
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication service
│   │   ├── user_service.py     # User management
│   │   ├── api_key_service.py  # API key management
│   │   ├── model_service.py    # Model downloading/management
│   │   ├── inference_service.py # Inference orchestration
│   │   └── usage_service.py    # Usage tracking
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_router.py      # /auth endpoints
│   │   ├── users_router.py     # /users endpoints
│   │   ├── keys_router.py      # /keys endpoints
│   │   ├── completions_router.py # /completions, /chat/completions
│   │   └── models_router.py    # /models endpoints
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth_middleware.py  # API key validation
│   │   └── rate_limiter.py     # Rate limiting
│   │
│   └── inference/
│       ├── __init__.py
│       ├── ollama_client.py    # Ollama API client
│       ├── lmstudio_client.py  # LM Studio client
│       └── base_client.py      # Abstract inference client
│
├── web/
│   ├── __init__.py
│   ├── app.py                  # Flask web application
│   ├── templates/              # HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   └── api_keys.html
│   └── static/
│       ├── css/
│       └── js/
│
├── scripts/
│   ├── init_db.py              # Database initialization
│   ├── download_models.py      # Model download script
│   └── setup_ollama.py         # Ollama setup helper
│
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_api_keys.py
    ├── test_completions.py
    └── test_models.py
```

---

## Functionality Specification

### 1. User Management

#### Features
- **Registration**: Username, email, password with bcrypt hashing
- **Login**: Email/password authentication returning session token
- **Password Reset**: Email-based reset flow (future enhancement)
- **User Profile**: View/edit user information

#### User Model
```python
class User:
    id: UUID (primary key)
    username: str (unique, 3-50 chars)
    email: str (unique, valid email format)
    password_hash: str (bcrypt)
    is_active: bool (default True)
    is_admin: bool (default False)
    created_at: datetime
    updated_at: datetime
    last_login: datetime (nullable)
```

### 2. API Key Management

#### Features
- **Key Generation**: Cryptographically secure random keys (32 bytes, hex encoded = 64 chars)
- **Key Naming**: User-provided descriptive names for keys
- **Key Scoping**: Optional model restrictions per key
- **Key Revocation**: Immediate invalidation on user request
- **Key Listing**: View all keys with creation date and last used
- **Usage Tracking**: Per-key request count and token usage

#### API Key Model
```python
class APIKey:
    id: UUID (primary key)
    key_hash: str (SHA-256 hash of actual key)
    key_prefix: str (first 8 chars for identification)
    user_id: UUID (foreign key)
    name: str (user-provided label)
    scopes: List[str] (e.g., ["completions", "models/read"])
    rate_limit: int (requests per minute, default 60)
    is_active: bool (default True)
    created_at: datetime
    last_used_at: datetime (nullable)
    expires_at: datetime (nullable)
```

### 3. Model Management

#### Supported Models (≤2GB RAM footprint)
| Model | Size | RAM Required | Description |
|-------|------|--------------|-------------|
| llama3.2:1b | 1.3GB | 2GB | Meta's latest efficient model |
| qwen2.5:0.5b | 390MB | 1GB | Alibaba's lightweight model |
| phi3:mini | 2GB | 3GB* | Microsoft's efficient model |
| mistral-nemo | 7GB | 8GB | Mistral's base model |
| codellama:3.5 | 3.5GB | 4GB | Code-specialized |

*Note: Some models exceed 2GB but are included for flexibility

#### Features
- **Auto-Download**: Automatic model fetching from Ollama library
- **Model Listing**: Available models from local Ollama instance
- **Model Info**: Metadata about each model (size, parameters, quantization)
- **Model Switching**: Runtime model selection per request

#### Model Catalog
```python
class Model:
    id: str (e.g., "llama3.2:1b")
    name: str
    provider: str (e.g., "ollama", "lmstudio")
    size_bytes: int
    parameter_count: int
    quantization: str (e.g., "Q4_0")
    is_downloaded: bool
    last_used: datetime
```

### 4. Inference API (OpenAI-Compatible)

#### Core Endpoints

**POST /v1/completions**
```json
// Request
{
    "model": "llama3.2:1b",
    "prompt": "Once upon a time",
    "max_tokens": 100,
    "temperature": 0.7,
    "top_p": 0.9,
    "n": 1,
    "stream": false,
    "stop": ["\n", "###"],
    "echo": false
}

// Response
{
    "id": "cmpl-abc123",
    "object": "text_completion",
    "created": 1699999999,
    "model": "llama3.2:1b",
    "choices": [
        {
            "text": " in a distant galaxy...",
            "index": 0,
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 5,
        "completion_tokens": 20,
        "total_tokens": 25
    }
}
```

**POST /v1/chat/completions**
```json
// Request
{
    "model": "llama3.2:1b",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
}

// Response
{
    "id": "chatcmpl-xyz789",
    "object": "chat.completion",
    "created": 1699999999,
    "model": "llama3.2:1b",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you today?"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 15,
        "total_tokens": 40
    }
}
```

**GET /v1/models** - List available models
**GET /v1/models/{model_id}** - Get model metadata
**POST /v1/embeddings** - Generate embeddings (future)

### 5. Web Interface

#### Pages
1. **Home** (`/`) - Landing page with feature overview
2. **Login** (`/login`) - User authentication
3. **Register** (`/register`) - New user signup
4. **Dashboard** (`/dashboard`) - User dashboard with usage stats
5. **API Keys** (`/keys`) - Key management interface
6. **Models** (`/models`) - Available models browser

#### Frontend Stack
- Flask/Jinja2 templates (server-rendered)
- Tailwind CSS via CDN
- Vanilla JavaScript for interactivity

---

## API Endpoint Specifications

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | /auth/register | Register new user | No |
| POST | /auth/login | Login, returns session | No |
| POST | /auth/logout | Invalidate session | Yes |
| GET | /auth/me | Get current user | Yes |

### User Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /users/me | Current user profile | Yes |
| PUT | /users/me | Update profile | Yes |
| DELETE | /users/me | Delete account | Yes |

### API Key Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /keys | List user's API keys | Yes |
| POST | /keys | Create new API key | Yes |
| GET | /keys/{key_id} | Get key details | Yes |
| DELETE | /keys/{key_id} | Revoke key | Yes |
| GET | /keys/{key_id}/usage | Get key usage stats | Yes |

### Model Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | /v1/models | List available models | API Key |
| GET | /v1/models/{model_id} | Get model info | API Key |
| POST | /v1/models/{model_id}/download | Start model download | API Key |

### Inference Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | /v1/completions | Text completion | API Key |
| POST | /v1/chat/completions | Chat completion | API Key |
| POST | /v1/embeddings | Generate embeddings | API Key |

---

## Database Schema

### SQLite Schema

```sql
-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- API Keys table
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    key_prefix TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    scopes TEXT DEFAULT '["completions", "chat/completions"]',
    rate_limit INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Usage logs table
CREATE TABLE usage_logs (
    id TEXT PRIMARY KEY,
    api_key_id TEXT NOT NULL REFERENCES api_keys(id),
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Models catalog table
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    size_bytes INTEGER,
    parameter_count INTEGER,
    quantization TEXT,
    is_downloaded BOOLEAN DEFAULT 0,
    last_used TIMESTAMP
);

-- Indexes
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_usage_logs_key ON usage_logs(api_key_id);
CREATE INDEX idx_usage_logs_created ON usage_logs(created_at);
```

---

## Authentication & Security

### API Key Authentication

```
Authorization: Bearer sk-local-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Validation Flow:**
1. Extract key from Authorization header
2. Hash incoming key with SHA-256
3. Lookup key_hash in database
4. Verify key is active and not expired
5. Check rate limits
6. Update last_used_at timestamp
7. Attach user context to request

### Rate Limiting

- Default: 60 requests/minute per API key
- Configurable per key
- Redis-free implementation using token bucket algorithm
- Returns `429 Too Many Requests` when exceeded

### Security Measures

1. **Password Hashing**: bcrypt with cost factor 12
2. **API Key Storage**: SHA-256 hashed (keys never stored in plaintext)
3. **HTTPS Required**: All production deployments
4. **Input Validation**: Pydantic models for all inputs
5. **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
6. **CORS Configuration**: Configurable allowed origins

---

## Configuration

### config.yaml

```yaml
app:
  name: "OpenLocalAI"
  host: "0.0.0.0"
  port: 8000
  debug: false
  secret_key: "change-this-in-production"
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:8000"

database:
  url: "sqlite:///./openlocalai.db"
  echo: false

inference:
  provider: "ollama"  # ollama, lmstudio, or huggingface
  ollama:
    base_url: "http://localhost:11434"
    timeout: 300
  lmstudio:
    base_url: "http://localhost:1234"
    timeout: 300

rate_limiting:
  enabled: true
  default_requests_per_minute: 60
  burst_size: 10

models:
  default: "llama3.2:1b"
  cache_dir: "./models"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## Inference Layer Design

### Base Client Interface

```python
class BaseInferenceClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str, model: str, **kwargs) -> CompletionResponse:
        pass

    @abstractmethod
    async def chat_complete(self, messages: List[ChatMessage], model: str, **kwargs) -> ChatCompletionResponse:
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        pass

    @abstractmethod
    async def get_model_info(self, model_id: str) -> ModelInfo:
        pass
```

### Ollama Integration

- Uses Ollama's REST API (`http://localhost:11434`)
- Endpoints used:
  - `POST /api/generate` - Text completion
  - `POST /api/chat` - Chat completion
  - `GET /api/tags` - List models
  - `POST /api/pull` - Download model

### LM Studio Integration

- Uses LM Studio's OpenAI-compatible API (`http://localhost:1234`)
- Direct passthrough to existing OpenAI-compatible endpoints

---

## Deployment Considerations

### Single Machine Deployment

1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull desired model: `ollama pull llama3.2:1b`
3. Install Python dependencies: `pip install -r requirements.txt`
4. Initialize database: `python scripts/init_db.py`
5. Run server: `python src/main.py`

### Docker Deployment

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./models:/root/.ollama
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"

volumes:
  ollama_data:
```

### Scaling Considerations

1. **Horizontal Scaling**: Multiple API servers behind load balancer
2. **Redis for Rate Limiting**: Replace in-memory limiter with Redis
3. **PostgreSQL for Multi-instance**: SQLite doesn't support multi-instance
4. **Model Sharding**: Different instances serve different models
5. **Caching**: Response caching for repeated prompts

---

## Error Handling

### Standard Error Response

```json
{
    "error": {
        "message": "Invalid API key",
        "type": "authentication_error",
        "code": 401,
        "param": null
    }
}
```

### Error Codes

| HTTP Code | Error Type | Description |
|-----------|------------|-------------|
| 400 | invalid_request_error | Malformed request |
| 401 | authentication_error | Invalid or missing API key |
| 403 | permission_error | Insufficient permissions |
| 404 | not_found_error | Resource not found |
| 429 | rate_limit_error | Rate limit exceeded |
| 500 | server_error | Internal server error |
| 503 | service_unavailable | Model not loaded or unavailable |

---

## Implementation Priorities

### Phase 1: Core Infrastructure
1. Database models and setup
2. User registration/login
3. API key generation and validation
4. Basic FastAPI structure

### Phase 2: Inference
1. Ollama client integration
2. Completion endpoints
3. Chat completion endpoints
4. Model listing

### Phase 3: Polish
1. Web interface
2. Usage tracking
3. Rate limiting
4. Documentation

---

## Dependencies

```
# Core
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
python-multipart>=0.0.6

# Database
sqlalchemy>=2.0.0
aiosqlite>=0.19.0

# Authentication
bcrypt>=4.1.0
pyjwt>=2.8.0

# Web Framework
flask>=3.0.0
jinja2>=3.1.0

# HTTP Client
httpx>=0.25.0
aiohttp>=3.9.0

# Utilities
python-dotenv>=1.0.0
pyyaml>=6.0.0
```

---

## Testing Strategy

### Unit Tests
- Authentication service tests
- API key validation tests
- Model service tests
- Request/response validation tests

### Integration Tests
- End-to-end API request tests
- Database operation tests
- Ollama integration tests

### Test Commands
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v
```
