# PR Manager Skill

## Quick Start

```bash
# Set your GitHub token
export GITHUB_TOKEN=ghp_your_token_here

# Review all open PRs
skill: "pr-manager"  # or run ./pr-manager.sh review

# Fix linting/formatting issues
./pr-manager.sh fix

# Merge all ready PRs (requires AUTO_MERGE=true)
AUTO_MERGE=true ./pr-manager.sh merge

# Run full workflow
AUTO_MERGE=true ./pr-manager.sh all
```

## What It Does

### 1. Review (`review-prs.sh`)
- Lists all open PRs with status
- Shows CI/CD check results
- Identifies merge conflicts
- Reports test failures

### 2. Fix (`fix-prs.sh`)
- Checks out each PR branch
- Runs ESLint/Prettier (JavaScript/TypeScript)
- Runs Ruff/Black (Python)
- Runs tests to verify fixes
- Commits and pushes changes

### 3. Merge (`merge-prs.sh`)
- Verifies all CI checks pass
- Creates backup branches
- Merges using configured method (default: squash)
- Deletes merged branches

## Requirements

- `curl` - HTTP requests to GitHub API
- `jq` - JSON parsing
- `git` - Version control operations
- Language tools (optional): `eslint`, `prettier`, `ruff`, `black`, `npm`, `pytest`

## GitHub Token

Create a token at: https://github.com/settings/tokens

Required scopes:
- `repo` - Full control of private repositories
- `workflow` - Update GitHub Actions workflows

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | (required) | GitHub personal access token |
| `GITHUB_OWNER` | (auto) | Repository owner |
| `GITHUB_REPO` | (auto) | Repository name |
| `AUTO_MERGE` | `false` | Enable automatic merging |
| `RUN_TESTS` | `true` | Run tests before merging |
| `DRY_RUN` | `false` | Preview fixes without committing |
| `MERGE_METHOD` | `squash` | Merge method: squash, merge, rebase |

## Safety Features

✓ Requires all CI checks to pass  
✓ Skips PRs with merge conflicts  
✓ Creates backup branches before merging  
✓ `AUTO_MERGE` flag prevents accidental merges  
✓ Dry-run mode for testing fixes  

## Examples

**Review only (safe, no changes):**
```bash
export GITHUB_TOKEN=ghp_...
./pr-manager.sh review
```

**Fix issues with dry-run:**
```bash
DRY_RUN=true ./pr-manager.sh fix
```

**Full automated workflow:**
```bash
export GITHUB_TOKEN=ghp_...
export AUTO_MERGE=true
export RUN_TESTS=true
./pr-manager.sh all
```

## Troubleshooting

**"Invalid GitHub token"**
- Verify token is correct and has required scopes
- Check token hasn't expired

**"Could not detect GitHub owner/repo"**
- Ensure git remote is configured: `git remote -v`
- Or set `GITHUB_OWNER` and `GITHUB_REPO` manually

**"Merge conflicts detected"**
- PR must be updated with latest base branch
- Resolve conflicts manually before merging

**Tests failing locally but passing in CI**
- Check for uncommitted changes
- Verify local environment matches CI
