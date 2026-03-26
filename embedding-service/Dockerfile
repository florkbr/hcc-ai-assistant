FROM python:3.14-slim

WORKDIR /app

# Install dependencies from pyproject.toml
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Download the embedding model on build (caching)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"

# Copy application code
COPY main.py .

# Create data directory for ChromaDB persistence
RUN mkdir -p /app/data

# Default host and port (can be overridden via env vars)
# HOST: 0.0.0.0 for IPv4, :: for IPv6/dual-stack
ENV HOST=0.0.0.0
ENV PORT=8001

EXPOSE ${PORT}

# Run with uvicorn (host and port from environment variables)
CMD sh -c "uvicorn main:app --host ${HOST} --port ${PORT}"
