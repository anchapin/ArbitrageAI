#!/bin/bash
#
# Batch GitHub Issues - Quick Launch Script
#
# This script provides easy access to batch issue creation commands.
#
# Usage:
#   ./scripts/batch-issues.sh              # Show menu
#   ./scripts/batch-issues.sh dry-run      # Preview issues
#   ./scripts/batch-issues.sh create       # Create all issues
#   ./scripts/batch-issues.sh status       # Check status
#   ./scripts/batch-issues.sh phase1       # Create critical issues
#   ./scripts/batch-issues.sh phase2       # Create high priority issues
#   ./scripts/batch-issues.sh phase3       # Create medium priority issues
#   ./scripts/batch-issues.sh progress     # Show progress
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

# Python command (use python3 on Linux)
PYTHON_CMD="python3"
if command -v python &> /dev/null && [[ "$(uname)" == "Darwin" ]]; then
    PYTHON_CMD="python"
fi

# Check prerequisites
check_prereqs() {
    if ! command -v gh &> /dev/null; then
        echo -e "${RED}❌ GitHub CLI not found. Install: brew install gh${NC}"
        exit 1
    fi

    if ! gh auth status &> /dev/null; then
        echo -e "${RED}❌ GitHub CLI not authenticated. Run: gh auth login${NC}"
        exit 1
    fi

    if ! $PYTHON_CMD -c "import yaml" &> /dev/null; then
        echo -e "${RED}❌ PyYAML not installed. Run: pip install pyyaml${NC}"
        exit 1
    fi
}

# Show menu
show_menu() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}     ${GREEN}Batch GitHub Issues - Quick Launch${NC}              ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Available Commands:${NC}"
    echo "  ${GREEN}dry-run${NC}     - Preview issues without creating"
    echo "  ${GREEN}create${NC}      - Create all 11 issues"
    echo "  ${GREEN}status${NC}      - Show current issues and PRs"
    echo "  ${GREEN}phase1${NC}      - Create critical security issues (3)"
    echo "  ${GREEN}phase2${NC}      - Create high priority issues (5)"
    echo "  ${GREEN}phase3${NC}      - Create medium priority issues (3)"
    echo "  ${GREEN}progress${NC}    - Show progress dashboard"
    echo "  ${GREEN}report${NC}      - Generate detailed report"
    echo "  ${GREEN}test${NC}        - Run test suite"
    echo "  ${GREEN}help${NC}        - Show this help message"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./scripts/batch-issues.sh dry-run"
    echo "  ./scripts/batch-issues.sh create"
    echo "  ./scripts/batch-issues.sh phase1"
    echo ""
}

# Main command handler
case "${1:-}" in
    dry-run)
        check_prereqs
        echo -e "${BLUE}🔮 Running dry run...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_github_issues.py" dry-run
        ;;

    create)
        check_prereqs
        echo -e "${GREEN}🚀 Creating all issues...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_github_issues.py" create-issues
        ;;

    status)
        check_prereqs
        echo -e "${BLUE}📊 Checking status...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_github_issues.py" status
        ;;

    phase1|critical)
        check_prereqs
        echo -e "${RED}🔴 Executing Phase 1: Critical Security...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_orchestrator.py" phase critical
        ;;

    phase2|high)
        check_prereqs
        echo -e "${YELLOW}🟡 Executing Phase 2: High Priority...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_orchestrator.py" phase high
        ;;

    phase3|medium)
        check_prereqs
        echo -e "${GREEN}🟢 Executing Phase 3: Medium Priority...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_orchestrator.py" phase medium
        ;;

    progress)
        check_prereqs
        echo -e "${BLUE}📈 Showing progress...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_orchestrator.py" progress
        ;;

    report)
        check_prereqs
        echo -e "${BLUE}📝 Generating report...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/batch_orchestrator.py" report
        ;;

    test)
        echo -e "${BLUE}🧪 Running test suite...${NC}"
        $PYTHON_CMD "$SCRIPT_DIR/test_batch_tools.py"
        ;;

    help|--help|-h|"")
        show_menu
        ;;

    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_menu
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Done!${NC}"
