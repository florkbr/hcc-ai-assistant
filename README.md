# AI Assistant Service

HTTP-based AI assistant service using LightSpeed stack.

## Quick Start

```bash
# Install dependencies
make install

# Install with development dependencies
make install-dev

# Run the application
make run

# Run in development mode with auto-reload
make dev
```

## Available Commands

- `make install` - Install production dependencies
- `make install-dev` - Install with development dependencies
- `make run` - Run the application
- `make dev` - Run with uvicorn in development mode
- `make test` - Run tests
- `make clean` - Clean build artifacts
- `make lint` - Lint code
- `make format` - Format code
- `make help` - Show all available commands

## Services

- **Main Service**: Port 8000 (LightSpeed stack)
- **Metrics Server**: Port 9000 (Prometheus metrics)