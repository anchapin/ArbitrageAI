# Batch GitHub Issues & PRs - Complete Guide

> **Automated tools for creating, managing, and tracking GitHub issues and pull requests in batches.**

[![GitHub CLI](https://img.shields.io/badge/GitHub-CLI-blue)](https://cli.github.com/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green)](https://python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](https://opensource.org/licenses/MIT)

---

## 📖 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Tools Overview](#tools-overview)
- [Detailed Usage](#detailed-usage)
- [Workflow Examples](#workflow-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

---

## 🎯 Overview

This toolkit provides automated solutions for:

1. **Batch Issue Creation** - Create multiple GitHub issues from markdown files
2. **Phased Rollout** - Execute issue creation in priority-based phases
3. **PR Automation** - Automatically create branches and PR templates
4. **Progress Tracking** - Monitor and report on issue/PR status
5. **Workflow Integration** - Integrate with GitHub Projects and CI/CD

### Key Features

| Feature | Description |
|---------|-------------|
| 📝 **Markdown-based** | Create issues from pre-written markdown files |
| 🎚️ **Priority Phases** | Roll out issues in phases (Critical → High → Medium) |
| 🏷️ **Auto-labeling** | Intelligent label assignment based on content |
| 🌿 **Branch Management** | Automatic branch creation and naming |
| 📋 **PR Templates** | Generate PR templates with acceptance criteria |
| 📊 **Progress Reports** | Real-time progress tracking and reporting |
| 🔮 **Dry Run Mode** | Preview changes before executing |
| 💾 **Results Logging** | Save results to JSON for audit trails |

---

## 🚀 Quick Start

### 1-Minute Setup

```bash
# 1. Install GitHub CLI (if not already installed)
brew install gh  # macOS
# or follow installation guide at https://cli.github.com/

# 2. Authenticate with GitHub
gh auth login

# 3. Install Python dependencies
pip install pyyaml

# 4. Test the tools (dry run)
python scripts/batch_github_issues.py dry-run

# 5. Create all issues
python scripts/batch_github_issues.py create-issues
```

### Common Commands

```bash
# Preview what will be created
python scripts/batch_github_issues.py dry-run

# Create all issues from .github/ISSUES/
python scripts/batch_github_issues.py create-issues

# Create issues by priority phase
python scripts/batch_orchestrator.py phase critical  # Critical security issues
python scripts/batch_orchestrator.py phase high      # High priority issues
python scripts/batch_orchestrator.py phase all       # All issues

# Check status
python scripts/batch_github_issues.py status

# Create PRs for issues
python scripts/batch_github_issues.py create-prs

# Generate progress report
python scripts/batch_orchestrator.py report
```

---

## 📦 Installation

### Prerequisites

#### 1. GitHub CLI

**macOS:**
```bash
brew install gh
```

**Linux (Debian/Ubuntu):**
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

**Linux (RHEL/Fedora):**
```bash
sudo gh repo add github/cli https://cli.github.com/packages/rpm
sudo dnf install gh
```

**Windows:**
```bash
winget install --id GitHub.cli
```

#### 2. Authenticate GitHub CLI

```bash
# Interactive authentication
gh auth login

# Or use web flow
gh auth login --web

# Verify authentication
gh auth status
```

#### 3. Python Dependencies

```bash
# Install PyYAML for parsing issue files
pip install pyyaml

# Or install all dev dependencies
pip install -e ".[dev]"
```

#### 4. Verify Installation

```bash
# Check GitHub CLI
gh --version

# Check Python
python --version

# Test script
python scripts/batch_github_issues.py --help
```

---

## 🛠️ Tools Overview

### Tool Comparison

| Tool | Best For | Complexity |
|------|----------|------------|
| `batch_github_issues.py` | Simple batch creation | ⭐ Basic |
| `batch_orchestrator.py` | Phased rollout with tracking | ⭐⭐⭐ Advanced |
| `create_github_issues.sh` | Legacy bash script | ⭐⭐ Intermediate |

### 1. Batch GitHub Issues (`batch_github_issues.py`)

**Purpose:** Simple, straightforward batch issue and PR creation.

**Commands:**
- `create-issues` - Create all issues from markdown files
- `create-prs` - Create PRs for existing issues
- `status` - Show current status
- `dry-run` - Preview without creating

**Example:**
```bash
python scripts/batch_github_issues.py create-issues --dry-run
```

### 2. Batch Orchestrator (`batch_orchestrator.py`)

**Purpose:** Advanced workflow automation with phased rollout.

**Commands:**
- `phase <priority>` - Execute phase (critical/high/medium/all)
- `progress` - Show progress report
- `report` - Generate detailed report

**Example:**
```bash
python scripts/batch_orchestrator.py phase critical --verbose
```

### 3. Legacy Scripts

- `create_github_issues.sh` - Bash script for simple creation
- `create_qaqc_issues.py` - Python script with hardcoded issues

---

## 📖 Detailed Usage

### Batch GitHub Issues Tool

#### Create Issues

```bash
# Create all issues
python scripts/batch_github_issues.py create-issues

# Create with assignee
python scripts/batch_github_issues.py create-issues --assignee username

# Dry run (preview)
python scripts/batch_github_issues.py create-issues --dry-run

# Specify repository
python scripts/batch_github_issues.py create-issues --repo /path/to/repo
```

**What happens:**
1. Scans `.github/ISSUES/*.md` files
2. Extracts title, priority, labels from front matter
3. Creates GitHub issues via `gh issue create`
4. Assigns labels based on content analysis
5. Saves results to `.github/batch_results.json`

#### Create PRs

```bash
# Create PRs for all issues
python scripts/batch_github_issues.py create-prs

# Create PRs for specific issues
python scripts/batch_github_issues.py create-prs --numbers 1 2 3

# Create PRs with assignee
python scripts/batch_github_issues.py create-prs --assignee username
```

**What happens:**
1. Creates git branch for each issue
2. Generates PR template with acceptance criteria
3. Pushes branch to remote
4. Creates PR via `gh pr create`
5. Links PR to issue

#### Check Status

```bash
python scripts/batch_github_issues.py status
```

**Output:**
- List of all QA/QC issues
- Priority indicators (🔴 🟡 🟢)
- State (open/closed)
- Associated PRs
- Creation dates

### Batch Orchestrator Tool

#### Execute Phase

```bash
# Phase 1: Critical Security
python scripts/batch_orchestrator.py phase critical

# Phase 2: High Priority
python scripts/batch_orchestrator.py phase high

# Phase 3: Medium Priority
python scripts/batch_orchestrator.py phase medium

# All phases
python scripts/batch_orchestrator.py phase all

# With dry run
python scripts/batch_orchestrator.py phase critical --dry-run

# Verbose output
python scripts/batch_orchestrator.py phase high --verbose
```

**Phase Definitions:**

| Phase | Priority | Duration | Focus |
|-------|----------|----------|-------|
| Phase 1 | Critical | 2 weeks | Security vulnerabilities |
| Phase 2 | High | 4 weeks | Code quality & architecture |
| Phase 3 | Medium | 3 weeks | Performance optimizations |

#### Progress Tracking

```bash
# Show progress dashboard
python scripts/batch_orchestrator.py progress

# Generate detailed report
python scripts/batch_orchestrator.py report

# Save report to file
python scripts/batch_orchestrator.py report --output progress_report.md
```

---

## 🎬 Workflow Examples

### Example 1: Complete Workflow (Recommended)

```bash
# Step 1: Preview what will be created
python scripts/batch_github_issues.py dry-run

# Step 2: Create critical issues first
python scripts/batch_orchestrator.py phase critical

# Step 3: Verify critical issues created
python scripts/batch_github_issues.py status

# Step 4: Create high priority issues
python scripts/batch_orchestrator.py phase high

# Step 5: Create PRs for ready issues
python scripts/batch_github_issues.py create-prs --numbers 1 2 3

# Step 6: Generate progress report
python scripts/batch_orchestrator.py report --output week1_report.md
```

### Example 2: Incremental Rollout

```bash
# Monday: Create critical issues
python scripts/batch_orchestrator.py phase critical

# Wednesday: Check progress
python scripts/batch_orchestrator.py progress

# Friday: Create high priority issues
python scripts/batch_orchestrator.py phase high

# Next week: Create remaining issues
python scripts/batch_orchestrator.py phase medium
```

### Example 3: Team Assignment

```bash
# Create issues and assign to team leads
python scripts/batch_github_issues.py create-issues --assignee tech-lead

# Create PRs for specific team members
python scripts/batch_github_issues.py create-prs --numbers 4 5 --assignee dev1
python scripts/batch_github_issues.py create-prs --numbers 6 7 --assignee dev2
```

### Example 4: Multi-Repository

```bash
# Repository 1
python scripts/batch_github_issues.py create-issues --repo /path/to/repo1

# Repository 2
python scripts/batch_github_issues.py create-issues --repo /path/to/repo2

# Repository 3
python scripts/batch_github_issues.py create-issues --repo /path/to/repo3
```

---

## 📁 File Structure

```
.github/
├── ISSUES/                          # Issue markdown files
│   ├── README.md                    # Tracking index
│   ├── QAQC-001-security-eval-replacement.md
│   ├── QAQC-002-security-insecure-defaults.md
│   ├── QAQC-003-security-production-validation.md
│   ├── QAQC-004-code-quality-undefined-names.md
│   └── ...
├── ISSUE_TEMPLATE/                  # GitHub issue templates
│   ├── qaqc-critical-security.md
│   ├── qaqc-code-quality.md
│   └── ...
├── PR_TEMPLATES/                    # Generated PR templates
│   ├── PR-1.md
│   ├── PR-2.md
│   └── ...
├── batch_results/                   # Phase execution results
│   ├── phase_phase1_20260303_103000.json
│   └── ...
├── batch_results.json               # Latest batch results
└── pull_request_template.md         # Default PR template

scripts/
├── batch_github_issues.py           # Main batch tool
├── batch_orchestrator.py            # Workflow orchestrator
├── create_github_issues.sh          # Legacy bash script
└── create_qaqc_issues.py            # Legacy Python script
```

---

## 🏷️ Issue File Format

### Required Front Matter

```markdown
---
title: "CRITICAL: Replace eval() calls with json.loads()"
priority: critical
estimated_effort: 2 days
labels:
  - security
  - critical
  - bug
created: 2026-03-03
---

# Issue Description

Detailed description of the issue...

## Risk Assessment

- **Severity:** CRITICAL
- **CVSS Score:** ~9.8
- **Attack Vector:** Network

## Acceptance Criteria

- [ ] All eval() calls replaced
- [ ] Tests added
- [ ] Security scan passes

## Implementation Notes

Code examples and implementation guidance...
```

### Automatic Label Assignment

The tools automatically assign labels based on:

1. **Front matter** - Explicit labels in YAML
2. **Priority keywords** - CRITICAL, HIGH, MEDIUM in content
3. **Content analysis** - Security, performance, refactor keywords

**Label Mapping:**

| Keywords Found | Label Assigned |
|----------------|----------------|
| security, vulnerability, RCE, injection | `security` |
| performance, optimization, redis, index | `performance` |
| refactor, code quality, cleanup | `code-quality` |
| architecture, migration, database | `architecture` |
| test, coverage | `testing` |
| documentation, readme, guide | `documentation` |

---

## 📊 Output & Reporting

### Console Output

```
======================================================================
🚀 BATCH ISSUE CREATION
======================================================================
Total issues to create: 11
Dry run: False
======================================================================

[1/11] Processing: QAQC-001-security-eval-replacement.md
----------------------------------------------------------------------
  📝 Creating issue: CRITICAL: Replace eval() calls with json.loads()...
    ✅ Created: https://github.com/user/repo/issues/1

[2/11] Processing: QAQC-002-security-insecure-defaults.md
----------------------------------------------------------------------
  📝 Creating issue: CRITICAL: Implement secure random secret generation...
    ✅ Created: https://github.com/user/repo/issues/2

======================================================================
📊 BATCH OPERATION SUMMARY
======================================================================
Total:    11
✅ Success: 10 (90.9%)
❌ Failed:  1 (9.1%)
⏭️  Skipped: 0
======================================================================
```

### JSON Results

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

### Progress Report

```markdown
# Batch Issues Progress Report

**Generated:** 2026-03-03 10:30:00
**Repository:** ArbitrageAI

## Executive Summary

This report provides an overview of the QA/QC batch issue creation...

## Phase Status

### Critical Security (phase1)

**Description:** Address critical security vulnerabilities
**Target Duration:** 2 weeks

**Success Criteria:**
- [ ] Zero critical security vulnerabilities
- [ ] All secrets securely generated
- [ ] Production validation enforced

## Issues (11 total)

🔄🔴 #1: CRITICAL: Replace eval() calls with json.loads()
   - State: open
   - Created: 2026-03-03
   - URL: https://github.com/user/repo/issues/1
```

---

## ✅ Best Practices

### Before Creating Issues

1. ✅ **Review all issue files** - Ensure content is accurate
2. ✅ **Run dry-run** - Preview what will be created
3. ✅ **Check authentication** - Verify `gh auth status`
4. ✅ **Backup current state** - Export existing issues
5. ✅ **Notify team** - Coordinate issue creation timing

### During Creation

1. ✅ **Monitor output** - Watch for errors
2. ✅ **Verify on GitHub** - Check issues appear correctly
3. ✅ **Save results** - Keep JSON results for audit
4. ✅ **Update tracking** - Update project boards

### After Creation

1. ✅ **Add to projects** - Link issues to GitHub Projects
2. ✅ **Assign team members** - Assign issues appropriately
3. ✅ **Set milestones** - Add to sprint milestones
4. ✅ **Create PRs** - Create PRs for ready-to-implement issues
5. ✅ **Track progress** - Regular progress reports

### Issue File Management

1. ✅ **Use front matter** - Include title, priority, effort
2. ✅ **Clear acceptance criteria** - Define done clearly
3. ✅ **Implementation notes** - Provide guidance
4. ✅ **Code examples** - Show before/after
5. ✅ **Testing requirements** - Specify needed tests

---

## 🐛 Troubleshooting

### GitHub CLI Issues

#### Authentication Failed

```bash
# Check status
gh auth status

# Re-authenticate
gh auth logout
gh auth login

# Use web flow
gh auth login --web

# Check token permissions
gh api user | jq .
```

#### Rate Limiting

```bash
# Check rate limit
gh api rate_limit

# Wait for reset or use different token
```

#### Permission Denied

```bash
# Check repository permissions
gh repo view --json name,owner,permissions

# Ensure you have write access
```

### Git Issues

#### Branch Already Exists

```bash
# List branches
git branch -a | grep issue/

# Delete local branch
git branch -D issue/1-example

# Delete remote branch
git push origin --delete issue/1-example
```

#### Not on Main Branch

```bash
# Switch to main
git checkout main
git pull origin main
```

### Python Issues

#### Module Not Found

```bash
# Install dependencies
pip install pyyaml

# Or install in dev mode
pip install -e ".[dev]"
```

#### Permission Errors

```bash
# Run with appropriate permissions
# Don't run as root - fix file permissions instead
chmod +x scripts/batch_github_issues.py
```

### Issue Creation Failures

#### Label Doesn't Exist

```bash
# Create label first
gh label create security --color "#d73a4a" --description "Security issues"

# Or let GitHub auto-create (will be created on first use)
```

#### Duplicate Issue

```bash
# Check if issue exists
gh issue list --search "eval replacement"

# Close duplicate
gh issue close <issue-number>
```

---

## 🔗 Integration

### GitHub Projects

```bash
# Get project ID
gh project list --owner <org-or-user>

# Add issue to project
gh project item-add <project-id> \
  --owner <org-or-user> \
  --url <issue-url>

# Add item to project board column
gh project item-edit \
  --project-id <project-id> \
  --item-id <item-id> \
  --field-id <field-id> \
  --single-select-option-id <option-id>
```

### GitHub Actions

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
      phase:
        description: 'Phase (for orchestrator)'
        required: false
        type: choice
        options:
          - critical
          - high
          - medium
          - all

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
        run: |
          pip install pyyaml
          pip install -e ".[dev]"

      - name: Authenticate GitHub CLI
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | gh auth login --with-token

      - name: Run batch tool
        run: |
          if [ "${{ github.event.inputs.phase }}" != "" ]; then
            python scripts/batch_orchestrator.py phase ${{ github.event.inputs.phase }}
          else
            python scripts/batch_github_issues.py ${{ github.event.inputs.command }}
          fi

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: batch-results
          path: .github/batch_results*.json
```

### CI/CD Integration

Add to existing CI/CD pipeline:

```yaml
- name: Check Issue Creation
  run: |
    python scripts/batch_github_issues.py status
    if [ $? -ne 0 ]; then
      echo "Issue creation check failed"
      exit 1
    fi
```

---

## 📚 API Reference

### Batch GitHub Issues Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `create-issues` | `--dry-run`, `--assignee`, `--repo` | Create issues from markdown |
| `create-prs` | `--numbers`, `--assignee`, `--dry-run` | Create PRs for issues |
| `status` | None | Show current status |
| `dry-run` | None | Preview all actions |

### Batch Orchestrator Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `phase` | `<phase>`, `--dry-run`, `--verbose` | Execute phase |
| `progress` | None | Show progress dashboard |
| `report` | `--output` | Generate detailed report |

### Phase Options

| Phase | Priority | Description |
|-------|----------|-------------|
| `critical` / `phase1` | Critical | Security vulnerabilities |
| `high` / `phase2` | High | Code quality & architecture |
| `medium` / `phase3` | Medium | Performance optimizations |
| `all` | All | Execute all phases |

---

## 📄 License

MIT License - See [LICENSE](../LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `--dry-run`
5. Submit a PR

---

## 📞 Support

- **Documentation:** This file and `.github/README_BATCH_TOOLS.md`
- **Issues:** Create an issue in this repository
- **Examples:** See workflow examples above

---

**Last Updated:** March 3, 2026  
**Version:** 1.0.0  
**Maintained By:** Development Team
