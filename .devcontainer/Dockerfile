# =============================================================================
# ArbitrageAI - DevContainer Dockerfile
# =============================================================================
# This Dockerfile is used by the devcontainer to create a reproducible
# development environment.
#
# Usage: This file is referenced by .devcontainer/devcontainer.json
# =============================================================================

# Use Python 3.10 as base (matching project requirements)
FROM mcr.microsoft.com/devcontainers/python:3.10-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=development

# Set default shell
SHELL ["/bin/bash", "-c"]

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    build-essential \
    curl \
    git \
    # Database clients
    libpq-dev \
    # SSL libraries
    libffi-dev \
    libssl-dev \
    # Node.js for client portal (required by some dev workflows)
    nodejs \
    npm \
    # Process tools
    htop \
    vim \
    # Git extras
    git-lfs \
    # Docker CLI (for docker-compose workflows)
    docker.io \
    docker-compose \
    # Utilities
    ca-certificates \
    unzip \
    zip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for development
RUN groupadd --gid 1000 developers \
    && useradd --uid 1000 --gid developers --shell /bin/bash --create-home developer

# Switch to developer user
USER developer

# Set working directory
WORKDIR /workspaces/ArbitrageAI

# Create virtual environment
RUN python -m venv /home/developer/.venv

# Activate virtual environment in shell initialization
RUN echo "source /home/developer/.venv/bin/activate" >> /home/developer/.bashrc

# Set PATH to use virtual environment
ENV PATH="/home/developer/.venv/bin:$PATH"

# Install Python dependencies from pyproject.toml
# Copy dependency files first for better caching
COPY --chown=developer:developers pyproject.toml uv.lock ./

# Install dependencies using pip with uv for faster installs
RUN pip install --upgrade pip setuptools wheel \
    && pip install uv \
    && uv pip install --system -e ".[dev,tests]"

# Install Playwright for browser automation (used in tests)
RUN python -m playwright install --with-deps chromium

# Create necessary directories
RUN mkdir -p /home/developer/workspaces/ArbitrageAI/data \
    /home/developer/workspaces/ArbitrageAI/logs \
    /home/developer/workspaces/ArbitrageAI/.cache \
    && chmod -R 755 /home/developer/workspaces

# Copy project files
COPY --chown=developer:developers . /workspaces/ArbitrageAI/

# Set ownership of workspace
RUN sudo chown -R developer:developers /workspaces/ArbitrageAI

# Set default environment variables for development
ENV DATABASE_URL="sqlite:///data/tasks.db" \
    REDIS_URL="redis://localhost:6379/0" \
    OLLAMA_URL="http://localhost:11434/v1" \
    USE_LOCAL_BY_DEFAULT="false"

# Expose ports for development services
EXPOSE 8000 5173 11434 6379 3000 16686 9090

# Health check for the development container
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command - start development server with auto-reload
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
