#!/bin/bash
# Automatically fix common issues in PR branches

set -e

# Configuration
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
DRY_RUN="${DRY_RUN:-false}"

# Detect owner and repo from git remote
if [ -z "$GITHUB_OWNER" ] || [ -z "$GITHUB_REPO" ]; then
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$REMOTE_URL" =~ github.com[:/]([^/]+)/([^/]+?)(\.git)?$ ]]; then
        GITHUB_OWNER="${BASH_REMATCH[1]}"
        GITHUB_REPO="${BASH_REMATCH[2]}"
    fi
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is required"
    exit 1
fi

API_BASE="https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}"

# Save current branch
ORIGINAL_BRANCH=$(git branch --show-current)

echo "=== PR Fixer ==="
echo "Repository: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo "Dry Run: ${DRY_RUN}"
echo ""

# Fetch all open PRs
PR_RESPONSE=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${API_BASE}/pulls?state=open&per_page=100")

PR_COUNT=$(echo "$PR_RESPONSE" | jq 'length')

if [ "$PR_COUNT" -eq 0 ]; then
    echo "No open PRs found"
    exit 0
fi

FIXED_COUNT=0
SKIPPED_COUNT=0

# Process each PR
echo "$PR_RESPONSE" | jq -c '.[]' | while read -r pr; do
    PR_NUMBER=$(echo "$pr" | jq -r '.number')
    PR_TITLE=$(echo "$pr" | jq -r '.title')
    PR_BRANCH=$(echo "$pr" | jq -r '.head.ref')
    PR_SHA=$(echo "$pr" | jq -r '.head.sha')
    MERGEABLE_STATE=$(echo "$pr" | jq -r '.mergeable_state')
    
    echo "Processing PR #${PR_NUMBER}: ${PR_TITLE}"
    
    # Skip if merge conflicts
    if [ "$MERGEABLE_STATE" = "dirty" ]; then
        echo "  ⚠ Skipping - has merge conflicts"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    # Checkout PR branch
    echo "  Checking out branch: ${PR_BRANCH}"
    if [ "$DRY_RUN" = "false" ]; then
        git fetch origin "${PR_BRANCH}:${PR_BRANCH}" 2>/dev/null || true
        git checkout "${PR_BRANCH}" 2>/dev/null || {
            echo "  ⚠ Could not checkout branch"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        }
    fi
    
    # Track if we made changes
    MADE_CHANGES=false
    
    # Run linter fixes if available
    if [ -f "package.json" ] && command -v npx &> /dev/null; then
        if grep -q "eslint" package.json 2>/dev/null; then
            echo "  Running ESLint fix..."
            if [ "$DRY_RUN" = "false" ]; then
                if npx eslint --fix . 2>/dev/null; then
                    MADE_CHANGES=true
                    echo "    ✓ ESLint fixes applied"
                fi
            fi
        fi
        
        if grep -q "prettier" package.json 2>/dev/null; then
            echo "  Running Prettier..."
            if [ "$DRY_RUN" = "false" ]; then
                if npx prettier --write "**/*.{js,jsx,ts,tsx,json,css,md}" 2>/dev/null; then
                    MADE_CHANGES=true
                    echo "    ✓ Prettier formatting applied"
                fi
            fi
        fi
    fi
    
    # Run Python linter fixes if available
    if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
        if command -v ruff &> /dev/null; then
            echo "  Running Ruff fix..."
            if [ "$DRY_RUN" = "false" ]; then
                if ruff check --fix . 2>/dev/null; then
                    MADE_CHANGES=true
                    echo "    ✓ Ruff fixes applied"
                fi
            fi
        fi
        
        if command -v black &> /dev/null; then
            echo "  Running Black..."
            if [ "$DRY_RUN" = "false" ]; then
                if black . 2>/dev/null; then
                    MADE_CHANGES=true
                    echo "    ✓ Black formatting applied"
                fi
            fi
        fi
    fi
    
    # Run tests if available
    if [ "$DRY_RUN" = "false" ]; then
        if [ -f "package.json" ] && grep -q "\"test\"" package.json 2>/dev/null; then
            echo "  Running tests..."
            if npm test 2>/dev/null; then
                echo "    ✓ Tests passed"
            else
                echo "    ⚠ Tests failed - changes not committed"
                MADE_CHANGES=false
            fi
        elif [ -f "pytest.ini" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
            echo "  Running pytest..."
            if pytest 2>/dev/null; then
                echo "    ✓ Tests passed"
            else
                echo "    ⚠ Tests failed - changes not committed"
                MADE_CHANGES=false
            fi
        fi
    fi
    
    # Commit and push changes
    if [ "$MADE_CHANGES" = true ] && [ "$DRY_RUN" = "false" ]; then
        CHANGED_FILES=$(git diff --name-only | wc -l)
        if [ "$CHANGED_FILES" -gt 0 ]; then
            echo "  Committing ${CHANGED_FILES} changed file(s)..."
            git add -A
            git commit -m "chore: auto-fix linting and formatting for PR #${PR_NUMBER}"
            
            echo "  Pushing changes..."
            git push origin "${PR_BRANCH}"
            echo "  ✓ Fixes pushed to remote"
            FIXED_COUNT=$((FIXED_COUNT + 1))
        else
            echo "  No changes to commit"
        fi
    fi
    
    # Return to original branch
    git checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
    
    echo ""
done

echo "=== Summary ==="
echo "Fixed: ${FIXED_COUNT}, Skipped: ${SKIPPED_COUNT}"
echo ""
echo "Next steps:"
echo "1. Review the changes pushed to each PR branch"
echo "2. Run 'review-prs.sh' to check updated status"
echo "3. Run 'merge-prs.sh' to merge ready PRs"
