# OpenLocalAI - Self-Hosted AI API Server

A complete self-hosted solution for running open-source language models with an OpenAI-compatible API. Built with Python (FastAPI) and designed to work with Ollama for model inference.

## Features

- **OpenAI-Compatible API**: Use existing SDKs and tools with minimal changes
- **API Key Authentication**: Secure access control with per-key rate limiting
- **User Management**: Web interface for account and API key management
- **Multiple Models**: Support for various open-source models (Llama, Qwen, Phi, Mistral, CodeLlama)
- **Local Inference**: Run models entirely on your own hardware
- **Usage Tracking**: Monitor API usage per key and user

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  (OpenAI CLI, Python SDK, cURL, Web UI)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI REST Server (:8000)                 │
│  - Auth Middleware                                          │
│  - Rate Limiting                                            │
│  - API Key Validation                                       │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ User Service  │   │ Model Service │   │Usage Service  │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                  ┌───────────────────┐
                  │  SQLite Database  │
                  └───────────────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │  Ollama (:11434)  │
                  └───────────────────┘
```

## Quick Start

### 1. Install Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - Download from https://ollama.com/download
```

### 2. Start Ollama and Pull a Model

```bash
# Start Ollama server
ollama serve

# In another terminal, pull a model (1-4GB depending on model)
ollama pull llama3.2:1b
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
python scripts/init_db.py
```

### 5. Run the Server

```bash
# API Server
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# Web Interface (separate terminal)
python web/app.py
```

### 6. Access the Services

- **API Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Web UI**: http://localhost:5000
- **Admin Account**: admin@localhost / admin123

## Configuration

Edit `config.yaml` to customize settings:

```yaml
app:
  name: "OpenLocalAI"
  host: "0.0.0.0"
  port: 8000
  secret_key: "change-this-in-production"

inference:
  provider: "ollama"  # ollama or lmstudio
  ollama:
    base_url: "http://localhost:11434"
    timeout: 300

rate_limiting:
  enabled: true
  default_requests_per_minute: 60
```

## API Usage

### Register and Get API Key

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"password123"}'

# Response includes your access token and user info
```

### Using the API (OpenAI-Compatible)

```python
import openai

openai.api_key = "sk-local-your-api-key"
openai.api_base = "http://localhost:8000/v1"

# Chat completion
response = openai.ChatCompletion.create(
    model="llama3.2:1b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)

# Text completion
response = openai.Completion.create(
    model="llama3.2:1b",
    prompt="Once upon a time"
)
print(response.choices[0].text)
```

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login |
| `/keys` | GET | List API keys |
| `/keys` | POST | Create API key |
| `/v1/models` | GET | List available models |
| `/v1/completions` | POST | Text completion |
| `/v1/chat/completions` | POST | Chat completion |

## Available Models

| Model | Size | RAM Required | Description |
|-------|------|--------------|-------------|
| llama3.2:1b | 1.3GB | 2GB | Meta's latest efficient model |
| qwen2.5:0.5b | 390MB | 1GB | Alibaba's lightweight model |
| phi3:mini | 2GB | 3GB | Microsoft's efficient model |
| mistral-nemo | 7GB | 8GB | Mistral's base model |
| codellama:3.5 | 3.5GB | 4GB | Code-specialized |

Download additional models:
```bash
python scripts/download_models.py download <model-name>
```

## Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Format code (if black is installed)
black src/
```

## Project Structure

```
/www/AI_server/
├── src/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration
│   ├── models/           # Database models & schemas
│   ├── services/         # Business logic
│   ├── routers/          # API routes
│   ├── middleware/       # Auth & rate limiting
│   └── inference/        # Ollama/LM Studio clients
├── web/
│   ├── app.py            # Flask web app
│   └── templates/        # HTML templates
├── scripts/
│   ├── init_db.py        # Database setup
│   └── download_models.py # Model management
├── tests/                # Unit tests
├── config.yaml           # Configuration
└── requirements.txt      # Dependencies
```

## Security Considerations

1. **Change the secret key** in production (`config.yaml`)
2. **Use HTTPS** in production deployments
3. **Set appropriate rate limits** per API key
4. **Monitor usage** via the dashboard
5. **Regular backups** of the SQLite database

## Troubleshooting

### Ollama not responding
```bash
# Check if Ollama is running
curl http://localhost:11434

# Start Ollama
ollama serve
```

### Model not downloaded
```bash
# List available models
python scripts/download_models.py list

# Download a model
python scripts/download_models.py download llama3.2:1b
```

### Database errors
```bash
# Reinitialize database
rm openlocalai.db
python scripts/init_db.py
```

## License

MIT License - See LICENSE file for details.
