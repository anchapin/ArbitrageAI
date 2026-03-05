#!/bin/bash
# =============================================================================
# ArbitrageAI - DevContainer Post-Create Script
# =============================================================================
# This script runs after the devcontainer is created.
# It sets up the development environment with all necessary dependencies.
# =============================================================================

set -e

echo "=========================================="
echo "ArbitrageAI DevContainer Post-Create Setup"
echo "=========================================="

# Navigate to workspace
cd /workspaces/ArbitrageAI

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel

# Install uv for faster package installation
echo "Installing uv..."
pip install uv

# Install project dependencies
echo "Installing project dependencies..."
uv pip install --system -e ".[dev,tests]"

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pip install pre-commit
pre-commit install || true

# Install Playwright browsers
echo "Installing Playwright browsers..."
python -m playwright install --with-deps chromium || true

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
else
    echo ".env already exists, skipping..."
fi

# Run initial lint check (non-blocking)
echo "Running initial lint check..."
ruff check --fix . || echo "Lint check completed with some issues (non-blocking)"

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p data logs .cache

echo "=========================================="
echo "Post-Create Setup Complete!"
echo "=========================================="
echo ""
echo "To start the development server:"
echo "  uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "To run tests:"
echo "  pytest tests/ -v"
echo ""
echo "To install pre-commit hooks:"
echo "  pre-commit install"
echo "=========================================="
