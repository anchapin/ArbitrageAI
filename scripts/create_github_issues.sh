#!/bin/bash
# Script to create GitHub issues from markdown files

set -e

ISSUES_DIR=".github/ISSUES"
LABELS="qaqc-review"

echo "🚀 Creating GitHub issues from markdown files..."
echo "================================================"
echo ""

# Function to create an issue from a file
create_issue() {
    local file=$1
    local priority=$2
    
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi
    
    # Extract title from first heading
    local title=$(grep '^#' "$file" | head -1 | sed 's/^# //' | cut -c1-80)
    
    echo "📝 Creating issue: $title"
    
    # Create the issue
    local issue_url=$(gh issue create \
        --title "$title" \
        --body-file "$file" \
        --label "$LABELS" \
        --label "$priority")
    
    echo "✅ Created: $issue_url"
    echo ""
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

# Check if gh is authenticated
if ! gh auth status > /dev/null 2>&1; then
    echo "❌ GitHub CLI not authenticated. Please run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI authenticated"
echo "📁 Issues directory: $ISSUES_DIR"
echo ""

# Create Critical Security Issues (Week 1-2)
echo "🔴 Creating CRITICAL Security Issues..."
echo "─────────────────────────────────────────"
create_issue "$ISSUES_DIR/QAQC-001-security-eval-replacement.md" "critical"
create_issue "$ISSUES_DIR/QAQC-002-security-insecure-defaults.md" "critical"
create_issue "$ISSUES_DIR/QAQC-003-security-production-validation.md" "critical"

# Create High Priority Issues (Week 3-6)
echo "🟡 Creating HIGH Priority Issues..."
echo "─────────────────────────────────────────"
create_issue "$ISSUES_DIR/QAQC-004-code-quality-undefined-names.md" "high"
create_issue "$ISSUES_DIR/QAQC-005-code-quality-monolithic-files.md" "high"
create_issue "$ISSUES_DIR/QAQC-006-code-quality-exception-handling.md" "high"
create_issue "$ISSUES_DIR/QAQC-007-code-quality-all-ruff-violations.md" "high"
create_issue "$ISSUES_DIR/QAQC-008-architecture-database-migrations.md" "high"

# Create Medium Priority Issues (Week 7-10)
echo "🟢 Creating MEDIUM Priority Issues..."
echo "─────────────────────────────────────────"
create_issue "$ISSUES_DIR/QAQC-009-performance-redis-rate-limiting.md" "medium"
create_issue "$ISSUES_DIR/QAQC-010-performance-database-indexes.md" "medium"
create_issue "$ISSUES_DIR/QAQC-011-performance-n-plus-one-queries.md" "medium"

echo ""
echo "================================================"
echo "✅ All issues created successfully!"
echo ""

# List all created issues
echo "📋 Created Issues:"
echo "─────────────────────────────────────────"
gh issue list --label "qaqc-review" --limit 20 --json number,title,url --template \
'{{range .}}#{{.number}} - {{.title}}
{{.url}}

{{end}}'

echo ""
echo "💡 Next steps:"
echo "1. Review issues at: $(gh repo view --web 2>&1 | grep -o 'https://[^"]*' | head -1)/issues"
echo "2. Add issues to project board"
echo "3. Assign team members"
echo "4. Start with Phase 1 (Critical Security)"
