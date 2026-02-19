# AI Assistant Service

HTTP-based AI assistant service using LightSpeed stack with Google Vertex AI.

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values:
# VERTEX_PROJECT=your-project-id
# VERTEX_LOCATION=your-location
# ALLOWED_MODEL=your-model-name
# GOOGLE_API_KEY=your-api-key

# Start services
docker compose up
```

The service will be available at:
- **LightSpeed Stack**: http://localhost:8080

## Configuration

### Required Environment Variables

- `VERTEX_PROJECT` - Google Cloud project ID
- `VERTEX_LOCATION` - Vertex AI location
- `ALLOWED_MODEL` - Model name (e.g., "gemini-2.5-flash")
- `GOOGLE_API_KEY` - Google Cloud API key
