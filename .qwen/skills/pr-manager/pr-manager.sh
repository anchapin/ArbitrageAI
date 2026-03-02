#!/bin/bash
# Main entry point for PR Manager skill
# Reviews, fixes, and merges all open PRs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
ACTION="${1:-review}"

echo "╔══════════════════════════════════════╗"
echo "║       PR Manager Skill               ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is required"
    echo ""
    echo "Usage:"
    echo "  export GITHUB_TOKEN=your_token_here"
    echo "  ./pr-manager.sh [review|fix|merge]"
    echo ""
    echo "Actions:"
    echo "  review - List and review all open PRs (default)"
    echo "  fix    - Auto-fix linting/formatting issues"
    echo "  merge  - Merge all PRs that pass checks"
    echo ""
    echo "Environment variables:"
    echo "  GITHUB_TOKEN  - Required. GitHub personal access token"
    echo "  GITHUB_OWNER  - Optional. Repo owner (auto-detected)"
    echo "  GITHUB_REPO   - Optional. Repo name (auto-detected)"
    echo "  AUTO_MERGE    - Set to 'true' to enable merging (default: false)"
    echo "  RUN_TESTS     - Set to 'true' to run tests before merge (default: true)"
    echo "  DRY_RUN       - Set to 'true' to preview fixes without committing"
    echo "  MERGE_METHOD  - Merge method: squash, merge, or rebase (default: squash)"
    exit 1
fi

case "$ACTION" in
    review)
        echo "Action: Review PRs"
        echo ""
        "${SCRIPT_DIR}/review-prs.sh"
        ;;
    fix)
        echo "Action: Fix PR Issues"
        echo ""
        "${SCRIPT_DIR}/fix-prs.sh"
        ;;
    merge)
        echo "Action: Merge PRs"
        echo ""
        "${SCRIPT_DIR}/merge-prs.sh"
        ;;
    all)
        echo "Action: Full PR Workflow (review → fix → merge)"
        echo ""
        echo "Step 1: Reviewing PRs..."
        echo "─────────────────────────────────────"
        "${SCRIPT_DIR}/review-prs.sh"
        echo ""
        
        echo "Step 2: Fixing issues..."
        echo "─────────────────────────────────────"
        "${SCRIPT_DIR}/fix-prs.sh"
        echo ""
        
        echo "Step 3: Merging ready PRs..."
        echo "─────────────────────────────────────"
        export AUTO_MERGE="${AUTO_MERGE:-true}"
        "${SCRIPT_DIR}/merge-prs.sh"
        ;;
    *)
        echo "Unknown action: ${ACTION}"
        echo "Valid actions: review, fix, merge, all"
        exit 1
        ;;
esac
