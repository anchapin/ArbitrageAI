#!/usr/bin/env python3
"""
B904 Violation Fixer

This script systematically fixes B904 violations (raise-without-from-inside-except)
by adding proper exception chaining with 'from exc' or 'from None'.

B904 Rule:
Within an except clause, raise exceptions with `raise ... from err` or 
`raise ... from None` to distinguish them from errors in exception handling.

Usage:
    python scripts/fix_b904.py [--dry-run] [--verbose]

Options:
    --dry-run     Show what would be fixed without making changes
    --verbose     Show detailed output for each fix
    --interactive Prompt before each fix

The script:
1. Identifies all B904 violations using ruff
2. Parses each violation to understand context
3. Applies the appropriate fix pattern
4. Creates backups before modifying files
5. Provides a detailed report of changes

Fix Patterns:
- Pattern 1: Add 'from exc' when exception variable exists
- Pattern 2: Rename exception variable to 'exc' and add 'from exc'
- Pattern 3: Add 'from None' when intentional suppression
- Pattern 4: Manual review for complex cases
"""

import re
import subprocess
import sys
import os
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime


@dataclass
class B904Violation:
    """Represents a single B904 violation."""
    file: Path
    line: int
    column: int
    code: str
    message: str
    context_before: str = ""
    context_after: str = ""


@dataclass
class FixResult:
    """Result of attempting to fix a violation."""
    violation: B904Violation
    success: bool
    old_code: str
    new_code: str
    fix_type: str
    error_message: str = ""


def run_ruff_check(directory: str = "src/") -> List[B904Violation]:
    """Run ruff check and parse B904 violations."""
    print("🔍 Running ruff check for B904 violations...")
    
    result = subprocess.run(
        ["ruff", "check", directory, "--select", "B904", "--output-format", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and not result.stdout.strip():
        print("✅ No B904 violations found!")
        return []
    
    violations = []
    
    try:
        import json
        data = json.loads(result.stdout)
        
        for item in data:
            if item.get("code") == "B904":
                violation = B904Violation(
                    file=Path(item["filename"]),
                    line=item["location"]["row"],
                    column=item["location"]["column"],
                    code=item["code"],
                    message=item["message"]
                )
                violations.append(violation)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error parsing ruff output: {e}")
        print(f"Raw output: {result.stdout[:500]}")
        return []
    
    print(f"📊 Found {len(violations)} B904 violation(s)")
    return violations


def read_file_with_context(file_path: Path, line_num: int, context_lines: int = 3) -> Tuple[str, str, str]:
    """Read file and return target line with context."""
    try:
        lines = file_path.read_text().splitlines(keepends=True)
        
        # Get context before and after
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        
        context_before = "".join(lines[start:line_num - 1])
        target_line = lines[line_num - 1] if line_num <= len(lines) else ""
        context_after = "".join(lines[line_num:end])
        
        return context_before, target_line, context_after
    except Exception as e:
        return "", "", f"Error reading file: {e}"


def analyze_exception_pattern(target_line: str, context_before: str) -> Tuple[str, Optional[str]]:
    """
    Analyze the exception handling pattern.
    
    Returns:
        Tuple of (fix_type, exception_var_name)
        fix_type: 'add_from_exc', 'add_from_none', 'manual_review'
        exception_var_name: The name of the exception variable if found
    """
    # Pattern 1: Check if there's an 'as exc' or 'as e' in the except clause
    # Look in the last few lines before the raise
    except_pattern = r'except\s+[^(]*\s+as\s+(\w+)'
    match = re.search(except_pattern, context_before)
    
    if match:
        exc_var = match.group(1)
        # Check if 'from' is already present (shouldn't be for B904)
        if ' from ' not in target_line.lower():
            return 'add_from_exc', exc_var
    
    # Pattern 2: Check for except with exception but no 'as'
    # e.g., "except ValueError:" or "except httpx.HTTPError:"
    except_no_as = r'except\s+([\w.]+)\s*:'
    match_no_as = re.search(except_no_as, context_before)
    
    if match_no_as:
        # Exception type is captured but not assigned to variable
        # We should add 'as exc' to the except line, but that's complex
        # For now, mark as needs manual review or use 'from None' if exception not used
        exc_type = match_no_as.group(1)
        # Check if the exception is referenced in the raise (e.g., str(e))
        if re.search(rf'\b{exc_type}\b', target_line):
            return 'manual_review', None  # Need to add 'as exc' first
        else:
            return 'add_from_none', None
    
    # Pattern 3: Check for bare except (no exception variable)
    bare_except = r'except\s*:'
    if re.search(bare_except, context_before):
        # Need to add exception variable first
        return 'add_exception_var', None
    
    # Pattern 4: Check if exception variable 'e' is used in the raise
    if re.search(r'\bstr\(e\)|\brepr\(e\)|\b{e}\b', target_line):
        # Exception 'e' is being used, find where it's defined
        except_with_e = r'except\s+[^(]*\s+as\s+e\s*:'
        if re.search(except_with_e, context_before):
            return 'add_from_exc', 'e'
    
    # Pattern 5: Default - check if any exception variable exists
    any_except = r'except\s+.*?\s+as\s+(\w+)\s*:'
    any_match = re.search(any_except, context_before)
    if any_match:
        exc_var = any_match.group(1)
        return 'add_from_exc', exc_var
    
    return 'manual_review', None


def generate_fix(
    target_line: str,
    context_before: str,
    fix_type: str,
    exc_var: Optional[str] = None
) -> Optional[str]:
    """Generate the fixed code for a violation."""

    stripped = target_line.rstrip()
    indent = len(target_line) - len(target_line.lstrip())
    indent_str = " " * indent

    if fix_type == 'add_from_exc' and exc_var:
        # Pattern: raise Error("msg") -> raise Error("msg") from exc_var
        # Check if 'from' is already there
        if ' from ' in stripped.lower():
            return None  # Already has 'from', shouldn't happen for B904

        # Check if this is a multi-line raise
        is_multiline = stripped.endswith('(') or (stripped.count('(') > stripped.count(')'))
        
        if is_multiline:
            return None  # Mark for manual review - too complex
        else:
            # Single line raise - add 'from {exc_var}' at the end
            fixed = f"{stripped} from {exc_var}\n"
            return fixed

    elif fix_type == 'add_from_none':
        # Pattern: raise Error("msg") -> raise Error("msg") from None
        if ' from ' in stripped.lower():
            return None
        
        is_multiline = stripped.endswith('(') or (stripped.count('(') > stripped.count(')'))
        if is_multiline:
            return None  # Mark for manual review
        
        fixed = f"{stripped} from None\n"
        return fixed

    elif fix_type == 'add_exception_var':
        # Pattern: except: -> except Exception as exc:
        # This requires modifying the except line, not the raise line
        # Mark for manual review
        return None

    elif fix_type == 'add_from_exc_or_none':
        # Try to determine if should be 'from exc' or 'from None'
        # If exception variable exists in context, use it
        except_match = re.search(r'except\s+[^(]*\s+as\s+(\w+)', context_before)
        if except_match:
            exc_var = except_match.group(1)
            # Check if it's a simple raise (not multi-line)
            if not (stripped.endswith('(') or (stripped.count('(') > stripped.count(')'))):
                fixed = f"{stripped} from {exc_var}\n"
                return fixed
        
        # No exception variable or multi-line, suggest 'from None'
        if not (stripped.endswith('(') or (stripped.count('(') > stripped.count(')'))):
            fixed = f"{stripped} from None\n"
            return fixed
        return None

    return None


def create_backup(file_path: Path) -> Path:
    """Create a backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f"{file_path.suffix}.b904_backup_{timestamp}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def fix_violation(violation: B904Violation, dry_run: bool = False, verbose: bool = False) -> FixResult:
    """Attempt to fix a single B904 violation."""
    
    # Read file with context
    context_before, target_line, context_after = read_file_with_context(
        violation.file, violation.line
    )
    
    if not target_line:
        return FixResult(
            violation=violation,
            success=False,
            old_code="",
            new_code="",
            fix_type="error",
            error_message="Could not read target line"
        )
    
    # Analyze the pattern
    fix_type, exc_var = analyze_exception_pattern(target_line, context_before)
    
    if verbose:
        print(f"\n📍 {violation.file}:{violation.line}")
        print(f"   Fix type: {fix_type}, Exception var: {exc_var}")
        print(f"   Original: {target_line.strip()}")
    
    # Generate fix
    fixed_line = generate_fix(target_line, context_before, fix_type, exc_var)
    
    if not fixed_line:
        return FixResult(
            violation=violation,
            success=False,
            old_code=target_line,
            new_code="",
            fix_type=fix_type,
            error_message="Requires manual review"
        )
    
    if verbose:
        print(f"   Fixed:    {fixed_line.strip()}")
    
    # Apply fix if not dry run
    if not dry_run:
        try:
            # Create backup if not already done
            backup_path = create_backup(violation.file)
            if verbose:
                print(f"   Backup:   {backup_path}")
            
            # Read entire file
            content = violation.file.read_text()
            lines = content.splitlines(keepends=True)
            
            # Replace the target line
            line_idx = violation.line - 1
            if line_idx < len(lines):
                lines[line_idx] = fixed_line
                new_content = "".join(lines)
                
                # Write back
                violation.file.write_text(new_content)
                
                return FixResult(
                    violation=violation,
                    success=True,
                    old_code=target_line,
                    new_code=fixed_line,
                    fix_type=fix_type
                )
        except Exception as e:
            return FixResult(
                violation=violation,
                success=False,
                old_code=target_line,
                new_code="",
                fix_type=fix_type,
                error_message=str(e)
            )
    
    # Dry run - just return the result
    return FixResult(
        violation=violation,
        success=True,
        old_code=target_line,
        new_code=fixed_line,
        fix_type=fix_type
    )


def print_report(results: List[FixResult], dry_run: bool = False):
    """Print a detailed report of fixes."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful
    
    print("\n" + "="*80)
    print("📊 B904 FIX REPORT")
    print("="*80)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes were made")
        print()
    
    print(f"Total violations: {total}")
    print(f"✅ Fixed: {successful}")
    print(f"⚠️  Need manual review: {failed}")
    print(f"Success rate: {successful/total*100:.1f}%" if total > 0 else "N/A")
    print()
    
    # Group by file
    by_file = {}
    for result in results:
        file_path = result.violation.file
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(result)
    
    print(f"Files affected: {len(by_file)}")
    print()
    
    # Show successful fixes
    if successful > 0:
        print("✅ SUCCESSFUL FIXES:")
        print("-" * 80)
        for file_path, file_results in sorted(by_file.items()):
            file_successes = [r for r in file_results if r.success]
            if file_successes:
                print(f"\n{file_path}:")
                for result in file_successes:
                    print(f"  Line {result.violation.line}: {result.fix_type}")
                    if result.old_code.strip() != result.new_code.strip():
                        print(f"    - {result.old_code.strip()}")
                        print(f"    + {result.new_code.strip()}")
        print()
    
    # Show failures
    if failed > 0:
        print("⚠️  NEED MANUAL REVIEW:")
        print("-" * 80)
        for result in results:
            if not result.success:
                print(f"\n{result.violation.file}:{result.violation.line}")
                print(f"   Reason: {result.error_message}")
                print(f"   Code: {result.old_code.strip()}")
        print()
    
    # Show backup locations
    if not dry_run and successful > 0:
        print("💾 BACKUPS:")
        print("-" * 80)
        backup_files = set()
        for file_path in by_file.keys():
            backups = list(file_path.parent.glob(f"{file_path.name}.b904_backup_*"))
            backup_files.update(backups)
        
        for backup in sorted(backup_files):
            print(f"  {backup}")
        print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fix B904 violations (raise-without-from-inside-except)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each fix"
    )
    parser.add_argument(
        "--directory",
        default="src/",
        help="Directory to check (default: src/)"
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("🔧 B904 VIOLATION FIXER")
    print("="*80)
    print()
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    # Get violations
    violations = run_ruff_check(args.directory)
    
    if not violations:
        return 0
    
    print()
    print(f"Processing {len(violations)} violation(s)...")
    print()
    
    # Fix violations
    results = []
    for i, violation in enumerate(violations, 1):
        if args.verbose:
            print(f"\n[{i}/{len(violations)}] Processing {violation.file}:{violation.line}")
        
        result = fix_violation(violation, dry_run=args.dry_run, verbose=args.verbose)
        results.append(result)
        
        if not args.verbose:
            # Progress indicator
            if i % 50 == 0:
                print(f"  Processed {i}/{len(violations)}...")
    
    # Print report
    print_report(results, dry_run=args.dry_run)
    
    # Summary
    successful = sum(1 for r in results if r.success)
    total = len(results)
    
    print("="*80)
    if args.dry_run:
        print(f"🔍 DRY RUN: Would fix {successful}/{total} violations")
        print("   Run without --dry-run to apply fixes")
    else:
        print(f"✅ Fixed {successful}/{total} violations")
        if successful < total:
            print(f"⚠️  {total - successful} violations need manual review")
            print("   Review the violations above and fix them manually")
    
    print("="*80)
    
    return 0 if successful == total else 1


if __name__ == "__main__":
    sys.exit(main())
