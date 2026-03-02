#!/bin/bash
# Merge all PRs that pass checks

set -e

# Configuration
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
AUTO_MERGE="${AUTO_MERGE:-false}"
RUN_TESTS="${RUN_TESTS:-true}"
MERGE_METHOD="${MERGE_METHOD:-squash}"

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

echo "=== PR Merger ==="
echo "Repository: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo "Auto Merge: ${AUTO_MERGE}"
echo "Merge Method: ${MERGE_METHOD}"
echo ""

if [ "$AUTO_MERGE" != "true" ]; then
    echo "⚠ AUTO_MERGE is not enabled. Set AUTO_MERGE=true to proceed."
    echo "   This is a safety measure to prevent accidental merges."
    exit 1
fi

# Save current branch
ORIGINAL_BRANCH=$(git branch --show-current)

# Fetch all open PRs
PR_RESPONSE=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "${API_BASE}/pulls?state=open&per_page=100")

PR_COUNT=$(echo "$PR_RESPONSE" | jq 'length')

if [ "$PR_COUNT" -eq 0 ]; then
    echo "No open PRs found"
    exit 0
fi

MERGED_COUNT=0
SKIPPED_COUNT=0
FAILED_COUNT=0

# Process each PR
echo "$PR_RESPONSE" | jq -c '.[]' | while read -r pr; do
    PR_NUMBER=$(echo "$pr" | jq -r '.number')
    PR_TITLE=$(echo "$pr" | jq -r '.title')
    PR_BRANCH=$(echo "$pr" | jq -r '.head.ref')
    PR_SHA=$(echo "$pr" | jq -r '.head.sha')
    MERGEABLE=$(echo "$pr" | jq -r '.mergeable')
    MERGEABLE_STATE=$(echo "$pr" | jq -r '.mergeable_state')
    
    echo "Processing PR #${PR_NUMBER}: ${PR_TITLE}"
    
    # Check mergeability
    if [ "$MERGEABLE_STATE" = "dirty" ]; then
        echo "  ✗ Skipping - has merge conflicts"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    if [ "$MERGEABLE" = "false" ]; then
        echo "  ✗ Skipping - not mergeable"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    # Get check status
    CHECKS_RESPONSE=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
        "${API_BASE}/commits/${PR_SHA}/check-runs")
    
    TOTAL_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '.total_count')
    FAILED_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '[.check_runs[] | select(.conclusion == "failure" or .conclusion == "timed_out" or .conclusion == "action_required")] | length')
    PENDING_CHECKS=$(echo "$CHECKS_RESPONSE" | jq '[.check_runs[] | select(.status == "queued" or .status == "in_progress")] | length')
    
    if [ "$FAILED_CHECKS" -gt 0 ]; then
        echo "  ✗ Skipping - ${FAILED_CHECKS} check(s) failing"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    if [ "$PENDING_CHECKS" -gt 0 ]; then
        echo "  ⏳ Skipping - ${PENDING_CHECKS} check(s) still running"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    # Run tests locally if enabled
    if [ "$RUN_TESTS" = "true" ]; then
        echo "  Checking out branch for local tests..."
        git fetch origin "${PR_BRANCH}:${PR_BRANCH}" 2>/dev/null || true
        git checkout "${PR_BRANCH}" 2>/dev/null || {
            echo "  ⚠ Could not checkout branch - skipping"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        }
        
        TESTS_PASSED=true
        
        # Run npm tests
        if [ -f "package.json" ] && grep -q "\"test\"" package.json 2>/dev/null; then
            echo "  Running npm test..."
            if ! npm test 2>/dev/null; then
                TESTS_PASSED=false
            fi
        fi
        
        # Run pytest
        if [ -f "pytest.ini" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
            echo "  Running pytest..."
            if ! pytest 2>/dev/null; then
                TESTS_PASSED=false
            fi
        fi
        
        # Return to original branch
        git checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
        
        if [ "$TESTS_PASSED" = false ]; then
            echo "  ✗ Skipping - local tests failed"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi
        
        echo "  ✓ Local tests passed"
    fi
    
    # Create backup branch
    BACKUP_BRANCH="backup/pr-${PR_NUMBER}-$(date +%Y%m%d-%H%M%S)"
    echo "  Creating backup branch: ${BACKUP_BRANCH}"
    git branch "${BACKUP_BRANCH}" "${PR_BRANCH}" 2>/dev/null || true
    
    # Merge the PR
    echo "  Merging PR #${PR_NUMBER}..."
    
    MERGE_DATA="{\"merge_method\": \"${MERGE_METHOD}\""
    if [ "$MERGE_METHOD" = "squash" ]; then
        MERGE_DATA="${MERGE_DATA}, \"commit_title\": \"${PR_TITLE} (#${PR_NUMBER})\""
    fi
    MERGE_DATA="${MERGE_DATA}}"
    
    MERGE_RESPONSE=$(curl -s -X PUT \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        -d "$MERGE_DATA" \
        "${API_BASE}/pulls/${PR_NUMBER}/merge")
    
    MERGED=$(echo "$MERGE_RESPONSE" | jq -r '.merged')
    
    if [ "$MERGED" = "true" ]; then
        echo "  ✓ Successfully merged"
        MERGED_COUNT=$((MERGED_COUNT + 1))
        
        # Delete the branch
        echo "  Deleting branch: ${PR_BRANCH}"
        curl -s -X DELETE \
            -H "Authorization: token ${GITHUB_TOKEN}" \
            "${API_BASE}/git/refs/heads/${PR_BRANCH}"
    else
        REASON=$(echo "$MERGE_RESPONSE" | jq -r '.message')
        echo "  ✗ Merge failed: ${REASON}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
    
    echo ""
done

echo "=== Summary ==="
echo "Merged: ${MERGED_COUNT}, Skipped: ${SKIPPED_COUNT}, Failed: ${FAILED_COUNT}"
echo ""
echo "Backup branches created for all merged PRs."
echo "Review and delete backup branches manually when no longer needed:"
git branch | grep "backup/pr-" || true
