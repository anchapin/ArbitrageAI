# DevContainer Configuration

This directory contains the DevContainer configuration for ArbitrageAI, enabling reproducible development environments.

## What's Included

- **devcontainer.json** - Main DevContainer configuration file
- **Dockerfile** - Custom Dockerfile for the development environment
- **post-create.sh** - Script that runs after container creation
- **commands.sh** - Common development commands reference
- **README.md** - This file

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) or [Rancher Desktop](https://rancherdesktop.io/)
- [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Opening the Project in DevContainer

1. Open the ArbitrageAI project in VS Code
2. Install the Dev Containers extension if prompted
3. Click "Reopen in Container" when prompted (bottom-right corner)
   - Or: Press `F1`, type "Dev Containers: Reopen in Container"
4. Wait for the container to build (first time takes a few minutes)
5. The development environment is ready!

### Without VS Code

You can also use the DevContainer with other editors that support it:

```bash
# Using Docker directly
docker build -t arbitrageai-dev -f .devcontainer/Dockerfile .
docker run -it -p 8000:8000 -v $(pwd):/workspaces/ArbitrageAI arbitrageai-dev
```

## Features

### Python Environment
- Python 3.10 (matching project requirements)
- Virtual environment with all dev dependencies
- Pre-configured ruff, mypy, pytest

### VS Code Extensions
- Python (Microsoft)
- Ruff (charliermarsh)
- Pytest (Microsoft)
- GitLens (eamodio)
- And more (see devcontainer.json)

### Pre-configured Ports
| Port | Service |
|------|---------|
| 8000 | FastAPI Backend |
| 5173 | Vite Frontend |
| 11434 | Ollama LLM |
| 6379 | Redis |
| 3000 | Grafana |
| 16686 | Jaeger UI |
| 9090 | Prometheus |

## Commands

Inside the devcontainer, you can use:

```bash
# Install dependencies
.devcontainer/commands.sh install

# Start development server
.devcontainer/commands.sh start

# Run tests
.devcontainer/commands.sh test

# Run linter
.devcontainer/commands.sh lint

# Format code
.devcontainer/commands.sh format

# Type check
.devcontainer/commands.sh typecheck

# Clean cache
.devcontainer/commands.sh clean
```

## Environment Variables

The devcontainer sets these default environment variables:

```
PYTHONUNBUFFERED=1
ENVIRONMENT=development
DATABASE_URL=sqlite:///data/tasks.db
REDIS_URL=redis://localhost:6379/0
OLLAMA_URL=http://localhost:11434/v1
USE_LOCAL_BY_DEFAULT=false
```

## Troubleshooting

### Container fails to build

1. Ensure Docker is running
2. Try rebuilding: `Dev Containers: Rebuild Container`

### Port already in use

Stop the conflicting service or modify the port in `devcontainer.json`

### Dependencies not installed

Run the post-create script manually:
```bash
bash .devcontainer/post-create.sh
```

## Additional Resources

- [Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Dev Containers CLI](https://github.com/devcontainers/cli)
