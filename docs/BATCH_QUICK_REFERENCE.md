# Batch GitHub Issues - Quick Reference Card

> **Quick command reference for batch issue and PR creation.**

---

## 🚀 Quick Start (1 Minute)

```bash
# Authenticate
gh auth login

# Test (dry run)
python scripts/batch_issue_processor.py process --all --dry-run

# Create all issues (parallel)
python scripts/batch_issue_processor.py process --all --parallel --workers 8

# Create PRs automatically
python scripts/batch_issue_processor.py create-prs --auto

# Check status
python scripts/batch_issue_processor.py status
```

---

## 📋 Command Cheat Sheet

### Enhanced Processor (Recommended)

```bash
# Create all issues
python scripts/batch_issue_processor.py process --all

# Create by priority
python scripts/batch_issue_processor.py process --priority high
python scripts/batch_issue_processor.py process --priority critical

# Parallel processing (faster)
python scripts/batch_issue_processor.py process --all --parallel --workers 8

# Preview first
python scripts/batch_issue_processor.py process --all --dry-run

# Create PRs
python scripts/batch_issue_processor.py create-prs --auto
python scripts/batch_issue_processor.py create-prs --numbers 1 2 3

# Status & Reports
python scripts/batch_issue_processor.py status
python scripts/batch_issue_processor.py report
```

### Basic Batch Tool

```bash
# Create issues
python scripts/batch_github_issues.py create-issues

# Create PRs
python scripts/batch_github_issues.py create-prs

# Status
python scripts/batch_github_issues.py status

# Dry run
python scripts/batch_github_issues.py dry-run
```

### Batch Orchestrator (Phased)

```bash
# Phase 1: Critical
python scripts/batch_orchestrator.py phase critical

# Phase 2: High
python scripts/batch_orchestrator.py phase high

# Phase 3: Medium
python scripts/batch_orchestrator.py phase medium

# All phases
python scripts/batch_orchestrator.py phase all

# Progress
python scripts/batch_orchestrator.py progress
python scripts/batch_orchestrator.py report
```

### GitHub Projects Integration

```bash
# Add single issue
python scripts/github_projects_integration.py add-issue 123 --project "QA/QC"

# Sync all issues
python scripts/github_projects_integration.py sync --project "QA/QC"

# Check status
python scripts/github_projects_integration.py status --project "QA/QC"

# Generate report
python scripts/github_projects_integration.py report --project "QA/QC"
```

---

## 🎯 Common Workflows

### Workflow 1: Small Batch (< 10 issues)

```bash
python scripts/batch_github_issues.py dry-run
python scripts/batch_github_issues.py create-issues
python scripts/batch_github_issues.py status
```

### Workflow 2: Large Batch (> 20 issues) ⭐ Recommended

```bash
python scripts/batch_issue_processor.py process --all --parallel --workers 8
python scripts/batch_issue_processor.py create-prs --auto
python scripts/github_projects_integration.py sync --project "QA/QC"
python scripts/batch_issue_processor.py status
```

### Workflow 3: Phased Rollout

```bash
python scripts/batch_orchestrator.py phase critical
# Review Phase 1...
python scripts/batch_orchestrator.py phase high
# Review Phase 2...
python scripts/batch_orchestrator.py phase medium
python scripts/batch_orchestrator.py report
```

### Workflow 4: Priority-Based

```bash
# Critical first
python scripts/batch_issue_processor.py process --priority critical --parallel
# Then high
python scripts/batch_issue_processor.py process --priority high --parallel
# Then medium
python scripts/batch_issue_processor.py process --priority medium --parallel
```

---

## 🏷️ Issue File Template

```markdown
---
title: "Clear, Descriptive Title"
priority: high  # critical, high, medium, low
estimated_effort: 4-6 hours
---

# Issue Title

## Description
Clear description of what needs to be done.

## Acceptance Criteria
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3

## Implementation Plan
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## Additional Context
Any additional information or references.
```

---

## ⚡ Performance Tips

| Scenario | Command | Expected Time |
|----------|---------|---------------|
| **10 issues** | `--parallel --workers 4` | ~15 seconds |
| **50 issues** | `--parallel --workers 8` | ~40 seconds |
| **100 issues** | `--parallel --workers 8` | ~75 seconds |

**Max speed:**
```bash
python scripts/batch_issue_processor.py process --all --parallel --workers 8
```

---

## 🔧 Options Reference

### `process` Command

| Option | Description | Default |
|--------|-------------|---------|
| `--all` | Process all issues | - |
| `--priority <level>` | Filter by priority | - |
| `--parallel` | Enable parallel processing | Off |
| `--workers <N>` | Number of workers | 4 |
| `--dry-run` | Preview only | Off |
| `--verbose` | Verbose output | Off |

### `create-prs` Command

| Option | Description | Default |
|--------|-------------|---------|
| `--auto` | Automatic creation | - |
| `--numbers <N>` | Specific issues | All |
| `--assignee <user>` | Assign to user | - |

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Not authenticated | `gh auth login` |
| PyYAML missing | `pip install pyyaml` |
| Projects extension missing | `gh extension install github/gh-project` |
| Rate limit exceeded | Wait a few minutes, then retry |
| Branch exists | Normal warning, will use existing branch |

**Test everything:**
```bash
python scripts/test_batch_tools.py
```

---

## 📊 Tool Selection Guide

| Need | Tool |
|------|------|
| **Simple, quick batch** | `batch_github_issues.py` |
| **Large batch, fast** | `batch_issue_processor.py --parallel` |
| **Phased rollout** | `batch_orchestrator.py` |
| **Projects board** | `github_projects_integration.py` |
| **Auto PRs** | `batch_issue_processor.py create-prs` |

---

## 📈 Status Icons

- ✅ Created successfully
- ❌ Failed
- ⏭️ Skipped (dry run)
- 🟢 Open issue
- 🔒 Closed issue
- 📦 PR created
- 🔴 Critical priority
- 🟡 High priority
- 🟢 Medium priority

---

## 🔗 Quick Links

- **Full Guide:** [docs/ENHANCED_BATCH_PROCESSING_GUIDE.md](ENHANCED_BATCH_PROCESSING_GUIDE.md)
- **Issues Directory:** `.github/ISSUES/`
- **Results:** `.github/batch_results_enhanced.json`
- **Test Script:** `scripts/test_batch_tools.py`

---

## 💡 Pro Tips

1. **Always dry-run first:**
   ```bash
   python scripts/batch_issue_processor.py process --all --dry-run
   ```

2. **Use parallel for large batches:**
   ```bash
   --parallel --workers 8
   ```

3. **Auto-create PRs after issues:**
   ```bash
   create-prs --auto
   ```

4. **Sync to projects board:**
   ```bash
   github_projects_integration.py sync --project "QA/QC"
   ```

5. **Generate reports:**
   ```bash
   report > batch_report.md
   ```

---

**Last Updated:** March 2026
