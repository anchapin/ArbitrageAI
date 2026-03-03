# Batch GitHub Issues & PRs Management

> Automated tools for creating and managing GitHub issues and pull requests in batches.

## 📚 Overview

This directory contains tools and templates for efficiently managing GitHub issues and PRs, particularly for the QA/QC review process.

### Tools

| Script | Purpose | Usage |
|--------|---------|-------|
| [`batch_github_issues.py`](../scripts/batch_github_issues.py) | Main batch creation tool | `python scripts/batch_github_issues.py <command>` |
| [`create_github_issues.sh`](./create_github_issues.sh) | Legacy bash script | `bash scripts/create_github_issues.sh` |
| [`create_qaqc_issues.py`](./create_qaqc_issues.py) | Python issue creator | `python scripts/create_qaqc_issues.py` |

### Templates

| Template | Purpose |
|----------|---------|
| [`ISSUE_TEMPLATE/`](./ISSUE_TEMPLATE/) | GitHub issue templates for different categories |
| [`pull_request_template.md`](./pull_request_template.md) | Standard PR template |
| [`ISSUES/`](./ISSUES/) | Pre-written issue markdown files |

---

## 🚀 Quick Start

### Prerequisites

1. **GitHub CLI** installed and authenticated:
   ```bash
   # Install on macOS
   brew install gh

   # Install on Linux
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update && sudo apt install gh

   # Authenticate
   gh auth login
   ```

2. **Python 3.10+** with required dependencies:
   ```bash
   pip install pyyaml
   ```

3. **Git** repository initialized and you're on the `main` branch.

### Basic Usage

```bash
# 1. Preview what will be created (recommended first step)
python scripts/batch_github_issues.py dry-run

# 2. Create all issues from .github/ISSUES/ directory
python scripts/batch_github_issues.py create-issues

# 3. Check status of created issues and PRs
python scripts/batch_github_issues.py status

# 4. Create PRs for all issues
python scripts/batch_github_issues.py create-prs

# 5. Create PRs for specific issues only
python scripts/batch_github_issues.py create-prs --numbers 1 2 3
```

---

## 📖 Detailed Usage

### Command Reference

#### `create-issues`

Creates GitHub issues from markdown files in `.github/ISSUES/`.

```bash
# Create all issues
python scripts/batch_github_issues.py create-issues

# Dry run (preview only)
python scripts/batch_github_issues.py create-issues --dry-run

# Assign issues to a user
python scripts/batch_github_issues.py create-issues --assignee username
```

**What it does:**
- Scans `.github/ISSUES/*.md` files
- Extracts title, priority, and labels from each file
- Creates GitHub issues with proper metadata
- Generates branch names for each issue
- Saves results to `.github/batch_results.json`

#### `create-prs`

Creates pull requests for existing issues.

```bash
# Create PRs for all issues
python scripts/batch_github_issues.py create-prs

# Create PRs for specific issue numbers
python scripts/batch_github_issues.py create-prs --numbers 1 2 3

# Assign PRs to a user
python scripts/batch_github_issues.py create-prs --assignee username

# Dry run
python scripts/batch_github_issues.py create-prs --dry-run
```

**What it does:**
- Creates git branches for each issue
- Creates PR template files
- Pushes branches to remote
- Creates GitHub PRs with proper linking

#### `status`

Shows current status of issues and PRs.

```bash
python scripts/batch_github_issues.py status
```

**Output includes:**
- List of all QA/QC issues with state (open/closed)
- Priority indicators (🔴 critical, 🟡 high, 🟢 medium)
- Associated PRs
- Creation dates

#### `dry-run`

Preview all actions without making any changes.

```bash
python scripts/batch_github_issues.py dry-run
```

**Perfect for:**
- Testing before actual creation
- Understanding what will be created
- Validating issue files

---

## 📁 File Structure

```
.github/
├── ISSUES/                          # Issue markdown files
│   ├── README.md                    # Tracking index
│   ├── QAQC-001-security-eval-replacement.md
│   ├── QAQC-002-security-insecure-defaults.md
│   └── ...
├── ISSUE_TEMPLATE/                  # GitHub issue templates
│   ├── qaqc-critical-security.md
│   ├── qaqc-code-quality.md
│   └── ...
├── PR_TEMPLATES/                    # Generated PR templates
│   └── PR-1.md
├── batch_results.json               # Results from batch operations
└── pull_request_template.md         # Default PR template
```

---

## 🔧 Configuration

### Issue File Format

Each issue markdown file should have YAML front matter:

```markdown
---
title: "CRITICAL: Replace eval() calls with json.loads()"
priority: critical
labels:
  - security
  - critical
  - bug
created: 2026-03-03
---

# Issue Description

Detailed description of the issue...

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
```

### Label Mapping

The tool automatically assigns labels based on content analysis:

| Keyword | Label Assigned |
|---------|----------------|
| security, vulnerability, RCE | `security` |
| performance, optimization, redis | `performance` |
| refactor, code quality | `code-quality` |
| architecture, migration, database | `architecture` |
| test, coverage | `testing` |
| documentation, readme | `documentation` |

Priority labels (`critical`, `high`, `medium`) are extracted from front matter or content.

---

## 📊 Output & Reporting

### Batch Results JSON

After each batch operation, results are saved to `.github/batch_results.json`:

```json
{
  "timestamp": "2026-03-03T10:30:00",
  "dry_run": false,
  "summary": {
    "total": 11,
    "success": 10,
    "failed": 1,
    "skipped": 0
  },
  "issues": [
    {
      "file": ".github/ISSUES/QAQC-001-security-eval-replacement.md",
      "title": "CRITICAL: Replace eval() calls...",
      "priority": "critical",
      "labels": ["security", "critical"],
      "number": 1,
      "url": "https://github.com/user/repo/issues/1",
      "branch": "issue/1-replace-eval-calls",
      "status": "created",
      "created_at": "2026-03-03T10:30:00"
    }
  ]
}
```

### Console Output

The tool provides rich console output with:
- Progress indicators
- Success/failure icons
- Summary statistics
- Issue URLs

---

## 🎯 Best Practices

### Before Creating Issues

1. ✅ Review all issue files in `.github/ISSUES/`
2. ✅ Ensure issue content is accurate and complete
3. ✅ Run a dry-run to preview
4. ✅ Verify GitHub CLI authentication

### During Creation

1. ✅ Monitor console output for errors
2. ✅ Check `.github/batch_results.json` after completion
3. ✅ Verify issues on GitHub

### After Creation

1. ✅ Add issues to GitHub Project board
2. ✅ Assign team members
3. ✅ Set milestones
4. ✅ Create PRs for ready-to-implement issues

---

## 🐛 Troubleshooting

### GitHub CLI Authentication Issues

```bash
# Check authentication status
gh auth status

# Re-authenticate
gh auth logout
gh auth login

# Use web flow if token flow fails
gh auth login --web
```

### Permission Errors

Ensure you have write access to the repository:

```bash
# Check repository permissions
gh repo view --json name,owner,permissions
```

### Rate Limiting

GitHub API has rate limits. If you hit them:

```bash
# Check rate limit status
gh api rate_limit
```

### Branch Creation Failures

If branch creation fails:

```bash
# Ensure you're on main branch
git checkout main
git pull origin main

# Retry PR creation
python scripts/batch_github_issues.py create-prs --numbers <issue-number>
```

---

## 📝 Examples

### Example 1: Complete Workflow

```bash
# Step 1: Preview
python scripts/batch_github_issues.py dry-run

# Step 2: Create issues
python scripts/batch_github_issues.py create-issues

# Step 3: Check status
python scripts/batch_github_issues.py status

# Step 4: Create PRs for first 3 issues
python scripts/batch_github_issues.py create-prs --numbers 1 2 3

# Step 5: Verify
python scripts/batch_github_issues.py status
```

### Example 2: Incremental Creation

```bash
# Create issues one at a time
python scripts/batch_github_issues.py create-issues --dry-run | grep "QAQC-001"
python scripts/batch_github_issues.py create-issues  # Creates all

# Create PRs as issues are ready
python scripts/batch_github_issues.py create-prs --numbers 5
```

### Example 3: Assignee Management

```bash
# Create issues and assign to team members
python scripts/batch_github_issues.py create-issues --assignee dev1

# Create PRs with assignee
python scripts/batch_github_issues.py create-prs --assignee dev2
```

---

## 🔗 Integration with GitHub Projects

### Add Issues to Project Board

```bash
# Get project ID
gh project list --owner <org-or-user>

# Add issue to project
gh project item-add <project-id> --owner <org-or-user> --url <issue-url>
```

### Automate with GitHub Actions

Create `.github/workflows/batch-issues.yml`:

```yaml
name: Batch Issue Creation

on:
  workflow_dispatch:
    inputs:
      command:
        description: 'Command to run'
        required: true
        default: 'create-issues'
        type: choice
        options:
          - create-issues
          - create-prs
          - status

jobs:
  batch-issues:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install pyyaml

      - name: Authenticate GitHub CLI
        run: gh auth login --with-token <<< "${{ secrets.GITHUB_TOKEN }}"

      - name: Run batch tool
        run: python scripts/batch_github_issues.py ${{ github.event.inputs.command }}
```

---

## 📚 Related Documentation

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Issues Documentation](https://docs.github.com/en/issues)
- [GitHub Pull Requests Documentation](https://docs.github.com/en/pull-requests)
- [QA/QC Review Summary](../QAQC_GITHUB_ISSUES_SUMMARY.md)
- [Issues Tracking Index](./ISSUES/README.md)

---

## 🤝 Contributing

To add new issue templates or improve the batch tools:

1. Create issue files in `.github/ISSUES/`
2. Update this README
3. Test with `--dry-run`
4. Submit PR

---

## 📄 License

MIT License - See [LICENSE](../LICENSE) for details.

---

**Last Updated:** March 3, 2026  
**Maintained By:** Development Team
