# Batch GitHub Issues - Quick Start Cheat Sheet

> **Get started in 5 minutes with batch issue and PR creation**

---

## ⚡ 1-Minute Setup

```bash
# 1. Install GitHub CLI
brew install gh  # macOS
# or visit: https://cli.github.com/

# 2. Authenticate
gh auth login

# 3. Install Python dependency
pip install pyyaml

# 4. Test (dry run)
python scripts/batch_github_issues.py dry-run
```

---

## 🎯 Most Common Commands

### Create Issues

```bash
# Preview what will be created
python scripts/batch_github_issues.py dry-run

# Create ALL issues from .github/ISSUES/
python scripts/batch_github_issues.py create-issues

# Create issues by priority
python scripts/batch_orchestrator.py phase critical  # Critical first
python scripts/batch_orchestrator.py phase high      # Then high
python scripts/batch_orchestrator.py phase medium    # Then medium
```

### Check Status

```bash
# Show all issues and PRs
python scripts/batch_github_issues.py status

# Show progress dashboard
python scripts/batch_orchestrator.py progress
```

### Create PRs

```bash
# Create PRs for all issues
python scripts/batch_github_issues.py create-prs

# Create PRs for specific issues
python scripts/batch_github_issues.py create-prs --numbers 1 2 3
```

---

## 📊 Typical Workflow

### Option A: All at Once

```bash
# 1. Preview
python scripts/batch_github_issues.py dry-run

# 2. Create all issues
python scripts/batch_github_issues.py create-issues

# 3. Check status
python scripts/batch_github_issues.py status

# 4. Create PRs
python scripts/batch_github_issues.py create-prs
```

### Option B: Phased Rollout (Recommended)

```bash
# Week 1: Critical Security
python scripts/batch_orchestrator.py phase critical
python scripts/batch_orchestrator.py progress

# Week 2-3: High Priority Code Quality
python scripts/batch_orchestrator.py phase high
python scripts/batch_orchestrator.py progress

# Week 4: Medium Priority Performance
python scripts/batch_orchestrator.py phase medium
python scripts/batch_orchestrator.py progress

# Generate final report
python scripts/batch_orchestrator.py report --output final_report.md
```

---

## 🔧 Command Reference

### Batch GitHub Issues Tool

| Command | What it does |
|---------|-------------|
| `dry-run` | Preview without creating |
| `create-issues` | Create all issues from markdown |
| `create-prs` | Create PRs for issues |
| `status` | Show issues and PRs status |

**Options:**
- `--dry-run` - Preview mode
- `--assignee username` - Assign to user
- `--numbers 1 2 3` - Specific issues
- `--repo /path` - Repository path

### Batch Orchestrator Tool

| Command | What it does |
|---------|-------------|
| `phase critical` | Create critical security issues |
| `phase high` | Create high priority issues |
| `phase medium` | Create medium priority issues |
| `phase all` | Create all issues |
| `progress` | Show progress dashboard |
| `report` | Generate detailed report |

**Options:**
- `--dry-run` - Preview mode
- `--verbose` - Detailed output
- `--output file.md` - Save report to file

---

## 📁 File Locations

```
.github/
├── ISSUES/                    # Issue markdown files
│   ├── QAQC-001-*.md         # Critical security
│   ├── QAQC-004-*.md         # High priority
│   └── QAQC-009-*.md         # Medium priority
├── batch_results.json         # Latest results
└── PR_TEMPLATES/              # Generated PR templates

scripts/
├── batch_github_issues.py     # Main tool
└── batch_orchestrator.py      # Orchestrator
```

---

## 🎨 Example Output

### Dry Run Preview

```
🔮 DRY RUN MODE - No changes will be made

======================================================================
🚀 BATCH ISSUE CREATION
======================================================================
Total issues to create: 11
Dry run: True
======================================================================

[1/11] Processing: QAQC-001-security-eval-replacement.md
----------------------------------------------------------------------
  📝 Creating issue: CRITICAL: Replace eval() calls...
    [DRY RUN] Would run: gh issue create --title ...

[2/11] Processing: QAQC-002-security-insecure-defaults.md
----------------------------------------------------------------------
  📝 Creating issue: CRITICAL: Implement secure random...
    [DRY RUN] Would run: gh issue create --title ...

======================================================================
📊 BATCH OPERATION SUMMARY
======================================================================
Total:    11
✅ Success: 11 (100.0%)
❌ Failed:  0 (0.0%)
======================================================================
```

### Status Check

```
======================================================================
📊 GITHUB ISSUES & PRS STATUS
======================================================================

Found 11 QA/QC issues:

🟢🔴 #1: CRITICAL: Replace eval() calls with json.loads()
   https://github.com/user/repo/issues/1
   Created: 2026-03-03

🟢🟡 #4: HIGH: Fix 50 undefined name errors
   https://github.com/user/repo/issues/4
   Created: 2026-03-03

Found 3 QA/QC PRs:

🟢 #5: Implement issue #4: Fix undefined names
   Branch: issue/4-fix-undefined-names
   https://github.com/user/repo/pull/5
======================================================================
```

---

## 🐛 Quick Troubleshooting

### "GitHub CLI not authenticated"

```bash
gh auth login
```

### "Not in a git repository"

```bash
cd /path/to/ArbitrageAI
git status
```

### "ModuleNotFoundError: No module named 'yaml'"

```bash
pip install pyyaml
```

### "Label does not exist"

```bash
# GitHub will auto-create on first use
# Or create manually:
gh label create security --color "#d73a4a"
```

---

## 📞 Need More Help?

- **Full Guide:** `docs/BATCH_GITHUB_ISSUES_GUIDE.md`
- **README:** `.github/README_BATCH_TOOLS.md`
- **Issues Index:** `.github/ISSUES/README.md`

---

## 💡 Pro Tips

1. **Always dry-run first** - Preview before creating
2. **Use phased rollout** - Start with critical issues
3. **Save results** - Check `.github/batch_results.json`
4. **Assign immediately** - Use `--assignee` flag
5. **Track progress** - Run `progress` command daily

---

**Quick Reference Card**

```
┌─────────────────────────────────────────────────────┐
│  BATCH GITHUB ISSUES - QUICK REFERENCE              │
├─────────────────────────────────────────────────────┤
│  python scripts/batch_github_issues.py dry-run      │
│  python scripts/batch_github_issues.py create-issues│
│  python scripts/batch_github_issues.py status       │
│  python scripts/batch_github_issues.py create-prs   │
├─────────────────────────────────────────────────────┤
│  python scripts/batch_orchestrator.py phase critical│
│  python scripts/batch_orchestrator.py phase high    │
│  python scripts/batch_orchestrator.py progress      │
│  python scripts/batch_orchestrator.py report        │
└─────────────────────────────────────────────────────┘
```

---

**Last Updated:** March 3, 2026  
**Version:** 1.0.0
