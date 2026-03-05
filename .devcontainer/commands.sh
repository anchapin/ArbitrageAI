#!/bin/bash
# =============================================================================
# ArbitrageAI - DevContainer Command Reference
# =============================================================================
# This script provides common development commands for the devcontainer.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a devcontainer
if [ ! -f /.dockerenv ] && [ ! -d /.devcontainer ]; then
    print_warning "This script is designed to run in a devcontainer"
fi

# Parse command
COMMAND=${1:-help}

case "$COMMAND" in
    install)
        print_status "Installing dependencies..."
        pip install --upgrade pip setuptools wheel
        pip install uv
        uv pip install --system -e ".[dev,tests]"
        python -m playwright install --with-deps chromium
        pre-commit install || true
        print_status "Dependencies installed!"
        ;;

    start)
        print_status "Starting FastAPI development server..."
        uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
        ;;

    test)
        shift
        print_status "Running tests..."
        pytest tests/ -v "$@"
        ;;

    lint)
        print_status "Running linter..."
        ruff check .
        ;;

    format)
        print_status "Formatting code..."
        ruff format .
        ;;

    typecheck)
        print_status "Running type checker..."
        mypy src/ || true
        ;;

    clean)
        print_status "Cleaning up cache files..."
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
        print_status "Cleanup complete!"
        ;;

    setup)
        print_status "Running full setup..."
        bash .devcontainer/post-create.sh
        ;;

    help|*)
        echo "ArbitrageAI DevContainer Commands"
        echo ""
        echo "Usage: ./devcontainer/commands.sh <command>"
        echo ""
        echo "Commands:"
        echo "  install    - Install all dependencies"
        echo "  start      - Start FastAPI development server"
        echo "  test       - Run tests"
        echo "  lint       - Run linter"
        echo "  format     - Format code"
        echo "  typecheck  - Run type checker"
        echo "  clean      - Clean up cache files"
        echo "  setup      - Run full setup"
        echo "  help       - Show this help message"
        ;;
esac
