#!/bin/bash
#
# Batch GitHub Issues - Easy Wrapper Script
#
# Simplifies common batch operations with sensible defaults.
#
# Usage:
#   ./scripts/batch.sh create          # Create all issues (parallel)
#   ./scripts/batch.sh preview         # Dry run preview
#   ./scripts/batch.sh prs             # Create PRs automatically
#   ./scripts/batch.sh status          # Check status
#   ./scripts/batch.sh sync            # Sync to projects
#   ./scripts/batch.sh report          # Generate report
#   ./scripts/batch.sh test            # Run tests
#   ./scripts/batch.sh help            # Show help
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
DEFAULT_WORKERS=8
PROJECT_NAME="QA/QC"

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_prerequisites() {
    local missing=0
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.10+"
        missing=1
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        print_error "Git not found. Please install Git."
        missing=1
    fi
    
    # Check GitHub CLI
    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI (gh) not found. Please install from https://cli.github.com/"
        missing=1
    else
        # Check authentication
        if ! gh auth status &> /dev/null; then
            print_warning "GitHub CLI not authenticated"
            echo "Run: gh auth login"
            missing=1
        fi
    fi
    
    # Check PyYAML
    if ! python3 -c "import yaml" &> /dev/null; then
        print_warning "PyYAML not installed"
        echo "Run: pip install pyyaml"
        missing=1
    fi
    
    return $missing
}

cmd_create() {
    print_header "🚀 Creating GitHub Issues (Parallel Mode)"
    
    echo "Priority: $1"
    echo "Workers: $DEFAULT_WORKERS"
    echo
    
    if [ "$1" == "all" ]; then
        python3 "$SCRIPT_DIR/batch_issue_processor.py" process --all --parallel --workers $DEFAULT_WORKERS
    else
        python3 "$SCRIPT_DIR/batch_issue_processor.py" process --priority "$1" --parallel --workers $DEFAULT_WORKERS
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Issues created successfully!"
    else
        print_error "Failed to create some issues"
    fi
}

cmd_preview() {
    print_header "🔮 Preview Mode (Dry Run)"
    
    python3 "$SCRIPT_DIR/batch_issue_processor.py" process --all --dry-run --verbose
    
    if [ $? -eq 0 ]; then
        print_success "Preview complete!"
    else
        print_error "Preview failed"
    fi
}

cmd_prs() {
    print_header "📦 Creating Pull Requests"
    
    python3 "$SCRIPT_DIR/batch_issue_processor.py" create-prs --auto
    
    if [ $? -eq 0 ]; then
        print_success "PRs created successfully!"
    else
        print_error "Failed to create some PRs"
    fi
}

cmd_status() {
    print_header "📊 Status Check"
    
    python3 "$SCRIPT_DIR/batch_issue_processor.py" status
}

cmd_sync() {
    print_header "📋 Syncing to GitHub Projects"
    
    if [ -z "$PROJECT_NAME" ]; then
        print_error "Project name not set. Edit this script to set PROJECT_NAME."
        return 1
    fi
    
    python3 "$SCRIPT_DIR/github_projects_integration.py" sync --project "$PROJECT_NAME"
    
    if [ $? -eq 0 ]; then
        print_success "Sync complete!"
    else
        print_warning "Sync may have encountered issues"
    fi
}

cmd_report() {
    print_header "📄 Generating Report"
    
    local report_file="$REPO_ROOT/batch_report_$(date +%Y%m%d_%H%M%S).md"
    
    python3 "$SCRIPT_DIR/batch_issue_processor.py" report > "$report_file"
    
    if [ $? -eq 0 ]; then
        print_success "Report generated: $report_file"
    else
        print_error "Failed to generate report"
    fi
}

cmd_test() {
    print_header "🧪 Running Tests"
    
    python3 "$SCRIPT_DIR/test_batch_tools.py"
}

cmd_help() {
    cat << EOF
Batch GitHub Issues - Easy Wrapper

Usage: ./scripts/batch.sh <command> [options]

Commands:
  create [priority]    Create issues (all, critical, high, medium, low)
                       Default: all
  preview              Dry run preview (no changes made)
  prs                  Create PRs automatically
  status               Check current status
  sync                 Sync to GitHub Projects board
  report               Generate progress report
  test                 Run test suite
  help                 Show this help message

Examples:
  ./scripts/batch.sh create           # Create all issues
  ./scripts/batch.sh create high      # Create high priority only
  ./scripts/batch.sh preview          # Preview first
  ./scripts/batch.sh prs              # Create PRs
  ./scripts/batch.sh status           # Check status
  ./scripts/batch.sh sync             # Sync to projects
  ./scripts/batch.sh report           # Generate report

Configuration:
  Edit this script to change:
  - DEFAULT_WORKERS: Number of parallel workers (default: 8)
  - PROJECT_NAME: GitHub Projects board name (default: QA/QC)

Requirements:
  - Python 3.10+
  - Git
  - GitHub CLI (gh)
  - PyYAML (pip install pyyaml)

Quick Setup:
  1. gh auth login
  2. pip install pyyaml
  3. ./scripts/batch.sh test

EOF
}

# Main command dispatcher
case "${1:-help}" in
    create)
        check_prerequisites || exit 1
        cmd_create "${2:-all}"
        ;;
    preview)
        check_prerequisites || exit 1
        cmd_preview
        ;;
    prs)
        check_prerequisites || exit 1
        cmd_prs
        ;;
    status)
        cmd_status
        ;;
    sync)
        check_prerequisites || exit 1
        cmd_sync
        ;;
    report)
        cmd_report
        ;;
    test)
        cmd_test
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        cmd_help
        exit 1
        ;;
esac
