#!/bin/bash
# Review all open PRs and report their status

set -e

# Configuration
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"

# Detect owner and repo from git remote if not set
if [ -z "$GITHUB_OWNER" ] || [ -z "$GITHUB_REPO" ]; then
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$REMOTE_URL" =~ github.com[:/]([^/]+)/([^/]+?)(\.git)?$ ]]; then
        GITHUB_OWNER="${BASH_REMATCH[1]}"
        GITHUB_REPO="${BASH_REMATCH[2]}"
    fi
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is required"
    echo "Create a token at: https://github.com/settings/tokens"
    exit 1
fi

if [ -z "$GITHUB_OWNER" ] || [ -z "$GITHUB_REPO" ]; then
    echo "Error: Could not detect GitHub owner/repo"
    echo "Set GITHUB_OWNER and GITHUB_REPO environment variables"
    exit 1
fi

API_BASE="https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}"

echo "=== PR Review Report ==="
echo "Repository: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo ""

# Fetch all open PRs
PR_RESPONSE=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${API_BASE}/pulls?state=open&per_page=100")

# Check if response is valid
if echo "$PR_RESPONSE" | grep -q "Bad credentials"; then
    echo "Error: Invalid GitHub token"
    exit 1
fi

# Count PRs
PR_COUNT=$(echo "$PR_RESPONSE" | jq 'length')

if [ "$PR_COUNT" -eq 0 ]; then
    echo "No open PRs found"
    exit 0
fi

echo "Total Open PRs: ${PR_COUNT}"
echo ""

# Track status
READY_TO_MERGE=0
HAS_ISSUES=0
HAS_CONFLICTS=0

# Process each PR
echo "$PR_RESPONSE" | jq -c '.[]' | while read -r pr; do
    PR_NUMBER=$(echo "$pr" | jq -r '.number')
    PR_TITLE=$(echo "$pr" | jq -r '.title')
    PR_BRANCH=$(echo "$pr" | jq -r '.head.ref')
    PR_AUTHOR=$(echo "$pr" | jq -r '.user.login')
    MERGEABLE=$(echo "$pr" | jq -r '.mergeable')
    MERGEABLE_STATE=$(echo "$pr" | jq -r '.mergeable_state')
    COMMITS=$(echo "$pr" | jq -r '.commits')
    ADDITIONS=$(echo "$pr" | jq -r '.additions')
    DELETIONS=$(echo "$pr" | jq -r '.deletions')
    CREATED_AT=$(echo "$pr" | jq -r '.created_at')
    
    # Get check status
    CHECKS_RESPONSE=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
        "${API_BASE}/commits/$(echo "$pr" | jq -r '.head.sha')/check-runs")
    
    TOTAL_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '.total_count')
    FAILED_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '[.check_runs[] | select(.conclusion == "failure" or .conclusion == "timed_out" or .conclusion == "action_required")] | length')
    PENDING_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '[.check_runs[] | select(.status == "queued" or .status == "in_progress")] | length')
    SUCCESS_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '[.check_runs[] | select(.conclusion == "success")] | length')
    
    # Determine status
    STATUS_ICON="✓"
    STATUS_TEXT="Ready"
    
    if [ "$MERGEABLE_STATE" = "dirty" ] || [ "$MERGEABLE_STATE" = "blocked" ]; then
        STATUS_ICON="✗"
        STATUS_TEXT="Merge conflicts"
        HAS_CONFLICTS=$((HAS_CONFLICTS + 1))
    elif [ "$FAILED_CHECKS" -gt 0 ]; then
        STATUS_ICON="⚠"
        STATUS_TEXT="${FAILED_CHECKS} check(s) failing"
        HAS_ISSUES=$((HAS_ISSUES + 1))
    elif [ "$PENDING_CHECKS" -gt 0 ]; then
        STATUS_ICON="⏳"
        STATUS_TEXT="${PENDING_CHECKS} check(s) pending"
    else
        READY_TO_MERGE=$((READY_TO_MERGE + 1))
    fi
    
    # Print PR info
    echo "${STATUS_ICON} PR #${PR_NUMBER}: ${PR_TITLE}"
    echo "   Branch: ${PR_BRANCH} (by ${PR_AUTHOR})"
    echo "   Changes: +${ADDITIONS} -${DELETIONS} (${COMMITS} commits)"
    echo "   Checks: ${SUCCESS_CHECKS} passed, ${FAILED_CHECKS} failed, ${PENDING_CHECKS} pending"
    echo "   Status: ${STATUS_TEXT}"
    echo ""
done

echo "=== Summary ==="
echo "Review complete. Use 'fix-prs.sh' to fix issues or 'merge-prs.sh' to merge ready PRs."
