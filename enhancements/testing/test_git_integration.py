"""
Unit tests for Git integration tasks.

Tests all Git integration functionality including:
- Configuration commit operations
- Branch management
- Diff and history operations
- Rollback capabilities
- Drift detection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
import tempfile

from enhancements.integrations.git_integration import (
    GitIntegration,
    git_commit_config,
    git_create_branch,
    git_switch_branch,
    git_get_diff,
    git_rollback_config,
    git_tag_release,
    git_get_history,
    git_detect_drift
)
from enhancements.testing.test_framework import IntegrationTestBase


class TestGitIntegration(IntegrationTestBase):
    """Test Git integration class."""
    
    def test_integration_validation_success(self):
        """Test successful Git integration validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "repo_path": temp_dir,
                "author_name": "Test Author",
                "author_email": "test@example.com"
            }
            
            integration = GitIntegration(config)
            
            assert integration.repo_path == temp_dir
            assert integration.author_name == "Test Author"
            assert integration.author_email == "test@example.com"
            assert integration.default_branch == "main"  # default
            assert integration.config_subdir == "configs"  # default
    
    def test_integration_validation_missing_repo_path(self):
        """Test Git integration validation with missing repo path."""
        config = {"author_name": "Test Author"}
        
        with pytest.raises(ValueError, match="repo_path.*required"):
            GitIntegration(config)
    
    @patch('enhancements.integrations.git_integration.git')
    def test_get_repo_existing(self, mock_git):
        """Test getting existing Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {"repo_path": temp_dir}
            
            mock_repo = Mock()
            mock_repo.heads = ["main"]  # Repository has commits
            mock_git.Repo.return_value = mock_repo
            
            integration = GitIntegration(config)
            repo = integration.get_repo()
            
            mock_git.Repo.assert_called_once_with(Path(temp_dir))
            assert repo == mock_repo
    
    @patch('enhancements.integrations.git_integration.git')
    def test_get_repo_initialize_new(self, mock_git):
        """Test initializing new Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "repo_path": temp_dir,
                "author_name": "Test Author",
                "author_email": "test@example.com"
            }
            
            # Mock repository initialization
            mock_repo = Mock()
            mock_repo.heads = []  # Empty repository
            mock_git.Repo.side_effect = [mock_git.exc.InvalidGitRepositoryError(), mock_repo]
            mock_git.Repo.init.return_value = mock_repo
            
            # Mock Actor for commits
            mock_actor = Mock()
            mock_git.Actor.return_value = mock_actor
            
            integration = GitIntegration(config)
            repo = integration.get_repo()
            
            mock_git.Repo.init.assert_called_once_with(Path(temp_dir))
            mock_repo.index.commit.assert_called_once()
    
    @patch('enhancements.integrations.git_integration.git')
    def test_test_connection_success(self, mock_git):
        """Test successful connection test."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {"repo_path": temp_dir}
            
            mock_repo = Mock()
            mock_repo.working_dir = temp_dir
            mock_repo.active_branch = "main"
            mock_repo.is_dirty.return_value = False
            mock_repo.untracked_files = []
            mock_repo.iter_commits.return_value = ["commit1", "commit2"]
            mock_repo.remotes = []
            
            mock_git.Repo.return_value = mock_repo
            
            integration = GitIntegration(config)
            result = integration.test_connection()
            
            assert result["success"] is True
            assert "Git repository accessible" in result["message"]
            assert result["status"]["current_branch"] == "main"
            assert result["status"]["commit_count"] == 2


class TestGitCommitTasks(IntegrationTestBase):
    """Test Git commit operations."""
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_commit_config_success(self, mock_integration_class, mock_task):
        """Test successful configuration commit."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration.author_name = "Test Author"
        mock_integration.author_email = "test@example.com"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.working_dir = "/tmp/test-repo"
        mock_repo.active_branch = "main"
        
        # Setup mock commit
        mock_commit = Mock()
        mock_commit.hexsha = "abc123def456"
        mock_repo.index.commit.return_value = mock_commit
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Mock Path operations
        with patch('enhancements.integrations.git_integration.Path') as mock_path:
            mock_config_dir = Mock()
            mock_config_file = Mock()
            mock_backup_file = Mock()
            
            mock_path.return_value.__truediv__.return_value = mock_config_dir
            mock_config_dir.__truediv__.side_effect = [mock_config_file, mock_backup_file]
            mock_config_file.exists.return_value = False
            mock_config_file.relative_to.return_value = "configs/test-device/running-config.txt"
            
            # Execute task
            config_content = "hostname test-device\ninterface GigE0/1\n description Test"
            result = git_commit_config(
                mock_task,
                config_content=config_content,
                device_name="test-device",
                commit_message="Test commit"
            )
            
            # Assertions
            self.assert_result_success(result, ["device_name", "commit_hash", "commit_message"])
            assert result.result["device_name"] == "test-device"
            assert result.result["commit_hash"] == "abc123def456"
            assert result.result["commit_message"] == "Test commit"
            
            # Verify file operations
            mock_config_file.write_text.assert_called_once_with(config_content)
            mock_repo.index.add.assert_called_once()
            mock_repo.index.commit.assert_called_once()
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_commit_config_with_backup(self, mock_integration_class, mock_task):
        """Test configuration commit with existing file backup."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_integration.get_repo.return_value = mock_repo
        
        # Mock Path operations with existing file
        with patch('enhancements.integrations.git_integration.Path') as mock_path:
            mock_config_dir = Mock()
            mock_config_file = Mock()
            mock_backup_file = Mock()
            
            mock_path.return_value.__truediv__.return_value = mock_config_dir
            mock_config_dir.__truediv__.side_effect = [mock_config_file, mock_backup_file]
            mock_config_file.exists.return_value = True  # File exists
            mock_backup_file.exists.return_value = True
            
            # Execute task
            result = git_commit_config(mock_task, config_content="new config")
            
            # Verify backup was created
            mock_config_file.rename.assert_called_once_with(mock_backup_file)


class TestGitBranchOperations(IntegrationTestBase):
    """Test Git branch management."""
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_create_branch_success(self, mock_integration_class, mock_task):
        """Test successful branch creation."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.active_branch = "main"
        
        # Setup mock branch
        mock_branch = Mock()
        mock_repo.create_head.return_value = mock_branch
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_create_branch(mock_task, branch_name="feature-branch")
        
        # Assertions
        self.assert_result_success(result, ["branch_name", "current_branch"])
        assert result.result["branch_name"] == "feature-branch"
        
        # Verify branch operations
        mock_repo.create_head.assert_called_once_with("feature-branch")
        mock_branch.checkout.assert_called_once()
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_switch_branch_existing(self, mock_integration_class, mock_task):
        """Test switching to existing branch."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.active_branch = "main"
        mock_repo.git.checkout.return_value = None  # Successful checkout
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_switch_branch(mock_task, branch_name="develop")
        
        # Assertions
        self.assert_result_success(result, ["previous_branch", "current_branch"])
        assert result.result["previous_branch"] == "main"
        
        # Verify checkout
        mock_repo.git.checkout.assert_called_once_with("develop")
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_switch_branch_create_if_missing(self, mock_integration_class, mock_task):
        """Test switching to branch with creation if missing."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.active_branch = "main"
        mock_repo.git.checkout.side_effect = Exception("Branch not found")
        
        # Setup mock branch creation
        mock_branch = Mock()
        mock_repo.create_head.return_value = mock_branch
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_switch_branch(mock_task, branch_name="new-branch", create_if_missing=True)
        
        # Assertions
        self.assert_result_success(result, ["previous_branch", "current_branch", "created"])
        assert result.result["created"] is True
        
        # Verify branch creation
        mock_repo.create_head.assert_called_once_with("new-branch")
        mock_branch.checkout.assert_called_once()


class TestGitHistoryOperations(IntegrationTestBase):
    """Test Git history and diff operations."""
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_get_diff_success(self, mock_integration_class, mock_task):
        """Test successful diff retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository
        mock_repo = Mock()
        mock_repo.git.diff.return_value = "- old line\n+ new line"
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_get_diff(
            mock_task,
            device_name="test-device",
            commit1="abc123",
            commit2="def456"
        )
        
        # Assertions
        self.assert_result_success(result, ["device_name", "commit1", "commit2", "diff"])
        assert result.result["device_name"] == "test-device"
        assert result.result["has_changes"] is True
        assert "old line" in result.result["diff"]
        
        # Verify diff call
        expected_path = "configs/test-device/running-config.txt"
        mock_repo.git.diff.assert_called_once_with("abc123", "def456", expected_path)
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_get_history_success(self, mock_integration_class, mock_task):
        """Test successful history retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository and commits
        mock_commit1 = Mock()
        mock_commit1.hexsha = "abc123def456"
        mock_commit1.message = "First commit"
        mock_commit1.author = "Test Author"
        mock_commit1.committed_datetime = datetime(2024, 1, 1, 12, 0, 0)
        mock_commit1.stats.files = {"file1.txt": {}}
        
        mock_commit2 = Mock()
        mock_commit2.hexsha = "def456ghi789"
        mock_commit2.message = "Second commit"
        mock_commit2.author = "Test Author"
        mock_commit2.committed_datetime = datetime(2024, 1, 2, 12, 0, 0)
        mock_commit2.stats.files = {"file1.txt": {}, "file2.txt": {}}
        
        mock_repo = Mock()
        mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2]
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_get_history(mock_task, device_name="test-device", max_count=5)
        
        # Assertions
        self.assert_result_success(result, ["device_name", "commit_count", "history"])
        assert result.result["device_name"] == "test-device"
        assert result.result["commit_count"] == 2
        
        history = result.result["history"]
        assert len(history) == 2
        assert history[0]["hash"] == "abc123def456"
        assert history[0]["short_hash"] == "abc123de"
        assert history[0]["message"] == "First commit"
        assert history[1]["files_changed"] == 2


class TestGitRollbackAndDrift(IntegrationTestBase):
    """Test Git rollback and drift detection."""
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_rollback_config_success(self, mock_integration_class, mock_task):
        """Test successful configuration rollback."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository and commit
        mock_commit = Mock()
        mock_commit.hexsha = "abc123def456"
        mock_commit.message = "Previous config"
        mock_commit.committed_datetime = datetime(2024, 1, 1, 12, 0, 0)
        
        # Mock tree access for config content
        mock_tree_item = Mock()
        mock_tree_item.data_stream.read.return_value = b"hostname old-device\ninterface GigE0/1"
        mock_commit.tree = {"configs/test-device/running-config.txt": mock_tree_item}
        
        mock_repo = Mock()
        mock_repo.commit.return_value = mock_commit
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task
        result = git_rollback_config(
            mock_task,
            device_name="test-device",
            commit_hash="abc123def456"
        )
        
        # Assertions
        self.assert_result_success(result, ["device_name", "target_commit", "config_content"])
        assert result.result["device_name"] == "test-device"
        assert result.result["target_commit"] == "abc123def456"
        assert "hostname old-device" in result.result["config_content"]
    
    @patch('enhancements.integrations.git_integration.GitIntegration')
    def test_git_detect_drift_with_changes(self, mock_integration_class, mock_task):
        """Test drift detection with configuration changes."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.config_subdir = "configs"
        mock_integration_class.return_value = mock_integration
        
        # Setup mock repository and commit
        mock_commit = Mock()
        mock_tree_item = Mock()
        git_config = "hostname test-device\ninterface GigE0/1\n description Original"
        mock_tree_item.data_stream.read.return_value = git_config.encode('utf-8')
        mock_commit.tree = {"configs/test-device/running-config.txt": mock_tree_item}
        
        mock_repo = Mock()
        mock_repo.commit.return_value = mock_commit
        
        mock_integration.get_repo.return_value = mock_repo
        
        # Execute task with different current config
        current_config = "hostname test-device\ninterface GigE0/1\n description Modified"
        result = git_detect_drift(
            mock_task,
            current_config=current_config,
            device_name="test-device"
        )
        
        # Assertions
        self.assert_result_success(result, ["device_name", "drift_detected", "drift_percentage"])
        assert result.result["device_name"] == "test-device"
        assert result.result["drift_detected"] is True
        assert result.result["added_lines"] == 1
        assert result.result["removed_lines"] == 1
        assert result.result["drift_percentage"] > 0
