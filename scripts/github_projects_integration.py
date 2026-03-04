#!/usr/bin/env python3
"""
GitHub Projects Integration for Batch Issues

This module provides integration with GitHub Projects (beta):
1. Add issues to projects automatically
2. Set custom field values (priority, status, effort)
3. Track progress in project boards
4. Generate project-based reports

Usage:
    python scripts/github_projects_integration.py add-issue 123 --project "QA/QC"
    python scripts/github_projects_integration.py sync --project "QA/QC"
    python scripts/github_projects_integration.py status --project "QA/QC"
"""

import subprocess
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import yaml


@dataclass
class ProjectField:
    """GitHub Projects field definition."""
    id: str
    name: str
    data_type: str  # TEXT, NUMBER, SINGLE_SELECT, ITERATION, DATE
    options: List[str] = field(default_factory=list)


@dataclass
class ProjectItem:
    """Item in a GitHub Project."""
    id: str
    content_id: str
    content_type: str  # ISSUE, PULL_REQUEST
    title: str
    number: int
    status: str
    fields: Dict[str, str] = field(default_factory=dict)


class GitHubProjectsManager:
    """Manages GitHub Projects integration."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.config_file = self.repo_root / ".github" / "projects_config.yaml"
        self.cache_file = self.repo_root / ".github" / "projects_cache.json"
        self.dry_run = False
        self.verbose = False

    def run_command(self, cmd: List[str], check: bool = True,
                    timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a shell command."""
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
        except subprocess.TimeoutExpired as e:
            raise subprocess.TimeoutExpired(cmd, timeout) from e
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return e

    def check_auth(self) -> bool:
        """Check if GitHub CLI is authenticated with project scopes."""
        result = self.run_command(["gh", "auth", "status"], check=False)
        if result.returncode != 0:
            return False
        
        # Check if projects extension is installed
        result = self.run_command(["gh", "project", "--help"], check=False)
        if result.returncode != 0:
            print("⚠️  GitHub Projects extension not installed.")
            print("   Install with: gh extension install github/gh-project")
            return False
        
        return True

    def get_project_id(self, project_name: str) -> Optional[str]:
        """Get project ID by name."""
        # Try to get from cache first
        cache = self._load_cache()
        if project_name in cache.get('projects', {}):
            return cache['projects'][project_name]
        
        # Query GitHub API via gh CLI
        result = self.run_command([
            "gh", "project", "list",
            "--json", "number,title,id",
            "--limit", "100"
        ], check=False)
        
        if result.returncode != 0:
            return None
        
        projects = json.loads(result.stdout)
        for project in projects:
            if project['title'] == project_name or str(project['number']) == project_name:
                # Cache the result
                cache.setdefault('projects', {})[project_name] = project['id']
                self._save_cache(cache)
                return project['id']
        
        return None

    def get_project_fields(self, project_id: str) -> List[ProjectField]:
        """Get project fields."""
        result = self.run_command([
            "gh", "project", "field-list", project_id,
            "--json", "id,name,dataType,options"
        ], check=False)
        
        if result.returncode != 0:
            return []
        
        fields_data = json.loads(result.stdout)
        fields = []
        
        for field_data in fields_data:
            fields.append(ProjectField(
                id=field_data['id'],
                name=field_data['name'],
                data_type=field_data.get('dataType', 'TEXT'),
                options=field_data.get('options', [])
            ))
        
        return fields

    def add_issue_to_project(self, issue_number: int, project_name: str,
                            field_values: Optional[Dict[str, str]] = None) -> bool:
        """Add an issue to a project."""
        project_id = self.get_project_id(project_name)
        if not project_id:
            print(f"❌ Project not found: {project_name}")
            return False
        
        if self.dry_run:
            print(f"🔮 [DRY RUN] Would add issue #{issue_number} to project '{project_name}'")
            if field_values:
                print(f"   Fields: {field_values}")
            return True
        
        # Add issue to project
        result = self.run_command([
            "gh", "project", "item-add", project_id,
            "--url", f"https://github.com/{self._get_repo_full_name()}/issues/{issue_number}"
        ], check=False)
        
        if result.returncode != 0:
            print(f"❌ Failed to add issue #{issue_number} to project")
            if self.verbose:
                print(f"   Error: {result.stderr}")
            return False
        
        # Get item ID
        item_id = self._get_item_id(project_id, issue_number)
        if not item_id:
            print(f"⚠️  Could not get item ID for issue #{issue_number}")
            return True  # Issue was added, but can't set fields
        
        # Set field values
        if field_values:
            fields = self.get_project_fields(project_id)
            for field_name, field_value in field_values.items():
                field_def = next((f for f in fields if f.name == field_name), None)
                if field_def:
                    self._set_item_field(project_id, item_id, field_def, field_value)
        
        print(f"✅ Added issue #{issue_number} to project '{project_name}'")
        return True

    def _get_item_id(self, project_id: str, issue_number: int) -> Optional[str]:
        """Get project item ID for an issue."""
        result = self.run_command([
            "gh", "project", "item-list", project_id,
            "--json", "id,contentNumber,contentTypeName"
        ], check=False)
        
        if result.returncode != 0:
            return None
        
        items = json.loads(result.stdout)
        for item in items:
            if (item.get('contentNumber') == issue_number and 
                item.get('contentTypeName') == 'ISSUE'):
                return item['id']
        
        return None

    def _set_item_field(self, project_id: str, item_id: str, 
                       field_def: ProjectField, value: str) -> bool:
        """Set a field value for a project item."""
        if self.dry_run:
            print(f"   Setting {field_def.name} = {value}")
            return True
        
        cmd = [
            "gh", "project", "item-edit", project_id,
            "--id", item_id,
            "--field-id", field_def.id,
            "--text", value
        ]
        
        result = self.run_command(cmd, check=False)
        if result.returncode != 0:
            if self.verbose:
                print(f"   ⚠️  Failed to set field {field_def.name}: {result.stderr}")
            return False
        
        return True

    def _get_repo_full_name(self) -> str:
        """Get full repository name (owner/repo)."""
        result = self.run_command([
            "gh", "repo", "view", "--json", "nameWithOwner"
        ], check=False)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('nameWithOwner', '')
        
        # Fallback: parse from git remote
        result = self.run_command([
            "git", "remote", "get-url", "origin"
        ], check=False)
        
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.startswith('https://github.com/'):
                return url.replace('https://github.com/', '').replace('.git', '')
            elif url.startswith('git@github.com:'):
                return url.replace('git@github.com:', '').replace('.git', '')
        
        return ""

    def sync_issues_to_project(self, project_name: str, 
                               priority_field: str = "Priority",
                               status_field: str = "Status") -> Dict[str, Any]:
        """Sync all QA/QC issues to a project."""
        project_id = self.get_project_id(project_name)
        if not project_id:
            return {"success": False, "error": f"Project not found: {project_name}"}
        
        # Get all QA/QC issues
        result = self.run_command([
            "gh", "issue", "list",
            "--label", "qaqc-review",
            "--limit", "100",
            "--json", "number,title,labels,state"
        ], check=False)
        
        if result.returncode != 0:
            return {"success": False, "error": "Failed to fetch issues"}
        
        issues = json.loads(result.stdout)
        fields = self.get_project_fields(project_id)
        
        stats = {
            "total": len(issues),
            "added": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0
        }
        
        print(f"\n🔄 Syncing {len(issues)} issues to project '{project_name}'...\n")
        
        for issue in issues:
            number = issue['number']
            title = issue['title']
            labels = [l['name'] for l in issue['labels']]
            state = issue['state']
            
            # Determine priority from labels
            priority = next((l for l in labels if l in ['critical', 'high', 'medium', 'low']), 'medium')
            
            # Determine status
            status = "Done" if state == 'closed' else "In Progress"
            
            field_values = {}
            if any(f.name == priority_field for f in fields):
                field_values[priority_field] = priority.capitalize()
            if any(f.name == status_field for f in fields):
                field_values[status_field] = status
            
            # Check if already in project
            item_id = self._get_item_id(project_id, number)
            if item_id:
                # Update existing item
                if field_values:
                    for field_name, field_value in field_values.items():
                        field_def = next((f for f in fields if f.name == field_name), None)
                        if field_def:
                            self._set_item_field(project_id, item_id, field_def, field_value)
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                # Add to project
                if self.add_issue_to_project(number, project_name, field_values):
                    stats["added"] += 1
                else:
                    stats["failed"] += 1
        
        return {
            "success": True,
            "stats": stats,
            "project_id": project_id
        }

    def get_project_status(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get project status overview."""
        project_id = self.get_project_id(project_name)
        if not project_id:
            return None
        
        result = self.run_command([
            "gh", "project", "item-list", project_id,
            "--json", "id,contentNumber,contentTitle,fields"
        ], check=False)
        
        if result.returncode != 0:
            return None
        
        items = json.loads(result.stdout)
        
        # Group by status
        status_groups = {}
        for item in items:
            # Try to get status from fields
            status = "Unknown"
            for field_data in item.get('fields', []):
                if field_data.get('name') == 'Status':
                    status = field_data.get('value', 'Unknown')
                    break
            
            status_groups.setdefault(status, []).append({
                "number": item.get('contentNumber'),
                "title": item.get('contentTitle'),
                "id": item.get('id')
            })
        
        return {
            "project_name": project_name,
            "project_id": project_id,
            "total_items": len(items),
            "by_status": status_groups
        }

    def _load_cache(self) -> Dict:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text())
            except:
                return {}
        return {}

    def _save_cache(self, cache: Dict) -> None:
        """Save cache to file."""
        self.cache_file.write_text(json.dumps(cache, indent=2))

    def generate_project_report(self, project_name: str) -> str:
        """Generate a detailed project report."""
        status = self.get_project_status(project_name)
        if not status:
            return "❌ Could not fetch project status"
        
        report = f"""# Project Status Report: {project_name}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Project ID:** {status['project_id']}
**Total Items:** {status['total_items']}

---

## Status Breakdown

"""
        
        for status_name, items in status['by_status'].items():
            report += f"### {status_name} ({len(items)})\n\n"
            for item in items:
                report += f"- #{item['number']}: {item['title']}\n"
            report += "\n"
        
        report += """
---

## Next Steps

1. Review items in "Todo" status
2. Ensure all high-priority items are assigned
3. Update status fields as work progresses
"""
        
        return report


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="GitHub Projects Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s add-issue 123 --project "QA/QC"
  %(prog)s add-issue 123 --project "QA/QC" --fields Priority=High Status="In Progress"
  %(prog)s sync --project "QA/QC"
  %(prog)s status --project "QA/QC"
  %(prog)s report --project "QA/QC"
        """
    )
    
    parser.add_argument(
        'command',
        choices=['add-issue', 'sync', 'status', 'report'],
        help='Command to execute'
    )
    parser.add_argument(
        'issue_number',
        type=int,
        nargs='?',
        help='Issue number (for add-issue)'
    )
    parser.add_argument(
        '--project',
        type=str,
        required=True,
        help='Project name or number'
    )
    parser.add_argument(
        '--fields',
        type=str,
        nargs='+',
        help='Field values (format: FieldName=Value)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without making changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--repo',
        type=Path,
        default=Path.cwd(),
        help='Repository root'
    )
    
    args = parser.parse_args()
    
    manager = GitHubProjectsManager(repo_root=args.repo)
    manager.dry_run = args.dry_run
    manager.verbose = args.verbose
    
    if not manager.check_auth():
        print("❌ GitHub CLI not authenticated or Projects extension not installed")
        print("\nTo fix:")
        print("1. Run: gh auth login")
        print("2. Install extension: gh extension install github/gh-project")
        sys.exit(1)
    
    if args.command == 'add-issue':
        if not args.issue_number:
            print("❌ Issue number required for add-issue command")
            sys.exit(1)
        
        # Parse field values
        field_values = {}
        if args.fields:
            for field_str in args.fields:
                if '=' in field_str:
                    key, value = field_str.split('=', 1)
                    field_values[key] = value
        
        success = manager.add_issue_to_project(
            args.issue_number,
            args.project,
            field_values
        )
        sys.exit(0 if success else 1)
    
    elif args.command == 'sync':
        result = manager.sync_issues_to_project(args.project)
        if result.get('success'):
            stats = result['stats']
            print(f"\n✅ Sync complete!")
            print(f"   Added: {stats['added']}")
            print(f"   Updated: {stats['updated']}")
            print(f"   Failed: {stats['failed']}")
            print(f"   Skipped: {stats['skipped']}")
            sys.exit(0)
        else:
            print(f"❌ Sync failed: {result.get('error')}")
            sys.exit(1)
    
    elif args.command == 'status':
        status = manager.get_project_status(args.project)
        if status:
            print(f"\n📊 Project Status: {status['project_name']}")
            print(f"   Total Items: {status['total_items']}")
            print(f"\n   By Status:")
            for status_name, items in status['by_status'].items():
                print(f"   - {status_name}: {len(items)} items")
            sys.exit(0)
        else:
            print("❌ Could not fetch project status")
            sys.exit(1)
    
    elif args.command == 'report':
        report = manager.generate_project_report(args.project)
        print(report)
        
        # Save to file
        report_file = args.repo / ".github" / f"project_report_{args.project.replace(' ', '_')}.md"
        report_file.write_text(report)
        print(f"\n💾 Report saved to: {report_file}")
        sys.exit(0)


if __name__ == "__main__":
    main()
