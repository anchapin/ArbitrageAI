# Pre-commit Hooks Guide

**Issue #141**: Add pre-commit hooks for code quality
**Status**: ✅ **COMPLETE**
**Last Updated**: March 2, 2026

---

## Overview

Pre-commit hooks are automated checks that run before each commit to ensure code quality, security, and consistency. They catch issues early and prevent problematic code from entering the codebase.

---

## Quick Start

### Installation

```bash
# Run the setup script (recommended)
python scripts/setup_precommit.py

# Or manually install
pip install pre-commit
pre-commit install
```

### Usage

```bash
# Run on staged files (automatic on commit)
pre-commit run

# Run on all files
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate

# Run specific hook
pre-commit run ruff

# Skip pre-commit (not recommended)
git commit -m "message" --no-verify
```

---

## Installed Hooks

### Python Code Quality

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **ruff** | Fast Python linter (replaces flake8, isort, pyupgrade) | ✅ Yes |
| **ruff-format** | Code formatter | ✅ Yes |
| **mypy** | Static type checker | ❌ No |
| **flake8** | Additional security checks | ❌ No |
| **python-compile** | Syntax validation | ❌ No |

### Security Scanning

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **bandit** | Python security linter | ❌ No |
| **detect-secrets** | Detect secrets and credentials | ❌ No |
| **detect-private-key** | Detect private keys | ❌ No |

### Code Formatting

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **prettier** | Format JSON, YAML, Markdown, etc. | ✅ Yes |
| **trailing-whitespace** | Remove trailing whitespace | ✅ Yes |
| **end-of-file-fixer** | Ensure files end with newline | ✅ Yes |
| **mixed-line-ending** | Normalize line endings to LF | ✅ Yes |

### Git & File Checks

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **check-merge-conflict** | Detect merge conflict markers | ❌ No |
| **check-added-large-files** | Prevent large files (>10MB) | ❌ No |
| **check-case-conflict** | Detect case sensitivity issues | ❌ No |
| **check-json** | Validate JSON syntax | ❌ No |
| **check-yaml** | Validate YAML syntax | ❌ No |
| **check-toml** | Validate TOML syntax | ❌ No |
| **check-xml** | Validate XML syntax | ❌ No |
| **check-executables-have-shebangs** | Verify shebangs in executables | ❌ No |
| **no-commit-to-branch** | Prevent commits to protected branches | ❌ No |

### Docker & Documentation

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **hadolint** | Dockerfile linter | ❌ No |
| **markdownlint** | Markdown linter | ❌ No |

### Shell Scripts

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **shellcheck** | Shell script linter | ❌ No |

### Testing

| Hook | Description | Auto-fix |
|------|-------------|----------|
| **pytest-fast** | Run fast test subset | ❌ No |
| **name-tests-test** | Ensure test file naming | ❌ No |

---

## Configuration

Pre-commit configuration is stored in `.pre-commit-config.yaml`.

### Example Configuration

```yaml
repos:
  # Ruff - Fast Python linter
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.14
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # mypy - Type checker
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports, --disallow-untyped-defs]

  # Bandit - Security scanner
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.7
    hooks:
      - id: bandit
        args: [-r, -ll]
```

---

## Commit Message Format

Pre-commit includes a commit-msg hook that encourages **Conventional Commits**:

### Format

```
type(scope): description

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting) |
| `refactor` | Code refactoring |
| `perf` | Performance improvements |
| `test` | Test additions/modifications |
| `build` | Build system changes |
| `ci` | CI/CD changes |
| `chore` | Maintenance tasks |
| `revert` | Revert previous commit |

### Examples

```bash
feat(api): add security headers middleware
fix: resolve memory leak in executor
docs: update README with setup instructions
refactor(auth): simplify JWT token validation
test: add integration tests for delivery endpoint
chore: update dependencies
```

---

## Troubleshooting

### Hook Fails on Commit

**Problem**: Pre-commit hook fails when trying to commit.

**Solution**:
1. Read the error message carefully
2. Fix the reported issues
3. Stage the fixes: `git add <files>`
4. Commit again: `git commit -m "message"`

### Hook Takes Too Long

**Problem**: Pre-commit checks are slow.

**Solution**:
```bash
# Skip slow hooks temporarily
SKIP=pytest-fast,mypy git commit -m "message"

# Or run only fast hooks
pre-commit run --hook-stage pre-commit
```

### False Positive

**Problem**: Hook reports an issue that's not actually a problem.

**Solution**:
1. Check if the hook can be configured to ignore the issue
2. Add file/directory to hook's `exclude` pattern
3. As last resort, use `# noqa` or `# fmt: off` comments

### Need to Bypass Hook

**Problem**: Need to commit despite hook failures.

**Solution** (use sparingly):
```bash
# Skip all hooks
git commit -m "message" --no-verify

# Skip specific hook
SKIP=ruff git commit -m "message"
```

---

## Best Practices

### ✅ Do

- Run `pre-commit run --all-files` after setup to catch existing issues
- Fix issues immediately when pre-commit fails
- Keep pre-commit configuration up to date: `pre-commit autoupdate`
- Use auto-fix hooks: `ruff --fix`
- Run hooks locally before pushing

### ❌ Don't

- Don't use `--no-verify` regularly
- Don't disable hooks without good reason
- Don't commit directly to protected branches
- Don't ignore pre-commit failures

---

## Advanced Usage

### Custom Hook Stages

```yaml
# Run on pre-commit (before each commit)
stages: [pre-commit]

# Run on pre-push (before push)
stages: [pre-push]

# Run on manual (only when explicitly run)
stages: [manual]

# Run on commit-msg (validate commit message)
stages: [commit-msg]
```

### Local Hooks

Create custom local hooks:

```yaml
- repo: local
  hooks:
    - id: custom-check
      name: Custom Check
      entry: python scripts/custom_check.py
      language: system
      types: [python]
      pass_filenames: true
```

### Conditional Hooks

Run hooks only on specific files:

```yaml
- id: ruff
  files: ^src/
  exclude: ^src/client_portal/

- id: prettier
  files: ^src/client_portal/
  types_or: [javascript, typescript, css]
```

---

## Performance Optimization

### Speed Up Pre-commit

1. **Use `require_serial: false`** for parallel execution
2. **Exclude large directories** from hooks
3. **Use `stages`** to run heavy hooks only on push
4. **Cache results** where possible

### CI/CD Integration

Pre-commit automatically runs in CI/CD:

```yaml
# .github/workflows/ci.yml
- name: Run pre-commit
  uses: pre-commit/action@v3.0.0
```

---

## Maintenance

### Update Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Update specific repo
pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit

# Freeze versions
pre-commit autoupdate --freeze
```

### Remove Hooks

```bash
# Uninstall hooks
pre-commit uninstall

# Remove hook from config
# Edit .pre-commit-config.yaml and remove the hook
```

### Debug Hooks

```bash
# See what files a hook will run on
pre-commit run --hook-stage pre-commit --verbose

# Run hook with debug output
pre-commit run --hook-stage pre-commit --show-diff-on-failure
```

---

## Related Documentation

- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution guidelines
- [AGENTS.md](./AGENTS.md) - Coding standards
- [SECURITY.md](./SECURITY.md) - Security policies
- [pyproject.toml](./pyproject.toml) - Project configuration

---

## Support

For issues or questions:
1. Check [CONTRIBUTING.md](./CONTRIBUTING.md)
2. Review hook documentation: `pre-commit --help`
3. See pre-commit official docs: https://pre-commit.com

---

**Maintained by**: ArbitrageAI Team
**License**: MIT
