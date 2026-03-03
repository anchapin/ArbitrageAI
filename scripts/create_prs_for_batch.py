#!/usr/bin/env python3
"""
Create PRs for the QAQC batch issues (184-194).
"""

import subprocess
import json
from pathlib import Path
import re

REPO_ROOT = Path.cwd()
ISSUES_DIR = REPO_ROOT / ".github" / "ISSUES"

# Issue numbers from the batch we just created
ISSUE_NUMBERS = [184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194]

def run_command(cmd, check=True):
    """Run a shell command."""
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=check)
    return result

def get_issue_info(number):
    """Get issue info from GitHub."""
    result = run_command(["gh", "issue", "view", str(number), "--json", "title,number,state,url"], check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None

def generate_branch_name(title, number):
    """Generate a valid git branch name."""
    branch = title.lower()
    branch = re.sub(r'[^a-z0-9\s-]', '', branch)
    branch = re.sub(r'\s+', '-', branch)
    branch = re.sub(r'-+', '-', branch)
    branch = branch.strip('-')
    max_len = 200
    if len(branch) > max_len:
        branch = branch[:max_len].rsplit('-', 1)[0]
    return f"issue/{number}-{branch}"

def find_issue_file(number):
    """Find the corresponding issue file."""
    # Try to find by pattern matching
    for md_file in ISSUES_DIR.glob("*.md"):
        content = md_file.read_text()
        if f"#{number}" in content or f"Issue #{number}" in content:
            return md_file
        # Also check by title matching
        issue_info = get_issue_info(number)
        if issue_info and issue_info.get('title', '').lower()[:30] in md_file.name.lower():
            return md_file
    return None

def generate_pr_body(issue_info, issue_file):
    """Generate PR body from issue."""
    title = issue_info.get('title', f'Issue #{issue_info["number"]}')
    number = issue_info['number']
    
    content = issue_file.read_text() if issue_file else ""
    
    # Extract description
    description = ""
    in_description = False
    for line in content.split('\n'):
        if line.startswith('# ') and not in_description:
            in_description = True
            continue
        elif in_description:
            if line.startswith('## '):
                break
            description += line + '\n'
    
    # Extract acceptance criteria
    acceptance_criteria = []
    in_criteria = False
    for line in content.split('\n'):
        if 'Acceptance Criteria' in line:
            in_criteria = True
            continue
        if in_criteria:
            if line.startswith('- [ ]') or line.startswith('- [x]'):
                acceptance_criteria.append(line)
            elif line.startswith('## ') and acceptance_criteria:
                break
    
    # Build PR body
    pr_body = f"""# Pull Request: {title}

## Related Issue
- Closes #{number}

## Description
{description.strip() if description else 'See issue description for details.'}

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement
- [ ] Security fix

## Acceptance Criteria
"""
    
    if acceptance_criteria:
        for criterion in acceptance_criteria:
            pr_body += f"{criterion}\n"
    else:
        pr_body += "- [ ] All acceptance criteria from issue completed\n"
    
    pr_body += """
## Implementation Checklist
- [ ] Code changes complete
- [ ] Self-review completed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings
- [ ] All acceptance criteria met

## Testing
<!-- Describe how you tested these changes -->

## Related Issues
<!-- Link any related issues -->

## Screenshots/Recordings
<!-- If applicable -->

## Additional Notes
<!-- Add any additional context -->
"""
    
    return pr_body

def create_pr_for_issue(number):
    """Create a PR for a specific issue."""
    print(f"\n{'='*80}")
    print(f"Creating PR for issue #{number}")
    print('='*80)
    
    # Get issue info
    issue_info = get_issue_info(number)
    if not issue_info:
        print(f"  ❌ Could not get issue #{number}")
        return False
    
    title = issue_info.get('title', f'Issue #{number}')
    print(f"  Title: {title[:60]}...")
    
    # Generate branch name
    branch_name = generate_branch_name(title, number)
    print(f"  Branch: {branch_name}")
    
    # Find issue file
    issue_file = find_issue_file(number)
    if not issue_file:
        # Try to match by QAQC number
        qaqc_num = number - 183  # QAQC-001 -> 184, etc.
        pattern = f"QAQC-{qaqc_num:03d}*"
        matches = list(ISSUES_DIR.glob(pattern))
        if matches:
            issue_file = matches[0]
            print(f"  Found issue file: {issue_file.name}")
    
    if not issue_file:
        print(f"  ⚠️  Could not find issue file, using template")
    
    # Get current branch
    current_branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    
    # Check if branch exists
    result = run_command(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], check=False)
    branch_exists = (result.returncode == 0)
    
    if not branch_exists:
        # Create and checkout branch
        print(f"  Creating branch...")
        result = run_command(["git", "checkout", "-b", branch_name])
        if result.returncode != 0:
            print(f"  ❌ Failed to create branch: {result.stderr}")
            run_command(["git", "checkout", current_branch])
            return False
    else:
        print(f"  Branch already exists, checking out...")
        result = run_command(["git", "checkout", branch_name])
        if result.returncode != 0:
            print(f"  ❌ Failed to checkout branch: {result.stderr}")
            return False
    
    # Create a placeholder commit if needed
    result = run_command(["git", "rev-list", "--count", "HEAD"], check=False)
    if result.returncode == 0:
        # Create a work-in-progress file
        readme_file = REPO_ROOT / f"WORK_IN_PROGRESS_{number}.md"
        readme_file.write_text(f"# Work in Progress\n\nIssue #{number}: {title}\n\nThis is a placeholder commit to create the PR branch.\n")
        
        run_command(["git", "add", str(readme_file)])
        result = run_command(["git", "commit", "-m", f"WIP: Issue #{number} - {title[:50]}"], check=False)
        
        if result.returncode == 0:
            print(f"  Created placeholder commit")
        else:
            print(f"  ℹ️  No changes to commit (branch may already have commits)")
    
    # Push branch
    print(f"  Pushing branch...")
    result = run_command(["git", "push", "-u", "origin", branch_name])
    if result.returncode != 0:
        print(f"  ❌ Failed to push branch: {result.stderr}")
        run_command(["git", "checkout", current_branch])
        return False
    
    # Generate PR body
    pr_body = generate_pr_body(issue_info, issue_file)
    pr_body_file = REPO_ROOT / f".pr_body_{number}.md"
    pr_body_file.write_text(pr_body)
    
    # Create PR
    print(f"  Creating PR...")
    cmd = [
        "gh", "pr", "create",
        "--base", "main",
        "--head", branch_name,
        "--title", f"Issue #{number}: {title[:60]}",
        "--body-file", str(pr_body_file),
    ]
    
    result = run_command(cmd, check=False)
    
    # Clean up
    run_command(["git", "checkout", current_branch])
    pr_body_file.unlink(missing_ok=True)
    
    if result.returncode == 0:
        pr_url = result.stdout.strip()
        print(f"  ✅ PR created: {pr_url}")
        return True
    else:
        # Check if PR already exists
        if "already exists" in result.stderr:
            print(f"  ℹ️  PR already exists")
            return True
        print(f"  ❌ Failed to create PR: {result.stderr}")
        return False

def main():
    """Main entry point."""
    print("="*80)
    print("📦 BATCH PR CREATION FOR QAQC ISSUES")
    print("="*80)
    print(f"Issue numbers: {ISSUE_NUMBERS}")
    
    success_count = 0
    failed_count = 0
    
    for number in ISSUE_NUMBERS:
        if create_pr_for_issue(number):
            success_count += 1
        else:
            failed_count += 1
    
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total: {len(ISSUE_NUMBERS)}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print("="*80)

if __name__ == "__main__":
    main()
