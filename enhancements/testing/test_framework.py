"""
Testing Framework for NornFlow Enhancements.

This module provides comprehensive testing utilities and base classes
for testing NornFlow enhancements including:
- Integration tasks testing
- Network automation tasks testing
- Workflow validation testing
- Mock utilities for external systems

The framework follows pytest patterns and integrates with the existing
NornFlow testing infrastructure.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import tempfile
import json
import yaml
from datetime import datetime

from nornir.core.task import Task, Result
from nornir.core.inventory import Host, Inventory
from nornir.core import Nornir


class MockHost:
    """Mock host for testing purposes."""
    
    def __init__(self, name: str = "test-device", **kwargs):
        self.name = name
        self.hostname = kwargs.get("hostname", "192.168.1.1")
        self.platform = kwargs.get("platform", "cisco_ios")
        self.port = kwargs.get("port", 22)
        self.username = kwargs.get("username", "admin")
        self.password = kwargs.get("password", "password")
        self.data = kwargs.get("data", {})
        
        # Add common host data
        self.data.setdefault("site", "test-site")
        self.data.setdefault("role", "router")
        self.data.setdefault("location", {"building": "DC1", "rack": "R01"})


class MockTask:
    """Mock task for testing purposes."""
    
    def __init__(self, host: Optional[MockHost] = None, **kwargs):
        self.host = host or MockHost()
        self.is_dry_run_value = kwargs.get("dry_run", False)
        self.nornir = kwargs.get("nornir", Mock())
        
    def is_dry_run(self) -> bool:
        """Return dry run status."""
        return self.is_dry_run_value


class IntegrationTestBase:
    """Base class for integration testing."""
    
    @pytest.fixture
    def mock_task(self):
        """Create a mock task for testing."""
        return MockTask()
    
    @pytest.fixture
    def mock_host(self):
        """Create a mock host for testing."""
        return MockHost()
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return {
            "url": "https://test.example.com",
            "username": "test_user",
            "password": "test_pass",
            "timeout": 30,
            "ssl_verify": True
        }
    
    def create_mock_response(self, status_code: int = 200, json_data: Optional[Dict] = None):
        """Create a mock HTTP response."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {}
        mock_response.text = json.dumps(json_data or {})
        mock_response.raise_for_status = Mock()
        
        if status_code >= 400:
            from requests.exceptions import HTTPError
            mock_response.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
        
        return mock_response
    
    def assert_result_success(self, result: Result, expected_keys: Optional[List[str]] = None):
        """Assert that a result is successful and contains expected keys."""
        assert isinstance(result, Result)
        assert not result.failed, f"Task failed: {result.result}"
        assert result.result is not None
        
        if expected_keys:
            for key in expected_keys:
                assert key in result.result, f"Missing key '{key}' in result: {result.result}"
    
    def assert_result_failed(self, result: Result, expected_error: Optional[str] = None):
        """Assert that a result failed with expected error."""
        assert isinstance(result, Result)
        assert result.failed, f"Expected task to fail but it succeeded: {result.result}"
        
        if expected_error:
            assert expected_error in str(result.result), f"Expected error '{expected_error}' not found in: {result.result}"


class NetworkTaskTestBase:
    """Base class for network task testing."""
    
    @pytest.fixture
    def mock_task(self):
        """Create a mock task for network testing."""
        return MockTask()
    
    @pytest.fixture
    def mock_netmiko_connection(self):
        """Create a mock netmiko connection."""
        mock_conn = Mock()
        mock_conn.send_command.return_value = "Mock command output"
        mock_conn.send_config_set.return_value = "Mock config output"
        mock_conn.is_alive.return_value = True
        mock_conn.disconnect.return_value = None
        return mock_conn
    
    @pytest.fixture
    def sample_config_content(self):
        """Sample configuration content for testing."""
        return """
hostname test-device
!
interface GigabitEthernet0/1
 description Test Interface
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
!
end
        """.strip()
    
    def create_mock_api_response(self, success: bool = True, data: Optional[Dict] = None):
        """Create a mock API response for network devices."""
        if success:
            return {
                "status": "success",
                "data": data or {"message": "Operation completed successfully"},
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": data or {"message": "Operation failed"},
                "timestamp": datetime.now().isoformat()
            }


class WorkflowTestBase:
    """Base class for workflow testing."""
    
    @pytest.fixture
    def temp_workflow_dir(self):
        """Create a temporary directory for workflow testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_workflow(self):
        """Sample workflow for testing."""
        return {
            "workflow": {
                "name": "Test Workflow",
                "description": "A test workflow for validation",
                "vars": {
                    "test_var": "test_value",
                    "timeout": 30
                },
                "tasks": [
                    {
                        "name": "test_task_1",
                        "args": {"message": "Hello World"}
                    },
                    {
                        "name": "test_task_2",
                        "args": {"input": "{{ test_var }}"},
                        "depends_on": "test_task_1"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def conditional_workflow(self):
        """Workflow with conditional logic for testing."""
        return {
            "workflow": {
                "name": "Conditional Test Workflow",
                "description": "Tests conditional execution",
                "vars": {
                    "deploy_config": True,
                    "environment": "test"
                },
                "tasks": [
                    {
                        "name": "backup_config",
                        "args": {"backup_dir": "/tmp/backups"}
                    },
                    {
                        "name": "deploy_config",
                        "args": {"config_file": "test.conf"},
                        "when": "{{ deploy_config }}",
                        "depends_on": "backup_config"
                    },
                    {
                        "name": "validate_config",
                        "args": {"validation_commands": ["show version"]},
                        "when": "{{ environment == 'production' }}",
                        "depends_on": "deploy_config"
                    }
                ]
            }
        }
    
    @pytest.fixture
    def loop_workflow(self):
        """Workflow with loop constructs for testing."""
        return {
            "workflow": {
                "name": "Loop Test Workflow",
                "description": "Tests loop execution",
                "vars": {
                    "interfaces": ["GigE0/1", "GigE0/2", "GigE0/3"],
                    "vlans": [100, 200, 300]
                },
                "tasks": [
                    {
                        "name": "configure_interface",
                        "args": {
                            "interface": "{{ item }}",
                            "description": "Configured by automation"
                        },
                        "loop": "{{ interfaces }}"
                    },
                    {
                        "name": "create_vlan",
                        "args": {
                            "vlan_id": "{{ item }}",
                            "name": "VLAN_{{ item }}"
                        },
                        "with_items": "{{ vlans }}",
                        "depends_on": "configure_interface"
                    }
                ]
            }
        }
    
    def create_workflow_file(self, workflow_dir: Path, workflow_data: Dict, filename: str = "test_workflow.yaml"):
        """Create a workflow file for testing."""
        workflow_file = workflow_dir / filename
        with open(workflow_file, 'w') as f:
            yaml.dump(workflow_data, f, default_flow_style=False)
        return workflow_file
    
    def assert_workflow_valid(self, workflow_data: Dict):
        """Assert that a workflow is valid."""
        assert "workflow" in workflow_data
        workflow = workflow_data["workflow"]
        assert "name" in workflow
        assert "tasks" in workflow
        assert len(workflow["tasks"]) > 0


class MockIntegrationAPIs:
    """Mock APIs for integration testing."""
    
    @staticmethod
    def mock_netbox_api():
        """Create a mock NetBox API."""
        mock_api = Mock()
        
        # Mock device operations
        mock_device = Mock()
        mock_device.id = 123
        mock_device.name = "test-device"
        mock_device.device_type = "Cisco ISR 4321"
        mock_device.device_role = "Router"
        mock_device.status = "active"
        mock_device.primary_ip4 = "192.168.1.1"
        mock_device.config_context = {"ntp_servers": ["10.0.0.1"], "dns_servers": ["8.8.8.8"]}
        
        mock_api.dcim.devices.get.return_value = mock_device
        mock_api.dcim.devices.filter.return_value = [mock_device]
        
        # Mock IP operations
        mock_ip = Mock()
        mock_ip.address = "192.168.1.100/24"
        mock_api.ipam.ip_addresses.create.return_value = mock_ip
        
        return mock_api
    
    @staticmethod
    def mock_git_repo():
        """Create a mock Git repository."""
        mock_repo = Mock()
        
        # Mock commit operations
        mock_commit = Mock()
        mock_commit.hexsha = "abc123def456"
        mock_commit.message = "Test commit"
        mock_commit.committed_datetime = datetime.now()
        
        mock_repo.index.commit.return_value = mock_commit
        mock_repo.active_branch = "main"
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        
        return mock_repo
    
    @staticmethod
    def mock_requests_session():
        """Create a mock requests session."""
        mock_session = Mock()
        
        # Default successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {}}
        mock_response.text = '{"status": "success", "data": {}}'
        
        mock_session.get.return_value = mock_response
        mock_session.post.return_value = mock_response
        mock_session.put.return_value = mock_response
        mock_session.delete.return_value = mock_response
        
        return mock_session


# Pytest fixtures for global use
@pytest.fixture
def integration_test_base():
    """Provide integration test base class."""
    return IntegrationTestBase()

@pytest.fixture
def network_task_test_base():
    """Provide network task test base class."""
    return NetworkTaskTestBase()

@pytest.fixture
def workflow_test_base():
    """Provide workflow test base class."""
    return WorkflowTestBase()

@pytest.fixture
def mock_apis():
    """Provide mock APIs for testing."""
    return MockIntegrationAPIs()
