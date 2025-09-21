"""
Git Integration for NornFlow.

This module provides comprehensive Git integration for configuration version control:
- Configuration backup to Git repositories
- Change tracking and commit history
- Branch management for different environments
- Configuration drift detection
- Automated rollback capabilities

Git integration enables proper version control for network configurations,
providing audit trails, change tracking, and rollback capabilities.
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
from nornir.core.task import Task, Result
import logging
import os
import subprocess

from . import (
    register_integration,
    BaseIntegration,
    require_dependency,
    validate_required_field,
    IntegrationError,
    DependencyError
)

logger = logging.getLogger(__name__)


@register_integration(
    name="git",
    description="Git version control integration for configuration management",
    dependencies=["GitPython"],
    tasks=[
        "git_commit_config",
        "git_create_branch",
        "git_switch_branch",
        "git_get_diff",
        "git_rollback_config",
        "git_tag_release",
        "git_get_history",
        "git_detect_drift"
    ]
)
class GitIntegration(BaseIntegration):
    """Git integration class."""
    
    def validate_config(self) -> None:
        """Validate Git configuration."""
        self.repo_path = validate_required_field(self.config.get("repo_path"), "repo_path")
        self.author_name = self.config.get("author_name", "NornFlow Automation")
        self.author_email = self.config.get("author_email", "nornflow@automation.local")
        self.default_branch = self.config.get("default_branch", "main")
        self.config_subdir = self.config.get("config_subdir", "configs")
        
        # Ensure repo path exists
        repo_path = Path(self.repo_path)
        if not repo_path.exists():
            repo_path.mkdir(parents=True, exist_ok=True)
    
    @require_dependency("git", "git")
    def get_repo(self):
        """Get Git repository object."""
        import git
        
        repo_path = Path(self.repo_path)
        
        try:
            # Try to open existing repository
            repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            # Initialize new repository
            repo = git.Repo.init(repo_path)
            
            # Create initial commit if repository is empty
            if not repo.heads:
                # Create .gitignore
                gitignore_path = repo_path / ".gitignore"
                gitignore_path.write_text("*.tmp\n*.log\n__pycache__/\n")
                
                # Create README
                readme_path = repo_path / "README.md"
                readme_path.write_text("# Network Configuration Repository\n\nManaged by NornFlow\n")
                
                # Add and commit initial files
                repo.index.add([".gitignore", "README.md"])
                repo.index.commit(
                    "Initial commit",
                    author=git.Actor(self.author_name, self.author_email)
                )
        
        return repo
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Git repository access."""
        try:
            repo = self.get_repo()
            
            # Get repository status
            status_info = {
                "repo_path": str(repo.working_dir),
                "current_branch": str(repo.active_branch),
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "commit_count": len(list(repo.iter_commits())),
                "remotes": [str(remote) for remote in repo.remotes]
            }
            
            return {
                "success": True,
                "message": f"Git repository accessible at {repo.working_dir}",
                "status": status_info
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to access Git repository: {str(e)}"
            }


# Git Task Functions

@require_dependency("git", "git")
def git_commit_config(
    task: Task,
    config_content: str,
    device_name: Optional[str] = None,
    commit_message: Optional[str] = None,
    branch: Optional[str] = None,
    file_extension: str = ".txt",
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Commit device configuration to Git repository.
    
    Args:
        task: Nornir task object
        config_content: Configuration content to commit
        device_name: Device name (defaults to task.host.name)
        commit_message: Custom commit message
        branch: Branch to commit to (defaults to current branch)
        file_extension: File extension for config file
        git_config: Git configuration
        
    Returns:
        Result containing commit information
    """
    device_name = device_name or task.host.name
    config = git_config or getattr(task.host, "git_config", {})
    
    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()
        
        # Switch to specified branch if provided
        if branch and str(repo.active_branch) != branch:
            try:
                repo.git.checkout(branch)
            except Exception:
                # Create new branch if it doesn't exist
                repo.git.checkout("-b", branch)
        
        # Create config directory structure
        config_dir = Path(repo.working_dir) / integration.config_subdir / device_name
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Write configuration file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_file = config_dir / f"running-config{file_extension}"
        backup_file = config_dir / f"backup_{timestamp}{file_extension}"
        
        # Create backup of existing config if it exists
        if config_file.exists():
            config_file.rename(backup_file)
        
        # Write new configuration
        config_file.write_text(config_content)
        
        # Add to Git index
        repo.index.add([str(config_file.relative_to(repo.working_dir))])
        
        # Create commit message
        if not commit_message:
            commit_message = f"Update configuration for {device_name}"
        
        # Commit changes
        import git
        commit = repo.index.commit(
            commit_message,
            author=git.Actor(integration.author_name, integration.author_email)
        )
        
        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "commit_hash": commit.hexsha,
                "commit_message": commit_message,
                "branch": str(repo.active_branch),
                "config_file": str(config_file),
                "backup_file": str(backup_file) if backup_file.exists() else None,
                "timestamp": timestamp
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to commit config to Git: {str(e)}"
        )


@require_dependency("git", "git")
def git_create_branch(
    task: Task,
    branch_name: str,
    from_branch: Optional[str] = None,
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create a new Git branch.
    
    Args:
        task: Nornir task object
        branch_name: Name of the new branch
        from_branch: Branch to create from (defaults to current branch)
        git_config: Git configuration
        
    Returns:
        Result containing branch creation status
    """
    config = git_config or getattr(task.host, "git_config", {})
    
    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()
        
        # Switch to source branch if specified
        if from_branch and str(repo.active_branch) != from_branch:
            repo.git.checkout(from_branch)
        
        # Create new branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        
        return Result(
            host=task.host,
            result={
                "branch_name": branch_name,
                "from_branch": from_branch or str(repo.active_branch),
                "current_branch": str(repo.active_branch),
                "message": f"Created and switched to branch '{branch_name}'"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create Git branch: {str(e)}"
        )


@require_dependency("git", "git")
def git_switch_branch(
    task: Task,
    branch_name: str,
    create_if_missing: bool = False,
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Switch to a Git branch.
    
    Args:
        task: Nornir task object
        branch_name: Name of the branch to switch to
        create_if_missing: Create branch if it doesn't exist
        git_config: Git configuration
        
    Returns:
        Result containing branch switch status
    """
    config = git_config or getattr(task.host, "git_config", {})
    
    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()
        
        current_branch = str(repo.active_branch)
        
        try:
            # Try to switch to existing branch
            repo.git.checkout(branch_name)
        except Exception as e:
            if create_if_missing:
                # Create new branch
                new_branch = repo.create_head(branch_name)
                new_branch.checkout()
            else:
                raise e
        
        return Result(
            host=task.host,
            result={
                "previous_branch": current_branch,
                "current_branch": str(repo.active_branch),
                "branch_name": branch_name,
                "created": create_if_missing and current_branch != branch_name,
                "message": f"Switched to branch '{branch_name}'"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to switch Git branch: {str(e)}"
        )


@require_dependency("git", "git")
def git_get_diff(
    task: Task,
    device_name: Optional[str] = None,
    commit1: Optional[str] = None,
    commit2: Optional[str] = "HEAD",
    file_path: Optional[str] = None,
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get diff between Git commits for device configuration.
    
    Args:
        task: Nornir task object
        device_name: Device name (defaults to task.host.name)
        commit1: First commit (defaults to previous commit)
        commit2: Second commit (defaults to HEAD)
        file_path: Specific file path to diff
        git_config: Git configuration
        
    Returns:
        Result containing diff information
    """
    device_name = device_name or task.host.name
    config = git_config or getattr(task.host, "git_config", {})
    
    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()
        
        # Determine file path if not provided
        if not file_path:
            file_path = f"{integration.config_subdir}/{device_name}/running-config.txt"
        
        # Get commits
        if not commit1:
            # Use previous commit
            commits = list(repo.iter_commits(paths=file_path, max_count=2))
            if len(commits) < 2:
                return Result(
                    host=task.host,
                    result={
                        "device_name": device_name,
                        "file_path": file_path,
                        "diff": "",
                        "message": "Not enough commits for diff"
                    }
                )
            commit1 = commits[1].hexsha
            commit2 = commits[0].hexsha
        
        # Get diff
        diff = repo.git.diff(commit1, commit2, file_path)
        
        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "file_path": file_path,
                "commit1": commit1,
                "commit2": commit2,
                "diff": diff,
                "has_changes": bool(diff.strip())
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get Git diff: {str(e)}"
        )


@require_dependency("git", "git")
def git_rollback_config(
    task: Task,
    device_name: Optional[str] = None,
    commit_hash: Optional[str] = None,
    steps_back: int = 1,
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Rollback device configuration to a previous Git commit.

    Args:
        task: Nornir task object
        device_name: Device name (defaults to task.host.name)
        commit_hash: Specific commit to rollback to
        steps_back: Number of commits to go back (if commit_hash not provided)
        git_config: Git configuration

    Returns:
        Result containing rollback information and config content
    """
    device_name = device_name or task.host.name
    config = git_config or getattr(task.host, "git_config", {})

    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()

        # Determine file path
        file_path = f"{integration.config_subdir}/{device_name}/running-config.txt"

        # Get target commit
        if commit_hash:
            target_commit = repo.commit(commit_hash)
        else:
            # Get commit N steps back
            commits = list(repo.iter_commits(paths=file_path, max_count=steps_back + 1))
            if len(commits) <= steps_back:
                return Result(
                    host=task.host,
                    failed=True,
                    result=f"Not enough commits to go back {steps_back} steps"
                )
            target_commit = commits[steps_back]

        # Get configuration content from target commit
        try:
            config_content = target_commit.tree[file_path].data_stream.read().decode('utf-8')
        except KeyError:
            return Result(
                host=task.host,
                failed=True,
                result=f"Configuration file not found in commit {target_commit.hexsha}"
            )

        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "target_commit": target_commit.hexsha,
                "commit_message": target_commit.message.strip(),
                "commit_date": target_commit.committed_datetime.isoformat(),
                "config_content": config_content,
                "file_path": file_path,
                "steps_back": steps_back if not commit_hash else None
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to rollback Git config: {str(e)}"
        )


@require_dependency("git", "git")
def git_tag_release(
    task: Task,
    tag_name: str,
    tag_message: Optional[str] = None,
    commit: Optional[str] = "HEAD",
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create a Git tag for a release.

    Args:
        task: Nornir task object
        tag_name: Name of the tag
        tag_message: Tag message (defaults to tag name)
        commit: Commit to tag (defaults to HEAD)
        git_config: Git configuration

    Returns:
        Result containing tag information
    """
    config = git_config or getattr(task.host, "git_config", {})

    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()

        # Create tag
        import git
        tag = repo.create_tag(
            tag_name,
            ref=commit,
            message=tag_message or f"Release {tag_name}",
            force=False
        )

        return Result(
            host=task.host,
            result={
                "tag_name": tag_name,
                "tag_message": tag_message or f"Release {tag_name}",
                "commit": tag.commit.hexsha,
                "commit_message": tag.commit.message.strip(),
                "created_date": datetime.now().isoformat()
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create Git tag: {str(e)}"
        )


@require_dependency("git", "git")
def git_get_history(
    task: Task,
    device_name: Optional[str] = None,
    max_count: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None,
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get Git commit history for device configuration.

    Args:
        task: Nornir task object
        device_name: Device name (defaults to task.host.name)
        max_count: Maximum number of commits to return
        since: Start date for history (ISO format)
        until: End date for history (ISO format)
        git_config: Git configuration

    Returns:
        Result containing commit history
    """
    device_name = device_name or task.host.name
    config = git_config or getattr(task.host, "git_config", {})

    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()

        # Determine file path
        file_path = f"{integration.config_subdir}/{device_name}/running-config.txt"

        # Build commit iteration parameters
        kwargs = {"paths": file_path, "max_count": max_count}
        if since:
            kwargs["since"] = since
        if until:
            kwargs["until"] = until

        # Get commits
        commits = list(repo.iter_commits(**kwargs))

        history = []
        for commit in commits:
            commit_info = {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
                "files_changed": len(commit.stats.files)
            }
            history.append(commit_info)

        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "file_path": file_path,
                "commit_count": len(history),
                "history": history,
                "parameters": {
                    "max_count": max_count,
                    "since": since,
                    "until": until
                }
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get Git history: {str(e)}"
        )


@require_dependency("git", "git")
def git_detect_drift(
    task: Task,
    current_config: str,
    device_name: Optional[str] = None,
    reference_commit: Optional[str] = "HEAD",
    git_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Detect configuration drift by comparing current config with Git version.

    Args:
        task: Nornir task object
        current_config: Current device configuration
        device_name: Device name (defaults to task.host.name)
        reference_commit: Git commit to compare against
        git_config: Git configuration

    Returns:
        Result containing drift detection results
    """
    device_name = device_name or task.host.name
    config = git_config or getattr(task.host, "git_config", {})

    try:
        integration = GitIntegration(config)
        repo = integration.get_repo()

        # Determine file path
        file_path = f"{integration.config_subdir}/{device_name}/running-config.txt"

        # Get reference configuration from Git
        try:
            commit = repo.commit(reference_commit)
            git_config_content = commit.tree[file_path].data_stream.read().decode('utf-8')
        except KeyError:
            return Result(
                host=task.host,
                failed=True,
                result=f"Configuration file not found in commit {reference_commit}"
            )

        # Compare configurations
        current_lines = current_config.strip().split('\n')
        git_lines = git_config_content.strip().split('\n')

        # Simple line-by-line comparison
        drift_detected = current_lines != git_lines

        # Calculate basic diff statistics
        added_lines = []
        removed_lines = []

        current_set = set(current_lines)
        git_set = set(git_lines)

        added_lines = list(current_set - git_set)
        removed_lines = list(git_set - current_set)

        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "drift_detected": drift_detected,
                "reference_commit": reference_commit,
                "current_lines": len(current_lines),
                "git_lines": len(git_lines),
                "added_lines": len(added_lines),
                "removed_lines": len(removed_lines),
                "added_content": added_lines[:10],  # First 10 added lines
                "removed_content": removed_lines[:10],  # First 10 removed lines
                "drift_percentage": round((len(added_lines) + len(removed_lines)) / max(len(git_lines), 1) * 100, 2)
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to detect Git drift: {str(e)}"
        )
