#!/usr/bin/env python3
"""
Script to create GitHub issues from QA/QC review findings.
Run from repository root: python scripts/create-qaqc-issues.py
"""

import subprocess
import json
from pathlib import Path

ISSUES = [
    {
        "title": "CRITICAL: Replace eval() calls with json.loads() - Remote Code Execution Risk",
        "labels": ["security", "critical", "bug"],
        "body": """# Security Vulnerability

## Description
The codebase contains **12 occurrences of eval()** which pose a critical Remote Code Execution (RCE) risk if LLM output is ever compromised.

## Affected Files
- `src/agent_execution/executor.py` (lines 569, 1045, 1335, 1844, 2105, 2821)
- `src/agent_execution/planning.py` (lines 607, 785, 1012, 1095)
- `src/utils/logging_alerting.py` (line 397)
- `src/agent_execution/market_scanner.py` (line 615)

## Current Code Example
```python
result_data = eval(log.text[json_start:json_end])
```

## Required Fix
Replace all `eval()` calls with safe alternatives:
```python
import json
result_data = json.loads(log.text[json_start:json_end])
```

Or for Python literals:
```python
import ast
result_data = ast.literal_eval(log.text[json_start:json_end])
```

## Security Impact
- **Severity:** CRITICAL
- **CVSS Score:** ~9.8 (Critical)
- **Attack Vector:** Network
- **Impact:** Complete system compromise

## Acceptance Criteria
- [ ] All 12 eval() calls replaced with json.loads() or ast.literal_eval()
- [ ] Tests added to verify JSON parsing works correctly
- [ ] Security scan passes
- [ ] Code review completed

## References
- CWE-95: Improper Neutralization of Directives in Dynamically Evaluated Code
- OWASP: Code Injection
"""
    },
    {
        "title": "CRITICAL: Dockerfile references non-existent requirements.txt",
        "labels": ["critical", "bug", "devops"],
        "body": """# Build Failure Risk

## Description
The production Dockerfile references `requirements.txt` which doesn't exist. The project uses `pyproject.toml` for dependency management, causing production builds to fail.

## Affected File
- `Dockerfile` (production build stage)

## Current Code
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
```

## Required Fix
Update Dockerfile to use pyproject.toml:
```dockerfile
COPY pyproject.toml .
RUN pip install --no-cache-dir --user -e .
```

Or generate requirements.txt from pyproject.toml using pip-tools.

## Impact
- **Severity:** CRITICAL
- **Production Impact:** Complete build failure
- **Deployment Risk:** Cannot deploy to production

## Acceptance Criteria
- [ ] Dockerfile updated to use pyproject.toml
- [ ] Docker build succeeds locally
- [ ] CI/CD pipeline builds Docker image successfully
- [ ] Production deployment verified

## Additional Notes
Consider adding `pip-tools` or similar for lockfile management if needed.
"""
    },
    {
        "title": "HIGH: Insecure default secrets in config - Authentication bypass risk",
        "labels": ["security", "high", "bug"],
        "body": """# Security Vulnerability

## Description
The application ships with insecure default secrets that could lead to authentication bypass if not changed in production.

## Affected Files
- `src/config/config_manager.py` (line 105)
- `src/utils/client_auth.py` (line 35)

## Current Code
```python
# config_manager.py
"JWT_SECRET_KEY": "CHANGE_ME_IN_PRODUCTION_generate_a_secure_random_32_byte_key"

# client_auth.py
CLIENT_AUTH_SECRET = os.environ.get(
    "CLIENT_AUTH_SECRET", "CHANGE_ME_IN_PRODUCTION_use_a_random_32_byte_key"
)
```

## Required Fix
1. Remove default values entirely
2. Add startup validation to fail if insecure defaults detected in production
3. Add documentation for secret generation

```python
# Example fix
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY and os.getenv("ENVIRONMENT") == "production":
    raise RuntimeError("JWT_SECRET_KEY must be set in production!")
```

## Security Impact
- **Severity:** HIGH
- **CVSS Score:** ~8.1 (High)
- **Attack Vector:** Network
- **Impact:** Authentication bypass, unauthorized access

## Acceptance Criteria
- [ ] Default secrets removed from code
- [ ] Startup validation added for production
- [ ] .env.example updated with secure generation instructions
- [ ] Documentation added for secret management
- [ ] Tests verify startup fails without secrets in production mode

## References
- CWE-798: Use of Hard-coded Credentials
- OWASP: Broken Authentication
"""
    },
    {
        "title": "HIGH: Add type checking enforcement with mypy",
        "labels": ["high", "enhancement", "code-quality"],
        "body": """# Code Quality Improvement

## Description
The codebase has no type checking enforcement configuration. While type hints are present in many places, there's no mypy or pyright configuration to enforce type safety.

## Current State
- ❌ No mypy configuration
- ❌ No pyright configuration
- ❌ No type checking in CI/CD
- ⚠️ Type hints present but not enforced

## Required Implementation

### 1. Add mypy configuration to pyproject.toml
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
strict_equality = true
```

### 2. Add mypy to CI/CD pipeline
```yaml
- name: Type checking
  run: mypy src/
```

### 3. Add mypy to dev dependencies
```toml
[tool.poetry.group.dev.dependencies]
mypy = "^1.0.0"
```

## Benefits
- Catch type errors before runtime
- Better IDE support
- Improved code documentation
- Reduced bugs in production

## Acceptance Criteria
- [ ] mypy configuration added to pyproject.toml
- [ ] mypy added to dev dependencies
- [ ] Type checking added to CI/CD pipeline
- [ ] Existing type errors documented or fixed
- [ ] Gradual rollout plan for strict mode

## Implementation Strategy
Consider starting with permissive settings and gradually increasing strictness as type errors are fixed.
"""
    },
    {
        "title": "HIGH: Consolidate duplicate configuration systems",
        "labels": ["high", "refactor", "tech-debt"],
        "body": """# Code Quality Improvement

## Description
The project has two coexisting configuration systems causing confusion, potential inconsistency, and maintenance burden.

## Affected Files
- `src/config/config_manager.py` (new, validated, preferred)
- `src/config/__init__.py` (legacy, 450+ lines, still in use)

## Current State
- New ConfigManager class with Pydantic validation exists
- Legacy config module still actively used throughout codebase
- No clear deprecation path
- Risk of configuration inconsistency

## Required Implementation

### Phase 1: Audit Usage
- [ ] Identify all imports of legacy config
- [ ] Map configuration usage across codebase
- [ ] Document differences between systems

### Phase 2: Migration
- [ ] Create migration guide
- [ ] Update imports to use ConfigManager
- [ ] Add deprecation warnings to legacy config
- [ ] Test all configuration-dependent features

### Phase 3: Cleanup
- [ ] Remove legacy config module
- [ ] Update documentation
- [ ] Add ConfigManager usage examples

## Acceptance Criteria
- [ ] All code uses ConfigManager exclusively
- [ ] Legacy config module removed
- [ ] Documentation updated
- [ ] All tests pass
- [ ] No configuration-related bugs introduced

## Risk Mitigation
- Gradual migration with deprecation warnings
- Comprehensive testing before removal
- Clear communication to team
"""
    },
    {
        "title": "HIGH: Add security scanning to CI/CD pipeline",
        "labels": ["security", "high", "devops", "enhancement"],
        "body": """# Security Improvement

## Description
The CI/CD pipeline lacks automated security scanning for dependencies, leaving the project vulnerable to known security issues in third-party packages.

## Current State
- ✅ Linting with Ruff
- ✅ Unit tests with pytest
- ✅ E2E tests
- ❌ No dependency security scanning
- ❌ No secret detection
- ❌ No SAST (Static Application Security Testing)

## Required Implementation

### 1. Add pip-audit for dependency scanning
```yaml
- name: Security scan dependencies
  run: |
    pip install pip-audit
    pip-audit -r pyproject.toml || true  # Start non-blocking
```

### 2. Add safety as alternative/backup
```yaml
- name: Safety check
  run: |
    pip install safety
    safety check -r pyproject.toml --full-report
```

### 3. Add secret detection (gitleaks or truffleHog)
```yaml
- name: Secret detection
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 4. Consider SAST tools
- Bandit (Python-specific)
- Semgrep
- CodeQL

## Acceptance Criteria
- [ ] Dependency security scanning added to CI
- [ ] Secret detection configured
- [ ] Security scan results visible in PRs
- [ ] Process defined for handling security alerts
- [ ] Documentation updated

## Recommended Tools
| Tool | Purpose | Integration |
|------|---------|-------------|
| pip-audit | Dependency vulnerabilities | CLI |
| safety | Dependency check | CLI/CI |
| gitleaks | Secret detection | GitHub Action |
| bandit | Python SAST | CLI |
| dependabot | Automated updates | GitHub native |

## Additional Recommendation
Enable GitHub Dependabot for automated security updates.
"""
    },
    {
        "title": "HIGH: Add LICENSE file to repository",
        "labels": ["high", "legal", "documentation"],
        "body": """# Legal Compliance

## Description
The repository is missing a LICENSE file, creating legal uncertainty for users and contributors.

## Current State
- ❌ No LICENSE file in repository root
- ❌ No license information in pyproject.toml
- ❌ No copyright notices in source files

## Required Implementation

### 1. Choose appropriate license
Consider:
- **MIT License** - Permissive, minimal restrictions
- **Apache 2.0** - Permissive with patent protection
- **GPL v3** - Copyleft, requires derivative works to be open source
- **Proprietary** - All rights reserved

### 2. Add LICENSE file
- Create LICENSE file in repository root
- Add copyright year and holder name
- Include full license text

### 3. Update pyproject.toml
```toml
[project]
license = { text = "MIT" }
# or
license = { file = "LICENSE" }
```

### 4. Add copyright notices (optional)
Add to source files:
```python
# Copyright (c) 2026 [Your Name/Organization]
# SPDX-License-Identifier: MIT
```

## Acceptance Criteria
- [ ] License chosen and documented
- [ ] LICENSE file added to repository root
- [ ] pyproject.toml updated with license info
- [ ] README updated with license badge
- [ ] Team/stakeholders approve license choice

## Resources
- [choosealicense.com](https://choosealicense.com/)
- [GitHub Licensing Guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
"""
    },
    {
        "title": "MEDIUM: Replace print() statements with logger throughout codebase",
        "labels": ["medium", "code-quality", "refactor"],
        "body": """# Code Quality Improvement

## Description
The codebase contains **337 print() statements** in production code, which should be replaced with proper logging calls.

## Affected Files (Examples)
- `src/utils/telemetry.py` (line 77)
- `src/distillation/dataset_manager.py` (lines 393-407)
- 50+ additional files

## Current Code Examples
```python
print(f"🔭 Phoenix Observability Dashboard running at: {session.url}")
print("Distillation Dataset Manager")
print("=" * 50)
```

## Required Fix
Replace with logger calls:
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Phoenix Observability Dashboard running at: {session.url}")
logger.info("Distillation Dataset Manager")
```

## Implementation Plan

### Phase 1: Setup
- [ ] Ensure logger is available in all modules
- [ ] Define logging standards/guidelines
- [ ] Create logging utility if needed

### Phase 2: Replacement
- [ ] Replace print() with logger.info() for informational messages
- [ ] Replace print() with logger.error() for errors
- [ ] Replace print() with logger.warning() for warnings
- [ ] Replace print() with logger.debug() for debug info

### Phase 3: Configuration
- [ ] Configure log levels per environment
- [ ] Add structured logging where beneficial
- [ ] Ensure logs integrate with observability stack

## Acceptance Criteria
- [ ] All 337 print() statements replaced
- [ ] Consistent logging patterns across codebase
- [ ] Log levels appropriate for message type
- [ ] Tests verify logging works correctly
- [ ] No print() in production code

## Benefits
- Better log management
- Integration with observability tools
- Configurable log levels
- Structured logging support
- Production debugging capability
"""
    },
    {
        "title": "MEDIUM: Fix bare except Exception blocks - 33 occurrences",
        "labels": ["medium", "code-quality", "error-handling"],
        "body": """# Code Quality Improvement

## Description
The codebase contains **33 bare `except Exception:` blocks** that hide errors and make debugging difficult.

## Affected Files (Examples)
- `src/agent_execution/executor.py` (line 577)
- `src/api/rate_limit_middleware.py` (line 51)
- 30+ additional occurrences

## Current Code Examples
```python
# executor.py:577
except Exception:
    pass

# rate_limit_middleware.py:51
except Exception:
    logger.warning("Redis not available. Using in-memory rate limiter.")
```

## Required Fix
Specify exception types and add proper error handling:
```python
# Better
except (RedisConnectionError, TimeoutError):
    logger.warning("Redis not available. Using in-memory rate limiter.")

# Even better with context
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

## Implementation Plan

### Phase 1: Audit
- [ ] List all 33 occurrences
- [ ] Categorize by context/purpose
- [ ] Identify appropriate exception types

### Phase 2: Fix
- [ ] Replace bare except with specific exceptions
- [ ] Add error logging with context
- [ ] Add tests for error scenarios

### Phase 3: Prevent
- [ ] Add ruff rule to prevent future bare excepts
- [ ] Add to code review checklist

## Acceptance Criteria
- [ ] All 33 bare except blocks fixed
- [ ] Specific exception types used
- [ ] Error context logged appropriately
- [ ] Tests cover error scenarios
- [ ] Ruff rule added to prevent recurrence

## Ruff Configuration
```toml
[tool.ruff.lint]
select = ["E722"]  # bare-except
```

## Benefits
- Better error visibility
- Easier debugging
- Proper error propagation
- Improved reliability
"""
    },
    {
        "title": "MEDIUM: Add coverage thresholds and improve test coverage",
        "labels": ["medium", "testing", "enhancement"],
        "body": """# Testing Improvement

## Description
The project lacks coverage thresholds in CI and has gaps in test coverage for critical components.

## Current State
- ✅ 99 E2E tests passing
- ✅ 50+ unit test files
- ❌ No coverage threshold enforcement
- ❌ No .coveragerc configuration
- ❌ Coverage only configured in CI workflow

## Coverage Gaps Identified

### Critical Areas Without Tests
1. **Template System** - `src/templates/` (financial_summary.py, legal_contract.py, base_document.py)
2. **Fine-tuning CLI** - `src/fine_tuning/cli.py`
3. **Distillation modules** - Limited coverage
4. **Background job queue** - No dedicated tests
5. **Experience vector DB** - Only basic tests

## Required Implementation

### 1. Add coverage configuration
```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/migrations/*"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80
show_missing = true
```

### 2. Update CI to enforce coverage
```yaml
- name: Run tests with coverage
  run: pytest --cov=src --cov-fail-under=80 --cov-report=xml
```

### 3. Add coverage badge to README
```markdown
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/.../coverage.json)](...)
```

## Acceptance Criteria
- [ ] Coverage configuration added to pyproject.toml
- [ ] 80% coverage threshold enforced in CI
- [ ] Template system tests added
- [ ] Fine-tuning CLI tests added
- [ ] Background job queue tests added
- [ ] Coverage badge added to README
- [ ] Coverage reports generated

## Implementation Priority
1. Add coverage configuration (immediate)
2. Enforce threshold in CI (immediate)
3. Add tests for critical gaps (iterative)
4. Increase threshold to 90% (future goal)
"""
    },
    {
        "title": "MEDIUM: Add missing standard documentation files",
        "labels": ["medium", "documentation"],
        "body": """# Documentation Improvement

## Description
The repository is missing several standard documentation files expected in open source projects.

## Missing Files
- ❌ CONTRIBUTING.md - Contribution guidelines
- ❌ CHANGELOG.md - Version history and changes
- ❌ SECURITY.md - Security policy and reporting
- ❌ CODE_OF_CONDUCT.md - Community guidelines
- ❌ SUPPORT.md - Support channels and help

## Required Implementation

### 1. CONTRIBUTING.md
Should include:
- How to set up development environment
- How to run tests
- Code style guidelines
- Pull request process
- Issue reporting guidelines
- Branch naming conventions

### 2. CHANGELOG.md
Should follow [Keep a Changelog](https://keepachangelog.com/) format:
```markdown
# Changelog

## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [1.0.0] - 2026-03-02
```

### 3. SECURITY.md
Should include:
- How to report security vulnerabilities
- Security response process
- Supported versions
- Security contact information

### 4. CODE_OF_CONDUCT.md
Consider using [Contributor Covenant](https://www.contributor-covenant.org/)

### 5. SUPPORT.md
Should include:
- Where to get help
- Issue tracker usage
- Community channels
- Commercial support options

## Acceptance Criteria
- [ ] CONTRIBUTING.md created
- [ ] CHANGELOG.md created with initial version
- [ ] SECURITY.md created with reporting process
- [ ] CODE_OF_CONDUCT.md adopted
- [ ] SUPPORT.md created
- [ ] Links added to README
- [ ] Issue templates updated

## Templates
GitHub provides templates for these files that can be customized.
"""
    },
    {
        "title": "MEDIUM: Add .dockerignore file to reduce image size and improve security",
        "labels": ["medium", "devops", "docker"],
        "body": """# DevOps Improvement

## Description
The repository is missing a .dockerignore file, resulting in larger image sizes and potential security risks from including unnecessary files.

## Current State
- ✅ Dockerfile with multi-stage builds
- ✅ docker-compose.yml for development
- ✅ docker-compose.prod.yml for production
- ❌ No .dockerignore file

## Impact
- Larger Docker images (includes all files)
- Slower build times
- Potential security risks (secrets, local files)
- Unnecessary cache invalidation

## Required Implementation

### Create .dockerignore file
```
# Git
.git
.gitignore
.github

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
*.egg-info
.eggs

# Virtual environments
venv/
.venv/
ENV/
env/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.tox/

# Documentation
*.md
docs/
!README.md

# Misc
.DS_Store
Thumbs.db
*.log
logs/
data/*.db
tmp/
temp/

# Frontend
src/client_portal/node_modules/
src/client_portal/dist/

# Build artifacts
build/
dist/
*.egg

# Local config
.env.local
.env.*.local
secrets/
credentials/
*.key
*.pem
*.crt
```

## Acceptance Criteria
- [ ] .dockerignore file created
- [ ] Docker image size reduced
- [ ] Build time improved
- [ ] No sensitive files in image
- [ ] Dockerfile tested after changes

## Benefits
- Smaller image size (faster pulls/deployments)
- Faster builds (better caching)
- Improved security (no secrets in image)
- Cleaner images (no unnecessary files)
"""
    },
    {
        "title": "MEDIUM: Improve .gitignore to prevent accidental commits",
        "labels": ["medium", "repository", "maintenance"],
        "body": """# Repository Maintenance

## Description
The current .gitignore is missing several important patterns, risking accidental commits of generated files, caches, and sensitive data.

## Current .gitignore Status
✅ Present but incomplete

## Missing Patterns

### Python/Caching
- `*.pyc` (individual .pyc files)
- `.pytest_cache/`
- `.ruff_cache/`
- `.coverage`
- `htmlcov/`
- `.mypy_cache/`
- `*.egg`

### OS Files
- `.DS_Store` (macOS)
- `Thumbs.db` (Windows)
- `*.swp`, `*.swo` (Vim)

### Environment Files
- `.env.*` (all env variants)
- `.env.local`
- `.env.*.local`

### Security/Certificates
- `*.key`
- `*.pem`
- `*.crt`
- `secrets/`
- `credentials/`

### Logs/Data
- `logs/*.log`
- `data/*.db` (specific patterns)
- `*.sqlite`

### Build Artifacts
- `*.egg-info/`
- `build/`
- `dist/`

## Required Implementation

### Update .gitignore
Add all missing patterns in organized sections:
```
# Python
*.pyc
*.egg
*.egg-info/

# Caches
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Coverage
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db

# Security
*.key
*.pem
*.crt
secrets/
credentials/

# Environment
.env.*
.env.local

# Logs
logs/*.log
```

## Acceptance Criteria
- [ ] .gitignore updated with all missing patterns
- [ ] Existing tracked files that should be ignored removed from git
- [ ] Team notified of changes
- [ ] No accidental commits of ignored files

## Cleanup Existing Files
```bash
git rm -r --cached .pytest_cache
git rm -r --cached .ruff_cache
git rm --cached .coverage
# etc.
```
"""
    },
    {
        "title": "MEDIUM: Add pre-commit hooks for code quality",
        "labels": ["medium", "code-quality", "tooling"],
        "body": """# Code Quality Improvement

## Description
The project lacks pre-commit hooks to enforce code quality standards before commits are made.

## Current State
- ✅ Ruff configured for linting
- ✅ Tests run in CI
- ❌ No pre-commit hooks
- ❌ Issues caught late in CI instead of locally

## Required Implementation

### 1. Add pre-commit configuration
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
          - types-PyYAML
        exclude: ^tests/

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        files: ^src/client_portal/
```

### 2. Add to dev dependencies
```toml
[tool.poetry.group.dev.dependencies]
pre-commit = "^3.6.0"
```

### 3. Update documentation
Add to CONTRIBUTING.md:
```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Acceptance Criteria
- [ ] .pre-commit-config.yaml created
- [ ] pre-commit added to dev dependencies
- [ ] Installation instructions in CONTRIBUTING.md
- [ ] Team members install hooks
- [ ] CI verifies pre-commit passes

## Benefits
- Catch issues before commit
- Consistent code style
- Faster CI feedback
- Reduced review burden
"""
    },
    {
        "title": "MEDIUM: Complete unimplemented TODO features in websocket_manager.py",
        "labels": ["medium", "tech-debt", "websocket"],
        "body": """# Technical Debt

## Description
There are 4 TODO comments in websocket_manager.py (lines 750-774) for unimplemented features that should be completed or removed.

## Affected File
- `src/api/websocket_manager.py` (lines 750-774)

## Current TODOs
The file contains unimplemented features marked with TODO comments. These should either be:
1. Implemented if still needed
2. Removed if no longer relevant
3. Converted to GitHub issues if blocked

## Required Implementation

### Phase 1: Audit
- [ ] Review each TODO comment
- [ ] Determine if feature is still needed
- [ ] Check if blocked by dependencies
- [ ] Consult product requirements

### Phase 2: Action
For each TODO:
- **If needed:** Create implementation plan and timeline
- **If not needed:** Remove TODO and clean up related code
- **If blocked:** Create GitHub issue with dependencies

### Phase 3: Prevention
- [ ] Add policy for TODO comments
- [ ] Set expiration dates on new TODOs
- [ ] Regular TODO cleanup in sprints

## Acceptance Criteria
- [ ] All 4 TODOs in websocket_manager.py addressed
- [ ] Related features implemented or removed
- [ ] No orphaned TODO comments
- [ ] Documentation updated if features changed

## Best Practices for TODOs
```python
# TODO(username, YYYY-MM-DD): Description
# Issue: #123
# Reason: Why this is needed
```

## Alternative Approaches
- Use GitHub Issues for tracking instead of TODO comments
- Set calendar reminders for TODO cleanup
- Include TODO review in code review checklist
"""
    },
    {
        "title": "MEDIUM: Rename test files to follow consistent naming convention",
        "labels": ["medium", "testing", "convention"],
        "body": """# Testing Improvement

## Description
Some test files don't follow the standard `test_*.py` naming convention, causing confusion and potential discovery issues.

## Affected Files
- `tests/verify_issue_1.py` - should be `test_verify_issue_1.py` or integrated into existing tests
- `tests/reproduce_issue_34.py` - should be `test_reproduce_issue_34.py` or integrated
- Potentially other non-standard names

## Current State
- ✅ Most files follow `test_*.py` pattern
- ❌ Some files use different naming
- ⚠️ pytest may not discover non-standard names automatically

## Required Implementation

### Phase 1: Audit
- [ ] List all test files
- [ ] Identify non-standard names
- [ ] Determine purpose of each file

### Phase 2: Rename/Integrate
For each non-standard file:
- **If still relevant:** Rename to `test_*.py`
- **If temporary debugging:** Integrate into proper tests and delete
- **If obsolete:** Delete file

### Phase 3: Prevent
- [ ] Add naming convention to CONTRIBUTING.md
- [ ] Configure pytest to only discover standard names
- [ ] Add to code review checklist

## Acceptance Criteria
- [ ] All test files follow `test_*.py` pattern
- [ ] pytest discovers all tests correctly
- [ ] Temporary debug files removed
- [ ] Naming convention documented

## pytest Configuration
```toml
[tool.pytest.ini_options]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Benefits
- Consistent codebase
- Reliable test discovery
- Easier navigation
- Clear intent
"""
    },
    {
        "title": "LOW: Enhance ruff configuration for better code consistency",
        "labels": ["low", "code-quality", "linting"],
        "body": """# Code Quality Improvement

## Description
The current ruff configuration is minimal, only excluding the `.agents/` directory. Enhanced configuration would improve code consistency.

## Current Configuration
```toml
[tool.ruff]
exclude = [".agents/"]
```

## Missing Configuration
- ❌ No line length setting
- ❌ No rule selection
- ❌ No strictness levels
- ❌ No format configuration
- ❌ No per-file-ignores

## Required Implementation

### Enhanced ruff Configuration
```toml
[tool.ruff]
line-length = 88
target-version = "py310"
exclude = [
    ".agents/",
    ".git/",
    ".venv/",
    "__pycache__/",
]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "N",   # pep8-naming
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # unused imports OK in __init__
"tests/*" = ["S101"]      # assert allowed in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

## Acceptance Criteria
- [ ] Enhanced ruff configuration added
- [ ] Configuration tested on codebase
- [ ] Auto-fix applied where possible
- [ ] Team agrees on rules
- [ ] Documentation updated

## Implementation Steps
1. Add configuration to pyproject.toml
2. Run `ruff check --fix`
3. Run `ruff format`
4. Review and adjust rules as needed
5. Add to CI/CD pipeline
"""
    },
    {
        "title": "LOW: Add API versioning strategy",
        "labels": ["low", "architecture", "api"],
        "body": """# Architecture Improvement

## Description
The API lacks versioning, which will make future breaking changes difficult and risk breaking existing clients.

## Current State
- ✅ FastAPI application with auto-generated docs
- ✅ Multiple endpoints implemented
- ❌ No API versioning
- ❌ No versioning strategy documented

## Required Implementation

### Option 1: URL Path Versioning (Recommended)
```python
# Structure
/api/v1/tasks
/api/v1/agents
/api/v2/tasks  # future version

# Implementation
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")
v2_router = APIRouter(prefix="/api/v2")
```

### Option 2: Header Versioning
```python
# Clients send: API-Version: 1.0
# Implementation via middleware
```

### Option 3: Query Parameter Versioning
```
/api/tasks?version=1.0
```

## Implementation Plan

### Phase 1: Strategy
- [ ] Choose versioning approach (recommend URL path)
- [ ] Document versioning policy
- [ ] Define deprecation timeline

### Phase 2: Implementation
- [ ] Add version prefix to all routes
- [ ] Update OpenAPI documentation
- [ ] Update client portal
- [ ] Update tests

### Phase 3: Documentation
- [ ] Add versioning to API docs
- [ ] Document migration path
- [ ] Add deprecation warnings

## Acceptance Criteria
- [ ] Versioning strategy chosen and documented
- [ ] All routes versioned
- [ ] OpenAPI docs reflect versioning
- [ ] Tests updated
- [ ] Client portal updated

## Best Practices
- Support at least 2 versions simultaneously
- 6-month deprecation notice minimum
- Clear migration guides
- Version in URL path for discoverability
"""
    },
    {
        "title": "LOW: Consider migrating client portal to TypeScript",
        "labels": ["low", "enhancement", "frontend", "typescript"],
        "body": """# Enhancement

## Description
The client portal uses JavaScript (React 19) instead of TypeScript, missing out on type safety benefits.

## Current State
- ✅ React 19 with Vite
- ✅ ESLint configured
- ✅ Vitest for testing
- ❌ No TypeScript
- ❌ No tsconfig.json
- ⚠️ Type safety only via PropTypes or JSDoc (if used)

## Benefits of TypeScript
- Compile-time type checking
- Better IDE autocomplete
- Refactoring safety
- Self-documenting code
- Fewer runtime errors

## Migration Approaches

### Option 1: Gradual Migration (Recommended)
1. Add TypeScript configuration
2. Enable `allowJs: true`
3. Convert files one by one (starting with utilities)
4. Add type definitions for existing JS
5. Switch to `allowJs: false` when complete

### Option 2: Big Bang
1. Rename all .js/.jsx to .ts/.tsx
2. Fix all type errors
3. Complete in one sprint

### Option 3: Stay with JavaScript
1. Add JSDoc type annotations
2. Configure TypeScript to check JS files
3. Get some type safety without migration

## Required Implementation (if migrating)

### 1. Add TypeScript config
```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "allowJs": true  // Start true, false when complete
  },
  "include": ["src"]
}
```

### 2. Update dependencies
```json
{
  "devDependencies": {
    "typescript": "^5.3.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0"
  }
}
```

## Acceptance Criteria (if proceeding)
- [ ] TypeScript configuration added
- [ ] Migration approach chosen
- [ ] Team trained on TypeScript
- [ ] Migration completed or decision documented
- [ ] Type definitions for external libraries

## Recommendation
Start with JSDoc type annotations in JavaScript files to get incremental benefits, then evaluate full migration.
"""
    },
    {
        "title": "LOW: Improve client portal README with project-specific documentation",
        "labels": ["low", "documentation", "frontend"],
        "body": """# Documentation Improvement

## Description
The client portal README contains only the default Vite template text, lacking project-specific documentation for developers.

## Current File
- `src/client_portal/README.md` - Default Vite template

## Current State
```markdown
# Vite + React
This is a Vite project with React...
[Default Vite template content]
```

## Missing Information
- ❌ Project overview
- ❌ Feature documentation
- ❌ Component structure
- ❌ State management explanation
- ❌ API integration details
- ❌ Development workflow
- ❌ Deployment instructions

## Required Content

### Project Overview
- What is the client portal?
- Key features
- Target users

### Architecture
- Component hierarchy
- State management (Redux? Context? Zustand?)
- API communication pattern
- Authentication flow

### Development
- How to run locally
- Environment variables needed
- Common development tasks
- Testing instructions

### Component Documentation
- Major components and their purposes
- Reusable component library
- Design system usage

### Deployment
- Build process
- Deployment targets
- Environment-specific configuration

## Template
```markdown
# Client Portal

ArbitrageAI Client Portal - React-based dashboard for clients to monitor arbitrage agents and tasks.

## Features
- Real-time task monitoring
- Agent performance metrics
- Financial reporting
- Configuration management

## Quick Start
```bash
npm install
npm run dev
```

## Environment Variables
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## Project Structure
```
src/
├── components/    # Reusable components
├── pages/         # Page components
├── hooks/         # Custom hooks
├── stores/        # State management
├── api/           # API client
└── utils/         # Utilities
```

## Testing
```bash
npm run test
```

## Deployment
```bash
npm run build
```
```

## Acceptance Criteria
- [ ] README rewritten with project-specific content
- [ ] Development instructions included
- [ ] Architecture documented
- [ ] Component structure explained
- [ ] Deployment instructions added
"""
    },
    {
        "title": "LOW: Consolidate excessive documentation files into organized structure",
        "labels": ["low", "documentation", "organization"],
        "body": """# Documentation Improvement

## Description
The repository contains 50+ ISSUE_*_*.md implementation summary files, making navigation difficult. These should be consolidated into a more organized structure.

## Current State
- ✅ Extensive documentation (50+ files)
- ✅ Implementation summaries for many issues
- ❌ Difficult to navigate
- ❌ Redundant information
- ❌ No organization structure

## Files to Consolidate
Examples:
- `ISSUE_17_18_IMPLEMENTATION_SUMMARY.md`
- `ISSUE_20_IMPLEMENTATION.md`
- `ISSUE_22_23_24_IMPLEMENTATION.md`
- `COMPLETION_SUMMARY_BATCH_3_ISSUES_7_13_26_27_28.md`
- `COMPLETION_SUMMARY_ISSUES_29-33.md`
- `COMPLETION_SUMMARY_ISSUES_36-40.md`
- `COMPLETION_SUMMARY_ISSUES_41-45.md`
- `IMPLEMENTATION_COMPLETE_ISSUES_17-21.md`
- `IMPLEMENTATION_COMPLETE.md`
- `IMPLEMENTATION_SUMMARY_ALL_ISSUES.md`
- `EXHAUSTIVE_REVIEW_SUMMARY.md`
- 40+ similar files

## Required Implementation

### Option 1: Documentation Site (Recommended)
Use a documentation generator:
- **MkDocs** with Material theme
- **Docusaurus**
- **GitBook**
- **GitHub Wiki**

Structure:
```
docs/
├── index.md
├── getting-started/
├── architecture/
├── api-reference/
├── development/
├── deployment/
└── changelog/
```

### Option 2: Organized Directory Structure
```
docs/
├── README.md (documentation index)
├── architecture/
│   ├── overview.md
│   └── comparisons.md
├── development/
│   ├── setup.md
│   └── guides/
├── implementation/
│   ├── batch-1-issues.md (consolidated)
│   ├── batch-2-issues.md (consolidated)
│   └── releases/
└── operations/
    ├── deployment.md
    └── monitoring.md
```

### Option 3: Keep Individual Files, Add Index
- Create comprehensive index with links
- Add tags/categories to files
- Implement search functionality

## Acceptance Criteria
- [ ] Consolidation approach chosen
- [ ] Documentation structure designed
- [ ] Files reorganized
- [ ] Navigation improved
- [ ] Search implemented (if applicable)
- [ ] Old files archived or deleted

## Recommendation
Use MkDocs with Material theme for:
- Easy maintenance
- GitHub Pages deployment
- Search functionality
- Professional appearance
- Version support
"""
    },
    {
        "title": "LOW: Add security headers middleware to FastAPI application",
        "labels": ["low", "security", "enhancement"],
        "body": """# Security Enhancement

## Description
The FastAPI application lacks security headers middleware, leaving it vulnerable to common web attacks.

## Current State
- ✅ FastAPI application
- ✅ Basic CORS configuration
- ❌ No security headers middleware
- ❌ No HTTPS enforcement
- ❌ No HSTS
- ❌ No CSP
- ❌ No X-Frame-Options

## Required Security Headers

### Essential Headers
1. **Strict-Transport-Security (HSTS)**
   - Enforces HTTPS
   - Prevents protocol downgrade attacks

2. **Content-Security-Policy (CSP)**
   - Prevents XSS attacks
   - Controls resource loading

3. **X-Frame-Options**
   - Prevents clickjacking
   - Controls iframe embedding

4. **X-Content-Type-Options**
   - Prevents MIME sniffing

5. **X-XSS-Protection**
   - Legacy XSS protection

6. **Referrer-Policy**
   - Controls referrer information

## Implementation

### Create Security Middleware
```python
# src/api/security_middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # HSTS
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        
        # CSP
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        
        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"
        
        # MIME sniffing prevention
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

# Add to main.py
app.add_middleware(SecurityHeadersMiddleware)
```

## Acceptance Criteria
- [ ] Security headers middleware created
- [ ] Middleware added to application
- [ ] Headers verified in responses
- [ ] CSP tested with application functionality
- [ ] Documentation updated
- [ ] Security scan passes

## Testing
Use security scanning tools:
```bash
# Check headers
curl -I https://your-api.com

# Use security scanner
npx security-headers-check https://your-api.com
```

## Resources
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [SecurityHeaders.com](https://securityheaders.com/)
"""
    },
]


def create_issue(issue_data):
    """Create a single GitHub issue."""
    title = issue_data["title"]
    body = issue_data["body"]
    labels = ",".join(issue_data["labels"])

    cmd = [
        "gh",
        "issue",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--label",
        labels,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Created: {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {title}")
        print(f"   Error: {e.stderr}")
        return False


def main():
    """Create all issues."""
    print("Creating GitHub issues from QA/QC review...\n")

    # First, try to create labels if they don't exist
    all_labels = set()
    for issue in ISSUES:
        all_labels.update(issue["labels"])

    print("Ensuring labels exist...")
    for label in sorted(all_labels):
        cmd = ["gh", "label", "create", label, "--force"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=False)
        except (subprocess.SubprocessError, OSError):
            pass  # Ignore errors creating labels

    print("\nCreating issues...\n")
    success_count = 0
    fail_count = 0

    for issue in ISSUES:
        if create_issue(issue):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} created, {fail_count} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
