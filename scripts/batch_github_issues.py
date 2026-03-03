#!/usr/bin/env python3
"""
Batch GitHub Issues and PR Creation Tool

This script automates the process of:
1. Creating GitHub issues from markdown files
2. Creating branches for each issue
3. Generating PR templates
4. Tracking progress

Usage:
    python scripts/batch_github_issues.py create-issues    # Create all issues
    python scripts/batch_github_issues.py create-prs       # Create PRs for existing issues
    python scripts/batch_github_issues.py status           # Check status
    python scripts/batch_github_issues.py dry-run          # Preview without creating
"""

import subprocess
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import yaml


@dataclass
class IssueInfo:
    """Information about a GitHub issue."""
    file_path: Path
    title: str
    priority: str
    labels: list[str]
    number: Optional[int] = None
    url: Optional[str] = None
    branch_name: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None


@dataclass
class BatchResult:
    """Results from batch operations."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    issues: list[IssueInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class GitHubBatchManager:
    """Manages batch creation of GitHub issues and PRs."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.issues_dir = self.repo_root / ".github" / "ISSUES"
        self.results_file = self.repo_root / ".github" / "batch_results.json"
        self.dry_run = False

    def run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command and return the result."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return e

    def check_auth(self) -> bool:
        """Check if GitHub CLI is authenticated."""
        result = self.run_command(["gh", "auth", "status"], check=False)
        return result.returncode == 0

    def check_git(self) -> bool:
        """Check if we're in a git repository."""
        result = self.run_command(["git", "rev-parse", "--git-dir"], check=False)
        return result.returncode == 0

    def parse_front_matter(self, content: str) -> dict:
        """Parse YAML front matter from markdown content."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                return {}
        return {}

    def extract_title(self, content: str) -> str:
        """Extract title from markdown content."""
        # Try front matter first
        front_matter = self.parse_front_matter(content)
        if 'title' in front_matter:
            return front_matter['title']

        # Fall back to first heading
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()[:80]

        return "Untitled Issue"

    def extract_priority(self, content: str) -> str:
        """Extract priority from markdown content."""
        front_matter = self.parse_front_matter(content)
        if 'priority' in front_matter:
            return front_matter['priority'].lower()

        # Try to infer from content
        if 'CRITICAL' in content[:500]:
            return 'critical'
        elif 'HIGH' in content[:500]:
            return 'high'
        elif 'MEDIUM' in content[:500]:
            return 'medium'

        return 'medium'

    def determine_labels(self, content: str, priority: str) -> list[str]:
        """Determine labels for an issue."""
        labels = ['qaqc-review']

        # Add priority label
        labels.append(priority)

        # Infer from content
        if any(word in content.lower() for word in ['security', 'vulnerability', 'rce', 'injection']):
            labels.append('security')
        if any(word in content.lower() for word in ['performance', 'optimization', 'redis', 'index']):
            labels.append('performance')
        if any(word in content.lower() for word in ['refactor', 'code quality', 'cleanup']):
            labels.append('code-quality')
        if any(word in content.lower() for word in ['architecture', 'migration', 'database']):
            labels.append('architecture')
        if any(word in content.lower() for word in ['test', 'coverage']):
            labels.append('testing')
        if any(word in content.lower() for word in ['documentation', 'readme', 'guide']):
            labels.append('documentation')

        return list(set(labels))  # Remove duplicates

    def generate_branch_name(self, title: str, issue_number: Optional[int] = None) -> str:
        """Generate a valid git branch name from issue title."""
        # Convert to lowercase and replace spaces with hyphens
        branch = title.lower()
        branch = re.sub(r'[^a-z0-9\s-]', '', branch)  # Remove special chars
        branch = re.sub(r'\s+', '-', branch)  # Replace spaces with hyphens
        branch = re.sub(r'-+', '-', branch)  # Remove multiple hyphens
        branch = branch.strip('-')

        # Truncate if too long (max 255 chars for git refs)
        max_len = 200
        if len(branch) > max_len:
            branch = branch[:max_len].rsplit('-', 1)[0]

        # Add issue number prefix if available
        if issue_number:
            return f"issue/{issue_number}-{branch}"
        return f"issue/{branch}"

    def scan_issues(self) -> list[IssueInfo]:
        """Scan the issues directory for markdown files."""
        if not self.issues_dir.exists():
            raise FileNotFoundError(f"Issues directory not found: {self.issues_dir}")

        issues = []
        for md_file in sorted(self.issues_dir.glob("*.md")):
            if md_file.name == "README.md":
                continue

            content = md_file.read_text()
            title = self.extract_title(content)
            priority = self.extract_priority(content)
            labels = self.determine_labels(content, priority)

            issues.append(IssueInfo(
                file_path=md_file,
                title=title,
                priority=priority,
                labels=labels
            ))

        return issues

    def create_issue(self, issue: IssueInfo) -> bool:
        """Create a single GitHub issue."""
        print(f"  📝 Creating issue: {issue.title[:60]}...")

        # Build gh command
        cmd = [
            "gh", "issue", "create",
            "--title", issue.title,
            "--body-file", str(issue.file_path),
        ]

        # Add labels
        for label in issue.labels:
            cmd.extend(["--label", label])

        if self.dry_run:
            print(f"    [DRY RUN] Would run: {' '.join(cmd)}")
            issue.status = "dry-run"
            return True

        try:
            result = self.run_command(cmd)
            output = result.stdout.strip()

            # Extract issue number from output or URL
            if result.returncode == 0:
                # Try to get issue number from URL
                url_match = re.search(r'(https://github\.com/[^/]+/[^/]+/issues/\d+)', output)
                if url_match:
                    issue.url = url_match.group(1)
                    number_match = re.search(r'/issues/(\d+)', issue.url)
                    if number_match:
                        issue.number = int(number_match.group(1))
                        issue.branch_name = self.generate_branch_name(issue.title, issue.number)
                        issue.status = "created"
                        issue.created_at = datetime.now().isoformat()
                        print(f"    ✅ Created: {issue.url}")
                        return True

                # Fallback: get latest issue
                result2 = self.run_command(["gh", "issue", "list", "--limit", "1", "--json", "number,url"])
                if result2.stdout:
                    data = json.loads(result2.stdout)
                    if data:
                        issue.number = data[0]['number']
                        issue.url = data[0]['url']
                        issue.branch_name = self.generate_branch_name(issue.title, issue.number)
                        issue.status = "created"
                        issue.created_at = datetime.now().isoformat()
                        print(f"    ✅ Created: #{issue.number}")
                        return True

            print(f"    ❌ Failed to create issue")
            issue.status = "failed"
            return False

        except Exception as e:
            print(f"    ❌ Error: {e}")
            issue.status = "failed"
            return False

    def create_branch(self, issue: IssueInfo) -> bool:
        """Create a git branch for the issue."""
        if not issue.branch_name:
            print(f"  ⚠️  No branch name for issue #{issue.number}")
            return False

        print(f"  🌿 Creating branch: {issue.branch_name}")

        if self.dry_run:
            print(f"    [DRY RUN] Would create branch: {issue.branch_name}")
            return True

        # Check if branch already exists
        result = self.run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{issue.branch_name}"],
            check=False
        )
        if result.returncode == 0:
            print(f"    ⚠️  Branch already exists")
            return True

        # Create and checkout branch
        result = self.run_command(["git", "checkout", "-b", issue.branch_name])
        if result.returncode == 0:
            print(f"    ✅ Branch created")
            # Return to main branch
            self.run_command(["git", "checkout", "-"])
            return True
        else:
            print(f"    ❌ Failed to create branch")
            return False

    def create_pr_template(self, issue: IssueInfo) -> Path:
        """Create a PR template file for the issue."""
        pr_dir = self.repo_root / ".github" / "PR_TEMPLATES"
        pr_dir.mkdir(exist_ok=True)

        template_file = pr_dir / f"PR-{issue.number}.md"

        template_content = f"""# Pull Request: {issue.title}

## Related Issue
- Closes #{issue.number}
- Branch: `{issue.branch_name}`

## Description
<!-- Describe the changes made in this PR -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement
- [ ] Security fix

## Checklist
- [ ] Code follows project guidelines
- [ ] Self-review completed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Issue acceptance criteria met

## Testing
<!-- Describe how you tested these changes -->

## Related Issues
<!-- Link any related issues -->

## Screenshots/Recordings
<!-- If applicable, add screenshots or recordings to help explain your changes -->

## Additional Notes
<!-- Add any additional context or notes here -->
"""

        template_file.write_text(template_content)
        return template_file

    def create_pr(self, issue: IssueInfo, assignee: Optional[str] = None) -> bool:
        """Create a pull request for an issue."""
        if not issue.number or not issue.branch_name:
            print(f"  ❌ Cannot create PR: Issue #{issue.number} incomplete")
            return False

        print(f"  📦 Creating PR for issue #{issue.number}...")

        # Ensure branch exists
        if not self.create_branch(issue):
            return False

        # Create PR template
        template_file = self.create_pr_template(issue)

        if self.dry_run:
            print(f"    [DRY RUN] Would create PR from branch: {issue.branch_name}")
            print(f"    [DRY RUN] Template: {template_file}")
            return True

        # Checkout branch
        self.run_command(["git", "checkout", issue.branch_name])

        # Create a placeholder commit if branch is empty
        readme_file = self.repo_root / f"WORK_IN_PROGRESS_{issue.number}.md"
        readme_file.write_text(f"# Work in Progress\n\nIssue #{issue.number}: {issue.title}\n")

        self.run_command(["git", "add", str(readme_file)])
        self.run_command(["git", "commit", "-m", f"WIP: Issue #{issue.number} - {issue.title[:50]}"])

        # Push branch
        result = self.run_command(["git", "push", "-u", "origin", issue.branch_name])
        if result.returncode != 0:
            print(f"    ❌ Failed to push branch")
            return False

        # Create PR
        cmd = [
            "gh", "pr", "create",
            "--base", "main",
            "--head", issue.branch_name,
            "--title", f"Implement issue #{issue.number}: {issue.title[:60]}",
            "--body-file", str(template_file),
        ]

        if assignee:
            cmd.extend(["--assignee", assignee])

        result = self.run_command(cmd)
        if result.returncode == 0:
            print(f"    ✅ PR created: {result.stdout.strip()}")
            issue.status = "pr-created"
            # Clean up WIP file
            self.run_command(["git", "rm", str(readme_file)])
            self.run_command(["git", "commit", "-m", "Remove WIP file"])
            self.run_command(["git", "push"])
            return True
        else:
            print(f"    ❌ Failed to create PR: {result.stderr}")
            return False

    def create_issues_batch(self, issues: list[IssueInfo]) -> BatchResult:
        """Create multiple GitHub issues."""
        result = BatchResult(total=len(issues))

        print("\n" + "=" * 70)
        print("🚀 BATCH ISSUE CREATION")
        print("=" * 70)
        print(f"Total issues to create: {len(issues)}")
        print(f"Dry run: {self.dry_run}")
        print("=" * 70 + "\n")

        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Processing: {issue.file_path.name}")
            print("-" * 70)

            if self.create_issue(issue):
                result.success += 1
            else:
                result.failed += 1

            result.issues.append(issue)

        # Save results
        self.save_results(result)

        # Print summary
        self.print_summary(result)

        return result

    def create_prs_batch(self, issue_numbers: Optional[list[int]] = None,
                         assignee: Optional[str] = None) -> BatchResult:
        """Create PRs for existing issues."""
        result = BatchResult()

        print("\n" + "=" * 70)
        print("📦 BATCH PR CREATION")
        print("=" * 70)

        # Get issues from GitHub or use provided numbers
        if issue_numbers:
            issues = []
            for num in issue_numbers:
                # Fetch issue details
                cmd_result = self.run_command([
                    "gh", "issue", "view", str(num),
                    "--json", "title,number,state"
                ])
                if cmd_result.returncode == 0:
                    data = json.loads(cmd_result.stdout)
                    issue = IssueInfo(
                        file_path=Path(f".github/ISSUES/issue-{num}.md"),
                        title=data.get('title', f'Issue #{num}'),
                        priority='medium',
                        labels=[],
                        number=num,
                        branch_name=self.generate_branch_name(data.get('title', ''), num)
                    )
                    issues.append(issue)
        else:
            # Scan local issues directory
            issues = self.scan_issues()

        result.total = len(issues)

        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Creating PR for issue #{issue.number or '???'}")
            print("-" * 70)

            if self.create_pr(issue, assignee):
                result.success += 1
            else:
                result.failed += 1

            result.issues.append(issue)

        self.save_results(result)
        self.print_summary(result)

        return result

    def save_results(self, result: BatchResult) -> None:
        """Save batch operation results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "summary": {
                "total": result.total,
                "success": result.success,
                "failed": result.failed,
                "skipped": result.skipped
            },
            "issues": [
                {
                    "file": str(issue.file_path),
                    "title": issue.title,
                    "priority": issue.priority,
                    "labels": issue.labels,
                    "number": issue.number,
                    "url": issue.url,
                    "branch": issue.branch_name,
                    "status": issue.status,
                    "created_at": issue.created_at
                }
                for issue in result.issues
            ],
            "errors": result.errors
        }

        self.results_file.write_text(json.dumps(data, indent=2))
        print(f"\n💾 Results saved to: {self.results_file}")

    def print_summary(self, result: BatchResult) -> None:
        """Print a summary of batch operations."""
        print("\n" + "=" * 70)
        print("📊 BATCH OPERATION SUMMARY")
        print("=" * 70)
        print(f"Total:    {result.total}")
        print(f"✅ Success: {result.success} ({result.success/result.total*100:.1f}%)")
        print(f"❌ Failed:  {result.failed} ({result.failed/result.total*100:.1f}%)")
        print(f"⏭️  Skipped: {result.skipped}")
        print("=" * 70)

        if result.issues:
            print("\n📋 Issues:")
            for issue in result.issues:
                status_icon = {
                    "created": "✅",
                    "pr-created": "📦",
                    "failed": "❌",
                    "dry-run": "🔮",
                    "pending": "⏳"
                }.get(issue.status, "⚪")

                issue_num = f"#{issue.number}" if issue.number else "???"
                print(f"  {status_icon} {issue_num}: {issue.title[:50]} [{issue.status}]")

        print("\n" + "=" * 70)

    def show_status(self) -> None:
        """Show current status of issues and PRs."""
        print("\n" + "=" * 70)
        print("📊 GITHUB ISSUES & PRS STATUS")
        print("=" * 70)

        # Get issues from GitHub
        result = self.run_command([
            "gh", "issue", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,state,labels,url,createdAt"
        ])

        if result.returncode == 0:
            issues = json.loads(result.stdout)
            print(f"\nFound {len(issues)} QA/QC issues:\n")

            for issue in issues:
                state_icon = "🟢" if issue['state'] == 'open' else "🔒"
                labels = [l['name'] for l in issue['labels']]
                priority = next((l for l in labels if l in ['critical', 'high', 'medium']), 'medium')
                priority_icon = {
                    'critical': '🔴',
                    'high': '🟡',
                    'medium': '🟢'
                }.get(priority, '⚪')

                print(f"{state_icon}{priority_icon} #{issue['number']}: {issue['title'][:50]}")
                print(f"   {issue['url']}")
                print(f"   Created: {issue['createdAt'][:10]}")
                print()

        # Get PRs
        result = self.run_command([
            "gh", "pr", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,state,url,headRefName"
        ])

        if result.returncode == 0:
            prs = json.loads(result.stdout)
            if prs:
                print(f"\nFound {len(prs)} QA/QC PRs:\n")
                for pr in prs:
                    state_icon = "🟢" if pr['state'] == 'open' else "🔒"
                    print(f"{state_icon} #{pr['number']}: {pr['title'][:50]}")
                    print(f"   Branch: {pr['headRefName']}")
                    print(f"   {pr['url']}")
                    print()

        print("=" * 70)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch create GitHub issues and PRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create-issues           # Create all issues from markdown files
  %(prog)s create-issues --dry-run # Preview without creating
  %(prog)s create-prs              # Create PRs for all issues
  %(prog)s create-prs --numbers 1 2 3  # Create PRs for specific issues
  %(prog)s status                  # Show current status
  %(prog)s dry-run                 # Full dry run preview
        """
    )

    parser.add_argument(
        'command',
        choices=['create-issues', 'create-prs', 'status', 'dry-run'],
        help='Command to execute'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview actions without executing'
    )
    parser.add_argument(
        '--numbers',
        type=int,
        nargs='+',
        help='Specific issue numbers to process'
    )
    parser.add_argument(
        '--assignee',
        type=str,
        help='GitHub username to assign issues/PRs to'
    )
    parser.add_argument(
        '--repo',
        type=Path,
        default=Path.cwd(),
        help='Repository root directory'
    )

    args = parser.parse_args()

    # Initialize manager
    manager = GitHubBatchManager(repo_root=args.repo)
    manager.dry_run = args.dry_run or args.command == 'dry-run'

    # Check prerequisites
    if not manager.check_git():
        print("❌ Not in a git repository")
        sys.exit(1)

    if not manager.check_auth():
        print("❌ GitHub CLI not authenticated. Run: gh auth login")
        sys.exit(1)

    print("✅ GitHub CLI authenticated")
    print("✅ Git repository detected")

    # Execute command
    if args.command == 'create-issues':
        issues = manager.scan_issues()
        result = manager.create_issues_batch(issues)
        sys.exit(0 if result.failed == 0 else 1)

    elif args.command == 'create-prs':
        result = manager.create_prs_batch(
            issue_numbers=args.numbers,
            assignee=args.assignee
        )
        sys.exit(0 if result.failed == 0 else 1)

    elif args.command == 'status':
        manager.show_status()
        sys.exit(0)

    elif args.command == 'dry-run':
        print("\n🔮 DRY RUN MODE - No changes will be made\n")
        issues = manager.scan_issues()
        result = manager.create_issues_batch(issues)
        sys.exit(0)


if __name__ == "__main__":
    main()
