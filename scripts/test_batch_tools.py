#!/usr/bin/env python3
"""
Test script for batch GitHub issues tools.

This script tests the functionality without creating actual GitHub issues.
Run this to verify everything is working correctly.

Usage:
    python scripts/test_batch_tools.py
"""

import subprocess
import sys
from pathlib import Path


def run_test(name: str, cmd: list[str], expected_return: int = 0) -> bool:
    """Run a test command and check the result."""
    print(f"\n{'='*70}")
    print(f"🧪 TEST: {name}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=Path.cwd()
        )

        success = result.returncode == expected_return

        if result.stdout:
            print("STDOUT:")
            print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if success:
            print(f"✅ PASSED: Return code {result.returncode}")
        else:
            print(f"❌ FAILED: Expected {expected_return}, got {result.returncode}")

        return success

    except Exception as e:
        print(f"❌ FAILED: Exception - {e}")
        return False


def check_prerequisites() -> bool:
    """Check if prerequisites are installed."""
    print("\n" + "="*70)
    print("🔍 CHECKING PREREQUISITES")
    print("="*70)

    # Use python3 on Linux, python on Windows/macOS
    python_cmd = "python3" if sys.platform != "win32" else "python"

    checks = [
        ("Python 3.10+", [python_cmd, "--version"]),
        ("Git", ["git", "--version"]),
        ("GitHub CLI", ["gh", "--version"]),
    ]

    all_passed = True
    for name, cmd in checks:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"✅ {name}: {result.stdout.strip().split()[0]}")
            else:
                print(f"❌ {name}: Not found")
                all_passed = False
        except Exception as e:
            print(f"❌ {name}: {e}")
            all_passed = False

    # Check Python package
    try:
        import yaml
        print(f"✅ PyYAML: Installed")
    except ImportError:
        print(f"❌ PyYAML: Not installed (run: pip install pyyaml)")
        all_passed = False

    return all_passed


def check_file_structure() -> bool:
    """Check if required files exist."""
    print("\n" + "="*70)
    print("📁 CHECKING FILE STRUCTURE")
    print("="*70)

    repo_root = Path.cwd()
    required_files = [
        "scripts/batch_github_issues.py",
        "scripts/batch_orchestrator.py",
        ".github/ISSUES/README.md",
        ".github/pull_request_template.md",
        "docs/BATCH_GITHUB_ISSUES_GUIDE.md",
        "docs/BATCH_ISSUES_QUICKSTART.md",
    ]

    all_exist = True
    for file_path in required_files:
        full_path = repo_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - NOT FOUND")
            all_exist = False

    # Check issues directory
    issues_dir = repo_root / ".github" / "ISSUES"
    if issues_dir.exists():
        md_files = list(issues_dir.glob("*.md"))
        print(f"✅ Found {len(md_files)} issue files in .github/ISSUES/")
    else:
        print(f"❌ .github/ISSUES/ directory not found")
        all_exist = False

    return all_exist


def test_help_commands() -> bool:
    """Test --help commands."""
    print("\n" + "="*70)
    print("📖 TESTING HELP COMMANDS")
    print("="*70)

    # Use python3 on Linux
    python_cmd = "python3" if sys.platform != "win32" else "python"

    tests = [
        ("Batch Issues Help", [python_cmd, "scripts/batch_github_issues.py", "--help"]),
        ("Batch Orchestrator Help", [python_cmd, "scripts/batch_orchestrator.py", "--help"]),
    ]

    all_passed = True
    for name, cmd in tests:
        if not run_test(name, cmd):
            all_passed = False

    return all_passed


def test_dry_run() -> bool:
    """Test dry-run functionality."""
    print("\n" + "="*70)
    print("🔮 TESTING DRY RUN MODE")
    print("="*70)

    # Use python3 on Linux
    python_cmd = "python3" if sys.platform != "win32" else "python"

    # Test batch_github_issues.py dry-run
    test1 = run_test(
        "Batch Issues Dry Run",
        [python_cmd, "scripts/batch_github_issues.py", "dry-run"],
        expected_return=0
    )

    return test1


def test_scan_issues() -> bool:
    """Test issue scanning (via dry-run output)."""
    print("\n" + "="*70)
    print("📋 TESTING ISSUE SCANNING")
    print("="*70)

    # Use python3 on Linux
    python_cmd = "python3" if sys.platform != "win32" else "python"

    try:
        result = subprocess.run(
            [python_cmd, "scripts/batch_github_issues.py", "dry-run"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path.cwd()
        )

        output = result.stdout

        # Check for expected output
        checks = [
            ("Issues directory scanned", "Total issues to create:" in output),
            ("Issue files found", ".md" in output),
            ("Dry run mode", "DRY RUN" in output or "Dry run: True" in output),
        ]

        all_passed = True
        for name, check in checks:
            if check:
                print(f"✅ {name}")
            else:
                print(f"❌ {name}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 BATCH GITHUB ISSUES TOOLS - TEST SUITE")
    print("="*70)
    print(f"Repository: {Path.cwd()}")
    print(f"Python: {sys.version}")
    print("="*70)

    results = {
        "Prerequisites": check_prerequisites(),
        "File Structure": check_file_structure(),
        "Help Commands": test_help_commands(),
        "Dry Run": test_dry_run(),
        "Issue Scanning": test_scan_issues(),
    }

    # Print summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*70)

    if passed == total:
        print("\n🎉 All tests passed! Ready to create issues.")
        print("\nNext steps:")
        print("1. Review issues in .github/ISSUES/")
        print("2. Run: python scripts/batch_github_issues.py create-issues")
        print("3. Check status: python scripts/batch_github_issues.py status")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Install GitHub CLI: brew install gh")
        print("- Authenticate: gh auth login")
        print("- Install PyYAML: pip install pyyaml")
        return 1


if __name__ == "__main__":
    sys.exit(main())
