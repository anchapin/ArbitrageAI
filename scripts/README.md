# Batch GitHub Issues Scripts

> **Automated tools for creating, managing, and tracking GitHub issues and PRs in batches.**

---

## 🚀 Quick Start

```bash
# 1. Authenticate with GitHub
gh auth login

# 2. Install dependencies
pip install pyyaml

# 3. Test everything
./scripts/batch.sh test

# 4. Create all issues (parallel mode - fastest)
./scripts/batch.sh create

# 5. Create PRs automatically
./scripts/batch.sh prs

# 6. Check status
./scripts/batch.sh status
```

---

## 📋 Available Scripts

### Main Tools

| Script | Purpose | Speed | Best For |
|--------|---------|-------|----------|
| **`batch.sh`** | Easy wrapper | ⚡ Fast | **Daily use** |
| **`batch_issue_processor.py`** | Enhanced processor | ⚡⚡ **Fastest (8x)** | Large batches |
| **`batch_github_issues.py`** | Basic processor | 🐌 Sequential | Small batches |
| **`batch_orchestrator.py`** | Phased rollout | 🐌 Sequential | Controlled rollout |
| **`github_projects_integration.py`** | Projects sync | N/A | Project management |

### Quick Commands

```bash
# Using wrapper script (recommended)
./scripts/batch.sh create          # Create all issues
./scripts/batch.sh preview         # Dry run
./scripts/batch.sh prs             # Create PRs
./scripts/batch.sh status          # Check status
./scripts/batch.sh sync            # Sync to projects
./scripts/batch.sh report          # Generate report
./scripts/batch.sh test            # Run tests

# Using enhanced processor directly
python scripts/batch_issue_processor.py process --all --parallel --workers 8
python scripts/batch_issue_processor.py create-prs --auto
python scripts/batch_issue_processor.py status
```

---

## 🎯 Usage Examples

### Example 1: Quick Batch Creation

```bash
# Preview what will be created
./scripts/batch.sh preview

# Create all issues
./scripts/batch.sh create

# Check what was created
./scripts/batch.sh status
```

### Example 2: Large Batch (50+ Issues)

```bash
# Create all issues in parallel (8 workers)
python scripts/batch_issue_processor.py process --all --parallel --workers 8

# Auto-create PRs with smart content
python scripts/batch_issue_processor.py create-prs --auto

# Sync to GitHub Projects board
python scripts/github_projects_integration.py sync --project "QA/QC"

# Generate report
python scripts/batch_issue_processor.py report > report.md
```

### Example 3: Priority-Based Rollout

```bash
# Critical issues first
./scripts/batch.sh create critical

# Then high priority
./scripts/batch.sh create high

# Then medium
./scripts/batch.sh create medium

# Check progress
./scripts/batch.sh status
```

### Example 4: Phased Rollout (Controlled)

```bash
# Phase 1: Critical security
python scripts/batch_orchestrator.py phase critical

# Review Phase 1...

# Phase 2: High priority
python scripts/batch_orchestrator.py phase high

# Review Phase 2...

# Phase 3: Medium priority
python scripts/batch_orchestrator.py phase medium

# Final report
python scripts/batch_orchestrator.py report
```

---

## 📦 Installation

### Prerequisites

- **Python 3.10+**
- **Git**
- **GitHub CLI (gh)** - [Install](https://cli.github.com/)
- **PyYAML** - `pip install pyyaml`
- **GitHub Projects Extension** (optional) - `gh extension install github/gh-project`

### Setup

```bash
# 1. Install GitHub CLI
brew install gh  # macOS
# or follow https://cli.github.com/

# 2. Authenticate
gh auth login

# 3. Install Python dependencies
pip install pyyaml

# 4. (Optional) Install Projects extension
gh extension install github/gh-project

# 5. Test everything
./scripts/batch.sh test
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ENHANCED_BATCH_PROCESSING_GUIDE.md](../docs/ENHANCED_BATCH_PROCESSING_GUIDE.md) | Complete guide |
| [BATCH_QUICK_REFERENCE.md](../docs/BATCH_QUICK_REFERENCE.md) | Quick reference |
| [BATCH_IMPLEMENTATION_SUMMARY.md](../docs/BATCH_IMPLEMENTATION_SUMMARY.md) | Implementation report |

---

## 🔧 Enhanced Processor Features

### Parallel Execution

```bash
# 8x faster than sequential
python scripts/batch_issue_processor.py process --all --parallel --workers 8
```

**Performance:**
- 10 issues: 60s → 8s (7.5x faster)
- 50 issues: 300s → 38s (7.9x faster)
- 100 issues: 600s → 75s (8x faster)

### Smart Content Extraction

Automatically extracts from issue markdown:

```markdown
---
title: "Feature #41"
priority: high
---

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Implementation Plan
- [ ] Step 1
- [ ] Step 2
```

The processor will:
- ✅ Extract acceptance criteria
- ✅ Extract implementation plan
- ✅ Generate PR with checklists
- ✅ Set appropriate labels

### Auto-PR Generation

Creates complete PRs with:
- Smart branch naming: `issue/41-feature-title`
- PR body from issue description
- Pre-populated checklists
- Placeholder commit for immediate push

---

## 📊 Tool Comparison

| Feature | Basic | Orchestrator | **Enhanced** | Projects |
|---------|-------|--------------|--------------|----------|
| Parallel | ❌ | ❌ | ✅ **8x** | N/A |
| Auto-PR | ⚠️ | ⚠️ | ✅ **Smart** | ❌ |
| Phased | ❌ | ✅ | ⚠️ | ❌ |
| Projects | ❌ | ❌ | ❌ | ✅ |
| **Best For** | Simple | Structured | **Large** | PM |

---

## 🐛 Troubleshooting

### Common Issues

**Not authenticated:**
```bash
gh auth login
```

**PyYAML missing:**
```bash
pip install pyyaml
```

**Projects extension missing:**
```bash
gh extension install github/gh-project
```

**Rate limit exceeded:**
- Wait a few minutes
- Use fewer parallel workers
- Use personal access token

### Test Everything

```bash
./scripts/batch.sh test
```

---

## 📝 Issue File Template

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

## Implementation Plan
- [ ] Step 1
- [ ] Step 2

## Additional Context
Any additional information or references.
```

---

## 🎯 Best Practices

1. **Always preview first:**
   ```bash
   ./scripts/batch.sh preview
   ```

2. **Use parallel for large batches:**
   ```bash
   --parallel --workers 8
   ```

3. **Create PRs after validating issues:**
   ```bash
   ./scripts/batch.sh prs
   ```

4. **Sync to projects board:**
   ```bash
   ./scripts/batch.sh sync
   ```

5. **Generate reports:**
   ```bash
   ./scripts/batch.sh report > report.md
   ```

---

## 🔗 Resources

- **GitHub CLI:** https://cli.github.com/
- **GitHub Projects:** https://docs.github.com/en/issues/planning-and-tracking-with-projects
- **Full Documentation:** [../docs/](../docs/)

---

**Last Updated:** March 2026
