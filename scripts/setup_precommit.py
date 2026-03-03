#!/usr/bin/env python3
"""
Pre-commit Setup Script for ArbitrageAI

Issue #141: Add pre-commit hooks for code quality

This script automates the installation and configuration of pre-commit hooks.

Usage:
    python scripts/setup_precommit.py

Requirements:
    - Python 3.10+
    - pip install pre-commit

What this script does:
    1. Checks if pre-commit is installed
    2. Installs pre-commit if needed
    3. Installs git hooks
    4. Runs initial validation
    5. Provides setup instructions
"""

import subprocess
import sys
import os
from pathlib import Path


def print_header(text: str):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70 + "\n")


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"⚠️  {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


def check_python_version():
    """Check if Python version is 3.10+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(f"Python 3.10+ required, found {version.major}.{version.minor}")
        return False
    print_success(f"Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def check_precommit_installed():
    """Check if pre-commit is installed."""
    try:
        result = subprocess.run(
            ["pre-commit", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success(f"pre-commit installed: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning("pre-commit is not installed")
        return False


def install_precommit():
    """Install pre-commit."""
    print_info("Installing pre-commit...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pre-commit"],
            check=True,
            capture_output=True,
            text=True
        )
        print_success("pre-commit installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install pre-commit: {e}")
        return False


def check_git_repo():
    """Check if running in a git repository."""
    git_dir = Path(".git")
    if not git_dir.exists():
        print_error("Not a git repository. Please initialize git first.")
        return False
    print_success("Git repository detected")
    return True


def install_git_hooks():
    """Install git hooks."""
    print_info("Installing git hooks...")
    try:
        result = subprocess.run(
            ["pre-commit", "install"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success("Git hooks installed")
        print_info(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install git hooks: {e.stderr}")
        return False


def install_commit_msg_hook():
    """Install commit-msg hook for commit message validation."""
    print_info("Installing commit-msg hook...")
    
    hook_content = r'''#!/bin/bash
# Commit message validation hook

# Check if commit message follows conventional commit format
commit_msg_file="$1"
commit_msg=$(cat "$commit_msg_file")

# Skip merge commits
if echo "$commit_msg" | grep -q "^Merge"; then
    exit 0
fi

# Check for conventional commit format
# Format: type(scope): description OR type: description
if ! echo "$commit_msg" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9-]+\))?: .+"; then
    echo "⚠️  Commit message should follow conventional commit format"
    echo "   Example: feat(api): add security headers middleware"
    echo "   Example: fix: resolve memory leak in executor"
    echo ""
    echo "Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert"
    echo ""
    echo "Proceeding anyway (commit message format is optional)"
fi

exit 0
'''
    
    git_hooks_dir = Path(".git/hooks")
    git_hooks_dir.mkdir(exist_ok=True)
    
    hook_file = git_hooks_dir / "commit-msg"
    with open(hook_file, "w") as f:
        f.write(hook_content)
    
    # Make executable
    hook_file.chmod(0o755)
    
    print_success("Commit-msg hook installed")
    return True


def validate_config():
    """Validate pre-commit configuration."""
    print_info("Validating pre-commit configuration...")
    try:
        result = subprocess.run(
            ["pre-commit", "validate-config"],
            capture_output=True,
            text=True,
            check=True
        )
        print_success("Configuration is valid")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Configuration validation failed: {e.stderr}")
        return False


def run_initial_check():
    """Run initial pre-commit check on all files."""
    print_info("Running initial check on all files (this may take a while)...")
    try:
        result = subprocess.run(
            ["pre-commit", "run", "--all-files"],
            capture_output=True,
            text=True,
            check=False  # Don't fail on linting issues
        )
        print_info("Initial check completed")
        if result.returncode == 0:
            print_success("All checks passed!")
        else:
            print_warning("Some checks found issues (this is normal for first run)")
            print_info("Fix the issues and commit again")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Initial check failed: {e.stderr}")
        return False


def check_required_tools():
    """Check if required tools are installed."""
    print_info("Checking required tools...")
    
    required_tools = [
        "ruff",
        "mypy",
        "bandit",
        "pytest",
        "black",
        "flake8",
    ]
    
    missing_tools = []
    for tool in required_tools:
        try:
            subprocess.run(
                [tool, "--version"],
                capture_output=True,
                check=True
            )
            print_success(f"{tool} is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_warning(f"{tool} is not installed")
            missing_tools.append(tool)
    
    if missing_tools:
        print_warning(f"Missing tools: {', '.join(missing_tools)}")
        print_info("Install missing tools with: pip install -e '.[dev]'")
    
    return len(missing_tools) == 0


def print_setup_instructions():
    """Print setup instructions and next steps."""
    print_header("Setup Complete!")
    
    print("""
📋 Next Steps:

1. ✅ Pre-commit hooks are now installed and will run automatically on each commit

2. 🔧 To manually run pre-commit on all files:
   $ pre-commit run --all-files

3. 🚀 To update hook versions:
   $ pre-commit autoupdate

4. 📖 To learn more about pre-commit:
   $ pre-commit --help

5. ⚙️  To temporarily skip pre-commit (not recommended):
   $ git commit -m "message" --no-verify

6. 🧪 To run specific hooks:
   $ pre-commit run ruff
   $ pre-commit run mypy
   $ pre-commit run bandit

7. 📝 Commit message format (conventional commits):
   feat(api): add new feature
   fix: resolve bug
   docs: update documentation
   refactor: improve code structure
   test: add tests
   chore: maintenance tasks

🎯 Pre-commit will automatically:
   - Format code with ruff
   - Lint Python code
   - Check types with mypy
   - Scan for security issues
   - Validate JSON/YAML/TOML
   - Check for merge conflicts
   - Detect secrets and keys
   - Run fast test subset

⚠️  Note: Some hooks require additional tools. Install all dependencies with:
   $ pip install -e '.[dev,tests]'

📧 For issues or questions, see CONTRIBUTING.md
""")


def main():
    """Main setup function."""
    print_header("ArbitrageAI Pre-commit Setup")
    
    # Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    if not check_git_repo():
        sys.exit(1)
    
    # Install pre-commit if needed
    if not check_precommit_installed():
        if not install_precommit():
            sys.exit(1)
    
    # Check required tools
    check_required_tools()
    
    # Validate configuration
    if not validate_config():
        print_warning("Configuration has issues, but continuing...")
    
    # Install git hooks
    if not install_git_hooks():
        sys.exit(1)
    
    # Install commit-msg hook
    install_commit_msg_hook()
    
    # Optional: Run initial check
    print_info("\nWould you like to run initial pre-commit check on all files?")
    print_info("This may take several minutes but will catch existing issues.")
    response = input("Run initial check? (y/n): ").strip().lower()
    
    if response in ['y', 'yes']:
        run_initial_check()
    
    # Print instructions
    print_setup_instructions()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
