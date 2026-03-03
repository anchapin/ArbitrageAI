#!/usr/bin/env python3
"""
Advanced Batch Workflow Orchestrator

This script provides advanced workflow automation for GitHub issues and PRs:
1. Phased rollout (create issues in batches by priority)
2. Automatic branch management
3. PR template generation with implementation checklists
4. Progress tracking and reporting
5. Integration with GitHub Projects

Usage:
    python scripts/batch_orchestrator.py phase critical    # Create critical issues
    python scripts/batch_orchestrator.py phase high        # Create high priority issues
    python scripts/batch_orchestrator.py phase all         # Create all issues
    python scripts/batch_orchestrator.py progress          # Show progress report
    python scripts/batch_orchestrator.py report            # Generate detailed report
"""

import subprocess
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum
import yaml


class Priority(Enum):
    """Issue priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Phase(Enum):
    """Implementation phases."""
    PHASE_1 = "phase1"  # Critical Security
    PHASE_2 = "phase2"  # High Priority Code Quality
    PHASE_3 = "phase3"  # Medium Priority Performance
    ALL = "all"


@dataclass
class IssueMetadata:
    """Metadata for an issue."""
    file_path: Path
    title: str
    priority: str
    phase: str
    estimated_effort: str
    labels: List[str]
    number: Optional[int] = None
    url: Optional[str] = None
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None
    assigned_to: Optional[str] = None


@dataclass
class PhasePlan:
    """Plan for a phase."""
    phase: Phase
    name: str
    description: str
    duration_weeks: int
    issues: List[IssueMetadata] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)


class BatchOrchestrator:
    """Orchestrates batch issue and PR creation with phased rollout."""

    PHASE_DEFINITIONS = {
        Phase.PHASE_1: PhasePlan(
            phase=Phase.PHASE_1,
            name="Critical Security",
            description="Address critical security vulnerabilities",
            duration_weeks=2,
            success_criteria=[
                "Zero critical security vulnerabilities",
                "All secrets securely generated",
                "Production validation enforced",
                "Security audit passed"
            ]
        ),
        Phase.PHASE_2: PhasePlan(
            phase=Phase.PHASE_2,
            name="High Priority Code Quality",
            description="Fix code quality and architecture issues",
            duration_weeks=4,
            success_criteria=[
                "Zero ruff errors (F821, B904, etc.)",
                "All files under 500 lines",
                "Database migrations working",
                "Code quality grade: A"
            ]
        ),
        Phase.PHASE_3: PhasePlan(
            phase=Phase.PHASE_3,
            name="Medium Priority Performance",
            description="Performance optimizations and improvements",
            duration_weeks=3,
            success_criteria=[
                "Rate limiting works in distributed systems",
                "Query performance <100ms",
                "No N+1 queries",
                "Performance benchmarks met"
            ]
        )
    }

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.issues_dir = self.repo_root / ".github" / "ISSUES"
        self.results_dir = self.repo_root / ".github" / "batch_results"
        self.results_dir.mkdir(exist_ok=True)
        self.dry_run = False
        self.verbose = False

    def run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=check
            )
            if self.verbose and result.stdout:
                print(f"  {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            if self.verbose:
                print(f"  Command failed: {e}")
                print(f"  stderr: {e.stderr}")
            if check:
                raise
            return e

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("🔍 Checking prerequisites...")

        # Check git
        result = self.run_command(["git", "rev-parse", "--git-dir"], check=False)
        if result.returncode != 0:
            print("❌ Not in a git repository")
            return False
        print("✅ Git repository detected")

        # Check GitHub CLI
        result = self.run_command(["gh", "auth", "status"], check=False)
        if result.returncode != 0:
            print("❌ GitHub CLI not authenticated. Run: gh auth login")
            return False
        print("✅ GitHub CLI authenticated")

        # Check issues directory
        if not self.issues_dir.exists():
            print(f"❌ Issues directory not found: {self.issues_dir}")
            return False
        print(f"✅ Issues directory found: {self.issues_dir}")

        return True

    def parse_front_matter(self, content: str) -> Dict:
        """Parse YAML front matter."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                return {}
        return {}

    def extract_metadata(self, md_file: Path) -> IssueMetadata:
        """Extract metadata from an issue file."""
        content = md_file.read_text()
        front_matter = self.parse_front_matter(content)

        # Extract title
        title = front_matter.get('title', '')
        if not title:
            match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if match:
                title = match.group(1).strip()[:80]

        # Extract priority
        priority = front_matter.get('priority', 'medium').lower()

        # Determine phase based on priority
        if priority == 'critical':
            phase = 'phase1'
        elif priority == 'high':
            phase = 'phase2'
        else:
            phase = 'phase3'

        # Extract estimated effort
        effort = front_matter.get('estimated_effort', 'Unknown')

        # Determine labels
        labels = ['qaqc-review', priority]

        # Infer additional labels from content
        content_lower = content.lower()
        if any(word in content_lower for word in ['security', 'vulnerability', 'rce']):
            labels.append('security')
        if any(word in content_lower for word in ['performance', 'optimization', 'redis']):
            labels.append('performance')
        if any(word in content_lower for word in ['refactor', 'code quality']):
            labels.append('code-quality')
        if any(word in content_lower for word in ['architecture', 'migration', 'database']):
            labels.append('architecture')

        return IssueMetadata(
            file_path=md_file,
            title=title,
            priority=priority,
            phase=phase,
            estimated_effort=effort,
            labels=list(set(labels))
        )

    def scan_issues(self, priority_filter: Optional[str] = None) -> List[IssueMetadata]:
        """Scan issues directory with optional priority filter."""
        if not self.issues_dir.exists():
            return []

        issues = []
        for md_file in sorted(self.issues_dir.glob("*.md")):
            if md_file.name == "README.md":
                continue

            metadata = self.extract_metadata(md_file)

            if priority_filter and metadata.priority != priority_filter:
                continue

            issues.append(metadata)

        return issues

    def get_phase_issues(self, phase: Phase) -> List[IssueMetadata]:
        """Get issues for a specific phase."""
        if phase == Phase.ALL:
            return self.scan_issues()

        phase_plan = self.PHASE_DEFINITIONS.get(phase)
        if not phase_plan:
            return []

        # Map phase to priority
        priority_map = {
            Phase.PHASE_1: 'critical',
            Phase.PHASE_2: 'high',
            Phase.PHASE_3: 'medium'
        }

        priority = priority_map.get(phase)
        if not priority:
            return []

        return self.scan_issues(priority_filter=priority)

    def create_issue(self, issue: IssueMetadata) -> bool:
        """Create a single GitHub issue."""
        print(f"  📝 Creating: {issue.title[:60]}...")

        if self.dry_run:
            print(f"    [DRY RUN] Would create issue with labels: {', '.join(issue.labels)}")
            issue.status = "dry-run"
            return True

        # Build gh command
        cmd = [
            "gh", "issue", "create",
            "--title", issue.title,
            "--body-file", str(issue.file_path),
        ]

        for label in issue.labels:
            cmd.extend(["--label", label])

        result = self.run_command(cmd, check=False)
        if result.returncode == 0:
            # Get issue number
            output = result.stdout.strip()
            url_match = re.search(r'(https://github\.com/[^/]+/[^/]+/issues/\d+)', output)
            if url_match:
                issue.url = url_match.group(1)
                number_match = re.search(r'/issues/(\d+)', issue.url)
                if number_match:
                    issue.number = int(number_match.group(1))
                    issue.branch_name = f"issue/{issue.number}-{self.slugify(issue.title)}"
                    issue.status = "created"
                    issue.created_at = datetime.now().isoformat()
                    print(f"    ✅ Created: {issue.url}")
                    return True

            # Fallback
            result2 = self.run_command(["gh", "issue", "list", "--limit", "1", "--json", "number,url"])
            if result2.stdout:
                data = json.loads(result2.stdout)
                if data:
                    issue.number = data[0]['number']
                    issue.url = data[0]['url']
                    issue.branch_name = f"issue/{issue.number}-{self.slugify(issue.title)}"
                    issue.status = "created"
                    issue.created_at = datetime.now().isoformat()
                    print(f"    ✅ Created: #{issue.number}")
                    return True

        print(f"    ❌ Failed")
        issue.status = "failed"
        return False

    def slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        text = re.sub(r'\s+', '-', text)
        text = re.sub(r'-+', '-', text)
        return text.strip('-')[:100]

    def create_branch(self, issue: IssueMetadata) -> bool:
        """Create git branch for issue."""
        if not issue.branch_name:
            return False

        print(f"  🌿 Creating branch: {issue.branch_name}")

        if self.dry_run:
            return True

        # Check if exists
        result = self.run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{issue.branch_name}"],
            check=False
        )
        if result.returncode == 0:
            print(f"    ⚠️  Branch exists")
            return True

        # Create branch
        result = self.run_command(["git", "checkout", "-b", issue.branch_name])
        if result.returncode == 0:
            print(f"    ✅ Branch created")
            self.run_command(["git", "checkout", "-"])
            return True

        return False

    def create_pr_template(self, issue: IssueMetadata) -> Path:
        """Create PR template for issue."""
        pr_dir = self.repo_root / ".github" / "PR_TEMPLATES"
        pr_dir.mkdir(exist_ok=True)

        template_file = pr_dir / f"PR-{issue.number}.md"

        # Extract acceptance criteria from issue
        content = issue.file_path.read_text()
        acceptance_criteria = []
        in_criteria = False
        for line in content.split('\n'):
            if 'Acceptance Criteria' in line:
                in_criteria = True
            elif in_criteria:
                if line.startswith('- [ ]'):
                    acceptance_criteria.append(line.strip())
                elif line.startswith('#') and acceptance_criteria:
                    break

        template = f"""# Pull Request: {issue.title}

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

## Acceptance Criteria
<!-- From the original issue -->
{chr(10).join(acceptance_criteria) if acceptance_criteria else "- [ ] Add criteria from issue"}

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

## Additional Notes
<!-- Add any additional context -->
"""

        template_file.write_text(template)
        return template_file

    def execute_phase(self, phase: Phase) -> Dict:
        """Execute a phase of issue creation."""
        phase_plan = self.PHASE_DEFINITIONS[phase]

        print("\n" + "=" * 80)
        print(f"🚀 EXECUTING {phase_plan.name.upper()}")
        print("=" * 80)
        print(f"Description: {phase_plan.description}")
        print(f"Duration: {phase_plan.duration_weeks} weeks")
        print(f"Dry Run: {self.dry_run}")
        print("=" * 80)

        issues = self.get_phase_issues(phase)
        print(f"\n📋 Found {len(issues)} issues for this phase:\n")

        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue.title[:60]}")
            print(f"     Priority: {issue.priority}, Effort: {issue.estimated_effort}")

        print("\n" + "-" * 80)
        print("📝 CREATING ISSUES")
        print("-" * 80 + "\n")

        results = {
            "phase": phase.value,
            "phase_name": phase_plan.name,
            "total": len(issues),
            "success": 0,
            "failed": 0,
            "issues": []
        }

        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Processing: {issue.file_path.name}")
            print("-" * 80)

            if self.create_issue(issue):
                results["success"] += 1
                self.create_branch(issue)
                self.create_pr_template(issue)
            else:
                results["failed"] += 1

            results["issues"].append({
                "file": str(issue.file_path),
                "title": issue.title,
                "priority": issue.priority,
                "number": issue.number,
                "url": issue.url,
                "branch": issue.branch_name,
                "status": issue.status
            })

        # Save phase results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"phase_{phase.value}_{timestamp}.json"
        results_file.write_text(json.dumps(results, indent=2))

        # Print summary
        print("\n" + "=" * 80)
        print(f"📊 PHASE {phase_plan.name.upper()} SUMMARY")
        print("=" * 80)
        print(f"Total:    {results['total']}")
        print(f"✅ Success: {results['success']} ({results['success']/results['total']*100:.1f}%)")
        print(f"❌ Failed:  {results['failed']} ({results['failed']/results['total']*100:.1f}%)")
        print(f"\n💾 Results saved to: {results_file}")
        print("=" * 80)

        return results

    def show_progress(self) -> None:
        """Show progress report."""
        print("\n" + "=" * 80)
        print("📊 PROGRESS REPORT")
        print("=" * 80)

        # Get issues from GitHub
        result = self.run_command([
            "gh", "issue", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,state,labels,url,createdAt,closedAt"
        ], check=False)

        if result.returncode != 0:
            print("❌ Failed to fetch issues")
            return

        issues = json.loads(result.stdout)
        total = len(issues)
        open_count = sum(1 for i in issues if i['state'] == 'open')
        closed_count = sum(1 for i in issues if i['state'] == 'closed')

        # Group by priority
        priority_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for issue in issues:
            labels = [l['name'] for l in issue['labels']]
            for priority in priority_counts.keys():
                if priority in labels:
                    priority_counts[priority] += 1
                    break

        print(f"\n📈 Overall Statistics:")
        print(f"  Total Issues:    {total}")
        print(f"  🟢 Open:         {open_count}")
        print(f"  🔒 Closed:       {closed_count}")
        print(f"  Progress:        {closed_count/total*100:.1f}%" if total > 0 else "  Progress:        N/A")

        print(f"\n📊 By Priority:")
        print(f"  🔴 Critical:     {priority_counts['critical']}")
        print(f"  🟡 High:         {priority_counts['high']}")
        print(f"  🟢 Medium:       {priority_counts['medium']}")
        print(f"  ⚪ Low:          {priority_counts['low']}")

        # Phase progress
        print(f"\n📅 Phase Progress:")
        for phase, plan in self.PHASE_DEFINITIONS.items():
            phase_issues = [i for i in issues if plan.name.lower() in i['title'].lower()]
            phase_closed = sum(1 for i in phase_issues if i['state'] == 'closed')
            progress_bar = self._progress_bar(phase_closed, len(phase_issues) if phase_issues else 1)
            print(f"  {phase.value.upper():12} {progress_bar} {phase_closed}/{len(phase_issues) if phase_issues else 0}")

        print("\n" + "=" * 80)

    def _progress_bar(self, current: int, total: int, width: int = 30) -> str:
        """Generate a text progress bar."""
        if total == 0:
            return "[--------------------] 0%"
        percentage = current / total
        filled = int(width * percentage)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {percentage*100:.0f}%"

    def generate_report(self, output_file: Optional[Path] = None) -> None:
        """Generate detailed progress report."""
        timestamp = datetime.now()

        report = f"""# Batch Issues Progress Report

**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Repository:** {self.repo_root.name}

---

## Executive Summary

This report provides an overview of the QA/QC batch issue creation and progress.

---

## Phase Status

"""

        for phase, plan in self.PHASE_DEFINITIONS.items():
            report += f"""### {plan.name} ({phase.value})

**Description:** {plan.description}
**Target Duration:** {plan.duration_weeks} weeks

**Success Criteria:**
"""
            for criterion in plan.success_criteria:
                report += f"- [ ] {criterion}\n"

            report += "\n"

        # Add issues list
        result = self.run_command([
            "gh", "issue", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,state,labels,url,createdAt"
        ], check=False)

        if result.returncode == 0:
            issues = json.loads(result.stdout)
            report += f"\n## Issues ({len(issues)} total)\n\n"

            for issue in issues:
                labels = [l['name'] for l in issue['labels']]
                priority = next((l for l in labels if l in ['critical', 'high', 'medium']), 'medium')
                icon = {'critical': '🔴', 'high': '🟡', 'medium': '🟢'}.get(priority, '⚪')
                status_icon = "✅" if issue['state'] == 'closed' else "🔄"

                report += f"{status_icon}{icon} #{issue['number']}: {issue['title']}\n"
                report += f"   - State: {issue['state']}\n"
                report += f"   - Created: {issue['createdAt'][:10]}\n"
                report += f"   - URL: {issue['url']}\n\n"

        if output_file:
            output_file.write_text(report)
            print(f"✅ Report saved to: {output_file}")
        else:
            print(report)

    def run(self, phase: str, dry_run: bool = False, verbose: bool = False) -> int:
        """Run the orchestrator."""
        self.dry_run = dry_run
        self.verbose = verbose

        if not self.check_prerequisites():
            return 1

        phase_map = {
            'critical': Phase.PHASE_1,
            'high': Phase.PHASE_2,
            'medium': Phase.PHASE_3,
            'phase1': Phase.PHASE_1,
            'phase2': Phase.PHASE_2,
            'phase3': Phase.PHASE_3,
            'all': Phase.ALL
        }

        phase_enum = phase_map.get(phase.lower())
        if not phase_enum:
            print(f"❌ Unknown phase: {phase}")
            print(f"Valid phases: {', '.join(phase_map.keys())}")
            return 1

        if phase_enum == Phase.ALL:
            # Execute all phases
            for p in [Phase.PHASE_1, Phase.PHASE_2, Phase.PHASE_3]:
                self.execute_phase(p)
        else:
            self.execute_phase(phase_enum)

        return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch Workflow Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s phase critical     # Execute Phase 1 (Critical Security)
  %(prog)s phase high         # Execute Phase 2 (High Priority)
  %(prog)s phase all          # Execute all phases
  %(prog)s progress           # Show progress report
  %(prog)s report             # Generate detailed report
  %(prog)s phase critical --dry-run  # Preview without creating
        """
    )

    parser.add_argument(
        'command',
        choices=['phase', 'progress', 'report'],
        help='Command to execute'
    )
    parser.add_argument(
        'phase',
        nargs='?',
        choices=['critical', 'high', 'medium', 'phase1', 'phase2', 'phase3', 'all'],
        help='Phase to execute (for phase command)'
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
        '--output',
        type=Path,
        help='Output file for report'
    )
    parser.add_argument(
        '--repo',
        type=Path,
        default=Path.cwd(),
        help='Repository root'
    )

    args = parser.parse_args()

    orchestrator = BatchOrchestrator(repo_root=args.repo)

    if args.command == 'phase':
        if not args.phase:
            print("❌ Phase required for 'phase' command")
            return 1
        sys.exit(orchestrator.run(args.phase, args.dry_run, args.verbose))

    elif args.command == 'progress':
        orchestrator.show_progress()
        sys.exit(0)

    elif args.command == 'report':
        orchestrator.generate_report(args.output)
        sys.exit(0)


if __name__ == "__main__":
    main()
