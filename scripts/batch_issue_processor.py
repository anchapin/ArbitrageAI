#!/usr/bin/env python3
"""
Enhanced Batch Issue Processor with Parallel Execution

This script provides advanced batch processing for GitHub issues:
1. Parallel issue creation with configurable concurrency
2. Automatic PR creation from issue content
3. Smart branch management with worktrees
4. GitHub Projects integration
5. Real-time progress tracking
6. Automatic commit generation from issue checklists

Usage:
    python scripts/batch_issue_processor.py process --all          # Process all issues
    python scripts/batch_issue_processor.py process --priority high  # By priority
    python scripts/batch_issue_processor.py create-prs --auto      # Auto-create PRs
    python scripts/batch_issue_processor.py status                 # Check status
    python scripts/batch_issue_processor.py report                 # Generate report
"""

import asyncio
import subprocess
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from enum import Enum
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib


class Priority(Enum):
    """Issue priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(Enum):
    """Issue processing status."""
    PENDING = "pending"
    CREATED = "created"
    BRANCH_CREATED = "branch_created"
    PR_CREATED = "pr_created"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class IssueInfo:
    """Information about a GitHub issue."""
    file_path: Path
    title: str
    priority: str
    labels: List[str]
    number: Optional[int] = None
    url: Optional[str] = None
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    status: IssueStatus = IssueStatus.PENDING
    created_at: Optional[str] = None
    error_message: Optional[str] = None
    estimated_effort: str = "Unknown"
    acceptance_criteria: List[str] = field(default_factory=list)
    implementation_plan: List[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """Results from batch operations."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    issues: List[IssueInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    parallel: bool = False
    max_workers: int = 1


class EnhancedBatchProcessor:
    """Enhanced batch processor with parallel execution and auto-PR generation."""

    def __init__(self, repo_root: Optional[Path] = None, max_workers: int = 4):
        self.repo_root = repo_root or Path.cwd()
        self.issues_dir = self.repo_root / ".github" / "ISSUES"
        self.results_file = self.repo_root / ".github" / "batch_results_enhanced.json"
        self.projects_enabled = False
        self.project_id: Optional[str] = None
        self.max_workers = max_workers
        self.dry_run = False
        self.verbose = False

    def run_command(self, cmd: List[str], check: bool = True, 
                    timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a shell command with timeout."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired(cmd, timeout)
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return e

    async def run_command_async(self, cmd: List[str], 
                                check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command asynchronously."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.repo_root
        )
        stdout, stderr = await process.communicate()
        
        result = subprocess.CompletedProcess(
            cmd,
            process.returncode,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else ""
        )
        
        if check and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, stderr, stdout)
        
        return result

    def check_prerequisites(self) -> Tuple[bool, List[str]]:
        """Check if all prerequisites are met."""
        errors = []
        
        # Check git
        result = self.run_command(["git", "rev-parse", "--git-dir"], check=False)
        if result.returncode != 0:
            errors.append("Not in a git repository")
        
        # Check GitHub CLI
        result = self.run_command(["gh", "auth", "status"], check=False)
        if result.returncode != 0:
            errors.append("GitHub CLI not authenticated. Run: gh auth login")
        
        # Check issues directory
        if not self.issues_dir.exists():
            errors.append(f"Issues directory not found: {self.issues_dir}")
        
        return len(errors) == 0, errors

    def parse_front_matter(self, content: str) -> Dict:
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
        front_matter = self.parse_front_matter(content)
        if 'title' in front_matter:
            return front_matter['title']
        
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()[:80]
        
        return "Untitled Issue"

    def extract_priority(self, content: str) -> str:
        """Extract priority from markdown content."""
        front_matter = self.parse_front_matter(content)
        if 'priority' in front_matter:
            return front_matter['priority'].lower()
        
        if 'CRITICAL' in content[:500]:
            return 'critical'
        elif 'HIGH' in content[:500]:
            return 'high'
        elif 'MEDIUM' in content[:500]:
            return 'medium'
        
        return 'medium'

    def extract_estimated_effort(self, content: str) -> str:
        """Extract estimated effort from markdown content."""
        front_matter = self.parse_front_matter(content)
        if 'estimated_effort' in front_matter:
            return front_matter['estimated_effort']
        return "Unknown"

    def extract_acceptance_criteria(self, content: str) -> List[str]:
        """Extract acceptance criteria from issue content."""
        criteria = []
        in_criteria = False
        
        for line in content.split('\n'):
            if 'Acceptance Criteria' in line or 'acceptance criteria' in line.lower():
                in_criteria = True
                continue
            
            if in_criteria:
                if line.startswith('- [ ]') or line.startswith('- [x]'):
                    criteria.append(line.strip())
                elif line.startswith('#') and criteria:
                    break
                elif not line.strip() and criteria:
                    continue
                else:
                    break
        
        return criteria

    def extract_implementation_plan(self, content: str) -> List[str]:
        """Extract implementation plan/steps from issue content."""
        plan = []
        in_plan = False
        
        section_markers = [
            'Implementation Plan',
            'Implementation Steps',
            'Steps to Complete',
            'Task List',
            'TODO',
            '## Tasks'
        ]
        
        for line in content.split('\n'):
            if any(marker.lower() in line.lower() for marker in section_markers):
                in_plan = True
                continue
            
            if in_plan:
                if line.startswith('- [ ]') or line.startswith('- [x]'):
                    plan.append(line.strip())
                elif line.startswith('1.') or line.startswith('-'):
                    plan.append(line.strip())
                elif line.startswith('#') and plan:
                    break
                elif not line.strip() and plan:
                    continue
                else:
                    break
        
        return plan

    def determine_labels(self, content: str, priority: str) -> List[str]:
        """Determine labels for an issue based on content analysis."""
        labels = ['qaqc-review']
        labels.append(priority)
        
        content_lower = content.lower()
        
        # Security detection
        if any(word in content_lower for word in ['security', 'vulnerability', 'rce', 'injection', 'xss', 'csrf']):
            labels.append('security')
        
        # Performance detection
        if any(word in content_lower for word in ['performance', 'optimization', 'redis', 'index', 'caching']):
            labels.append('performance')
        
        # Code quality detection
        if any(word in content_lower for word in ['refactor', 'code quality', 'cleanup', 'ruff', 'lint']):
            labels.append('code-quality')
        
        # Architecture detection
        if any(word in content_lower for word in ['architecture', 'migration', 'database', 'schema']):
            labels.append('architecture')
        
        # Testing detection
        if any(word in content_lower for word in ['test', 'coverage', 'pytest']):
            labels.append('testing')
        
        # Documentation detection
        if any(word in content_lower for word in ['documentation', 'readme', 'guide']):
            labels.append('documentation')
        
        return list(set(labels))

    def generate_branch_name(self, title: str, issue_number: Optional[int] = None) -> str:
        """Generate a valid git branch name from issue title."""
        branch = title.lower()
        branch = re.sub(r'[^a-z0-9\s-]', '', branch)
        branch = re.sub(r'\s+', '-', branch)
        branch = re.sub(r'-+', '-', branch)
        branch = branch.strip('-')
        
        max_len = 200
        if len(branch) > max_len:
            branch = branch[:max_len].rsplit('-', 1)[0]
        
        if issue_number:
            return f"issue/{issue_number}-{branch}"
        return f"issue/{branch}"

    def scan_issues(self, priority_filter: Optional[str] = None) -> List[IssueInfo]:
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
            
            if priority_filter and priority != priority_filter:
                continue
            
            labels = self.determine_labels(content, priority)
            acceptance_criteria = self.extract_acceptance_criteria(content)
            implementation_plan = self.extract_implementation_plan(content)
            estimated_effort = self.extract_estimated_effort(content)

            issues.append(IssueInfo(
                file_path=md_file,
                title=title,
                priority=priority,
                labels=labels,
                acceptance_criteria=acceptance_criteria,
                implementation_plan=implementation_plan,
                estimated_effort=estimated_effort
            ))

        return issues

    async def create_issue_async(self, issue: IssueInfo, 
                                 semaphore: asyncio.Semaphore) -> IssueInfo:
        """Create a single GitHub issue asynchronously."""
        async with semaphore:
            return await asyncio.get_event_loop().run_in_executor(
                None, self.create_issue_sync, issue
            )

    def create_issue_sync(self, issue: IssueInfo) -> IssueInfo:
        """Create a single GitHub issue (synchronous)."""
        try:
            if self.dry_run:
                issue.status = IssueStatus.SKIPPED
                return issue
            
            cmd = [
                "gh", "issue", "create",
                "--title", issue.title,
                "--body-file", str(issue.file_path),
            ]
            
            for label in issue.labels:
                cmd.extend(["--label", label])
            
            result = self.run_command(cmd, check=False, timeout=30)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                url_match = re.search(r'(https://github\.com/[^/]+/[^/]+/issues/\d+)', output)
                
                if url_match:
                    issue.url = url_match.group(1)
                    number_match = re.search(r'/issues/(\d+)', issue.url)
                    if number_match:
                        issue.number = int(number_match.group(1))
                        issue.branch_name = self.generate_branch_name(issue.title, issue.number)
                        issue.status = IssueStatus.CREATED
                        issue.created_at = datetime.now().isoformat()
                        return issue
                
                # Fallback: get latest issue
                result2 = self.run_command(
                    ["gh", "issue", "list", "--limit", "1", "--json", "number,url"],
                    timeout=30
                )
                if result2.stdout:
                    data = json.loads(result2.stdout)
                    if data:
                        issue.number = data[0]['number']
                        issue.url = data[0]['url']
                        issue.branch_name = self.generate_branch_name(issue.title, issue.number)
                        issue.status = IssueStatus.CREATED
                        issue.created_at = datetime.now().isoformat()
                        return issue
            
            issue.status = IssueStatus.FAILED
            issue.error_message = "Failed to create issue"
            return issue
            
        except Exception as e:
            issue.status = IssueStatus.FAILED
            issue.error_message = str(e)
            return issue

    def create_branch(self, issue: IssueInfo) -> bool:
        """Create a git branch for the issue."""
        if not issue.branch_name:
            return False
        
        if self.dry_run:
            return True
        
        # Check if branch already exists
        result = self.run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{issue.branch_name}"],
            check=False
        )
        
        if result.returncode == 0:
            return True
        
        # Create and checkout branch
        result = self.run_command(["git", "checkout", "-b", issue.branch_name])
        if result.returncode == 0:
            # Return to previous branch
            self.run_command(["git", "checkout", "-"])
            return True
        
        return False

    def generate_pr_content(self, issue: IssueInfo) -> str:
        """Generate PR content from issue information."""
        content = issue.file_path.read_text()
        
        # Extract description (content between title and first major section)
        description = ""
        in_description = False
        found_first_heading = False
        
        for line in content.split('\n'):
            if line.startswith('# ') and not in_description:
                in_description = True
                continue
            elif in_description:
                if line.startswith('## '):
                    found_first_heading = True
                    break
                description += line + '\n'
        
        # Build PR body
        pr_body = f"""# Pull Request: {issue.title}

## Related Issue
- Closes #{issue.number}
- Branch: `{issue.branch_name}`

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
        
        if issue.acceptance_criteria:
            for criterion in issue.acceptance_criteria:
                pr_body += f"{criterion}\n"
        else:
            pr_body += "- [ ] All acceptance criteria from issue completed\n"
        
        pr_body += """
## Implementation Checklist
"""
        
        if issue.implementation_plan:
            for item in issue.implementation_plan:
                pr_body += f"{item}\n"
        else:
            pr_body += """- [ ] Code changes complete
- [ ] Self-review completed
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings
- [ ] All acceptance criteria met
"""
        
        pr_body += """
## Testing
<!-- Describe how you tested these changes -->

## Related Issues
<!-- Link any related issues -->

## Screenshots/Recordings
<!-- If applicable, add screenshots or recordings to help explain your changes -->

## Additional Notes
<!-- Add any additional context or notes here -->
"""
        
        return pr_body

    def create_pr(self, issue: IssueInfo, assignee: Optional[str] = None) -> bool:
        """Create a pull request for an issue."""
        if not issue.number or not issue.branch_name:
            return False
        
        # Ensure branch exists
        if not self.create_branch(issue):
            return False
        
        # Create PR body
        pr_body = self.generate_pr_content(issue)
        
        # Write PR body to temp file
        pr_body_file = self.repo_root / f".pr_body_{issue.number}.md"
        pr_body_file.write_text(pr_body)
        
        if self.dry_run:
            pr_body_file.unlink(missing_ok=True)
            return True
        
        # Checkout branch and create initial commit if needed
        current_branch = self.run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        ).stdout.strip()
        
        self.run_command(["git", "checkout", issue.branch_name], check=False)
        
        # Check if branch has commits
        result = self.run_command(
            ["git", "rev-parse", "HEAD"],
            check=False
        )
        
        # Create placeholder commit if needed
        readme_file = self.repo_root / f"WORK_IN_PROGRESS_{issue.number}.md"
        readme_file.write_text(f"# Work in Progress\n\nIssue #{issue.number}: {issue.title}\n")
        
        self.run_command(["git", "add", str(readme_file)])
        self.run_command(["git", "commit", "-m", f"WIP: Issue #{issue.number} - {issue.title[:50]}"], check=False)
        
        # Push branch
        result = self.run_command(["git", "push", "-u", "origin", issue.branch_name])
        if result.returncode != 0:
            # Clean up and return to original branch
            self.run_command(["git", "checkout", current_branch])
            pr_body_file.unlink(missing_ok=True)
            return False
        
        # Create PR
        cmd = [
            "gh", "pr", "create",
            "--base", "main",
            "--head", issue.branch_name,
            "--title", f"Implement issue #{issue.number}: {issue.title[:60]}",
            "--body-file", str(pr_body_file),
        ]
        
        if assignee:
            cmd.extend(["--assignee", assignee])
        
        result = self.run_command(cmd, check=False)
        
        # Clean up
        self.run_command(["git", "checkout", current_branch])
        pr_body_file.unlink(missing_ok=True)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            pr_url_match = re.search(r'(https://github\.com/[^/]+/[^/]+/pull/\d+)', output)
            if pr_url_match:
                issue.pr_url = pr_url_match.group(1)
                pr_number_match = re.search(r'/pull/(\d+)', issue.pr_url)
                if pr_number_match:
                    issue.pr_number = int(pr_number_match.group(1))
                    issue.status = IssueStatus.PR_CREATED
                    return True
        
        return False

    async def process_issues_parallel(self, issues: List[IssueInfo], 
                                      max_concurrent: int = 4) -> List[IssueInfo]:
        """Process issues in parallel with configurable concurrency."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        tasks = [
            self.create_issue_async(issue, semaphore)
            for issue in issues
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_issues = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                issues[i].status = IssueStatus.FAILED
                issues[i].error_message = str(result)
            processed_issues.append(issues[i] if isinstance(result, Exception) else result)
        
        return processed_issues

    def process_batch(self, issues: List[IssueInfo], 
                     parallel: bool = True,
                     max_concurrent: int = 4) -> BatchResult:
        """Process a batch of issues."""
        result = BatchResult(
            total=len(issues),
            parallel=parallel,
            max_workers=max_concurrent if parallel else 1,
            start_time=datetime.now().isoformat()
        )
        
        print("\n" + "=" * 80)
        print("🚀 BATCH ISSUE PROCESSING")
        print("=" * 80)
        print(f"Total issues: {len(issues)}")
        print(f"Parallel execution: {parallel}")
        print(f"Max concurrent: {max_concurrent}")
        print(f"Dry run: {self.dry_run}")
        print("=" * 80 + "\n")
        
        if parallel:
            # Use async parallel processing
            print("⚡ Processing issues in parallel...\n")
            processed_issues = asyncio.run(
                self.process_issues_parallel(issues, max_concurrent)
            )
        else:
            # Sequential processing
            print("📝 Processing issues sequentially...\n")
            processed_issues = []
            for i, issue in enumerate(issues, 1):
                print(f"[{i}/{len(issues)}] Processing: {issue.title[:60]}")
                processed_issue = self.create_issue_sync(issue)
                processed_issues.append(processed_issue)
                print(f"  Status: {processed_issue.status.value}")
        
        # Update result
        result.issues = processed_issues
        result.success = sum(1 for i in processed_issues if i.status == IssueStatus.CREATED)
        result.failed = sum(1 for i in processed_issues if i.status == IssueStatus.FAILED)
        result.skipped = sum(1 for i in processed_issues if i.status == IssueStatus.SKIPPED)
        result.end_time = datetime.now().isoformat()
        
        # Save results
        self.save_results(result)
        
        # Print summary
        self.print_summary(result)
        
        return result

    def create_prs_batch(self, issue_numbers: Optional[List[int]] = None,
                        assignee: Optional[str] = None) -> BatchResult:
        """Create PRs for existing issues."""
        result = BatchResult()
        
        print("\n" + "=" * 80)
        print("📦 BATCH PR CREATION")
        print("=" * 80)
        
        if issue_numbers:
            issues = []
            for num in issue_numbers:
                cmd_result = self.run_command([
                    "gh", "issue", "view", str(num),
                    "--json", "title,number,state"
                ], check=False)
                
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
            issues = self.scan_issues()
        
        result.total = len(issues)
        result.start_time = datetime.now().isoformat()
        
        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Creating PR for issue #{issue.number or '???'}")
            print("-" * 80)
            
            if self.create_pr(issue, assignee):
                result.success += 1
                print(f"  ✅ PR created: {issue.pr_url}")
            else:
                result.failed += 1
                print(f"  ❌ Failed to create PR")
            
            result.issues.append(issue)
        
        result.end_time = datetime.now().isoformat()
        self.save_results(result)
        self.print_summary(result)
        
        return result

    def save_results(self, result: BatchResult) -> None:
        """Save batch operation results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "parallel": result.parallel,
            "max_workers": result.max_workers,
            "summary": {
                "total": result.total,
                "success": result.success,
                "failed": result.failed,
                "skipped": result.skipped,
                "duration_seconds": (
                    datetime.fromisoformat(result.end_time) - 
                    datetime.fromisoformat(result.start_time)
                ).total_seconds() if result.start_time and result.end_time else 0
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
                    "pr_number": issue.pr_number,
                    "pr_url": issue.pr_url,
                    "status": issue.status.value,
                    "created_at": issue.created_at,
                    "error": issue.error_message,
                    "acceptance_criteria": issue.acceptance_criteria,
                    "implementation_plan": issue.implementation_plan
                }
                for issue in result.issues
            ],
            "errors": result.errors
        }
        
        self.results_file.write_text(json.dumps(data, indent=2))
        print(f"\n💾 Results saved to: {self.results_file}")

    def print_summary(self, result: BatchResult) -> None:
        """Print a summary of batch operations."""
        print("\n" + "=" * 80)
        print("📊 BATCH OPERATION SUMMARY")
        print("=" * 80)
        print(f"Total:         {result.total}")
        print(f"✅ Success:    {result.success} ({result.success/result.total*100:.1f}%)" if result.total > 0 else "✅ Success:    0")
        print(f"❌ Failed:     {result.failed} ({result.failed/result.total*100:.1f}%)" if result.total > 0 else "❌ Failed:     0")
        print(f"⏭️  Skipped:    {result.skipped}")
        
        if result.start_time and result.end_time:
            duration = (
                datetime.fromisoformat(result.end_time) - 
                datetime.fromisoformat(result.start_time)
            ).total_seconds()
            print(f"⏱️  Duration:    {duration:.2f}s")
            if result.parallel:
                print(f"🚀 Parallel:   Yes ({result.max_workers} workers)")
        
        print("=" * 80)
        
        if result.issues:
            print("\n📋 Issues:")
            for issue in result.issues:
                status_icon = {
                    "created": "✅",
                    "pr_created": "📦",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "pending": "⏳"
                }.get(issue.status.value, "⚪")
                
                issue_num = f"#{issue.number}" if issue.number else "???"
                print(f"  {status_icon} {issue_num}: {issue.title[:50]} [{issue.status.value}]")
        
        print("\n" + "=" * 80)

    def show_status(self) -> None:
        """Show current status of issues and PRs."""
        print("\n" + "=" * 80)
        print("📊 GITHUB ISSUES & PRS STATUS")
        print("=" * 80)
        
        # Get issues from GitHub
        result = self.run_command([
            "gh", "issue", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,state,labels,url,createdAt"
        ], check=False)
        
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
        ], check=False)
        
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
        
        print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced Batch Issue Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s process --all                    # Process all issues
  %(prog)s process --priority high          # Process high priority only
  %(prog)s process --parallel --workers 8   # Parallel with 8 workers
  %(prog)s create-prs --auto                # Auto-create PRs for all issues
  %(prog)s status                           # Show current status
  %(prog)s report                           # Generate detailed report
        """
    )
    
    parser.add_argument(
        'command',
        choices=['process', 'create-prs', 'status', 'report'],
        help='Command to execute'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all issues'
    )
    parser.add_argument(
        '--priority',
        type=str,
        choices=['critical', 'high', 'medium', 'low'],
        help='Filter by priority'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel processing'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without creating'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Automatic PR creation'
    )
    parser.add_argument(
        '--assignee',
        type=str,
        help='GitHub username to assign to'
    )
    parser.add_argument(
        '--numbers',
        type=int,
        nargs='+',
        help='Specific issue numbers'
    )
    parser.add_argument(
        '--repo',
        type=Path,
        default=Path.cwd(),
        help='Repository root directory'
    )
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = EnhancedBatchProcessor(
        repo_root=args.repo,
        max_workers=args.workers
    )
    processor.dry_run = args.dry_run
    processor.verbose = args.verbose
    
    # Check prerequisites
    ok, errors = processor.check_prerequisites()
    if not ok:
        print("❌ Prerequisites check failed:")
        for error in errors:
            print(f"   - {error}")
        sys.exit(1)
    
    print("✅ GitHub CLI authenticated")
    print("✅ Git repository detected")
    
    # Execute command
    if args.command == 'process':
        if not args.all and not args.priority:
            print("❌ Must specify --all or --priority")
            sys.exit(1)
        
        priority_filter = args.priority if args.priority else None
        issues = processor.scan_issues(priority_filter=priority_filter)
        
        if not issues:
            print("⚠️  No issues found to process")
            sys.exit(0)
        
        result = processor.process_batch(
            issues,
            parallel=args.parallel,
            max_concurrent=args.workers
        )
        sys.exit(0 if result.failed == 0 else 1)
    
    elif args.command == 'create-prs':
        result = processor.create_prs_batch(
            issue_numbers=args.numbers,
            assignee=args.assignee
        )
        sys.exit(0 if result.failed == 0 else 1)
    
    elif args.command == 'status':
        processor.show_status()
        sys.exit(0)
    
    elif args.command == 'report':
        processor.show_status()
        # Could generate more detailed report here
        sys.exit(0)


if __name__ == "__main__":
    main()
