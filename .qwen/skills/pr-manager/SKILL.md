# PR Manager Skill

## Purpose
Automated skill for reviewing, fixing, and merging all open pull requests in the repository.

## Capabilities
- **List Open PRs**: Fetch all open pull requests with their status
- **Review PRs**: Analyze code changes, check for issues, and provide feedback
- **Fix Issues**: Automatically fix common issues (linting, formatting, simple bugs)
- **Run Checks**: Execute tests, linting, and type checking
- **Merge PRs**: Safely merge PRs that pass all checks

## Usage

```bash
# Invoke the skill
skill: "pr-manager"
```

## Workflow

1. **Discovery Phase**
   - List all open PRs using GitHub API
   - Check CI/CD status for each PR
   - Identify merge conflicts and blockers

2. **Review Phase**
   - Fetch diff for each PR
   - Run static analysis on changed files
   - Check for common issues (linting, formatting, type errors)

3. **Fix Phase**
   - Checkout each PR branch
   - Run automated fixes (prettier, eslint, ruff, etc.)
   - Run tests to verify changes
   - Commit and push fixes if needed

4. **Merge Phase**
   - Verify all checks pass
   - Ensure no merge conflicts
   - Merge using appropriate strategy (squash, rebase, merge)
   - Delete merged branches

## Scripts

### `review-prs.sh`
Lists and reviews all open PRs with their status.

### `fix-prs.sh`
Automatically fixes common issues in PR branches.

### `merge-prs.sh`
Merges all PRs that pass checks.

## Configuration

Set the following environment variables:
- `GITHUB_TOKEN`: GitHub personal access token with repo access
- `GITHUB_REPO`: Repository name (default: from git remote)
- `GITHUB_OWNER`: Repository owner (default: from git remote)
- `AUTO_MERGE`: Set to "true" to enable automatic merging (default: false)
- `RUN_TESTS`: Set to "true" to run tests before merging (default: true)

## Safety Features

- Requires all CI checks to pass before merging
- Skips PRs with merge conflicts
- Requires review approval (unless AUTO_MERGE=true)
- Creates backup branches before merging
- Logs all actions for audit trail

## Example Output

```
=== PR Manager Report ===
Total Open PRs: 5

✓ PR #42: Feature X - Ready to merge (all checks pass)
✓ PR #43: Bug fix Y - Ready to merge (all checks pass)
⚠ PR #44: Refactor Z - 2 checks failing
✗ PR #45: New feature - Merge conflicts detected
⚠ PR #46: Hotfix - Awaiting review approval

Actions taken:
- Fixed linting issues in PR #44
- Pushed fixes to remote
- Merged PR #42, #43
- Skipped PR #45, #46

Summary: 2 merged, 2 fixed, 2 skipped
```
