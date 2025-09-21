"""
Integration testing framework for NornFlow enhancements.

This framework provides tools for testing real external system connectivity
and API interactions. It includes:
- Connection testing utilities
- Mock external system setup
- Environment-based test configuration
- Integration test discovery and execution
"""

import pytest
import os
import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import logging

from enhancements.testing.test_framework import IntegrationTestBase


class IntegrationTestConfig:
    """Configuration manager for integration tests."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load integration test configuration from environment and files."""
        config = {
            "netbox": {
                "enabled": self._is_enabled("NETBOX"),
                "url": os.getenv("TEST_NETBOX_URL"),
                "token": os.getenv("TEST_NETBOX_TOKEN"),
                "ssl_verify": os.getenv("TEST_NETBOX_SSL_VERIFY", "true").lower() == "true"
            },
            "git": {
                "enabled": self._is_enabled("GIT"),
                "repo_path": os.getenv("TEST_GIT_REPO_PATH", "/tmp/test-git-repo"),
                "author_name": os.getenv("TEST_GIT_AUTHOR", "Test Author"),
                "author_email": os.getenv("TEST_GIT_EMAIL", "test@example.com")
            },
            "grafana": {
                "enabled": self._is_enabled("GRAFANA"),
                "url": os.getenv("TEST_GRAFANA_URL"),
                "api_key": os.getenv("TEST_GRAFANA_API_KEY"),
                "ssl_verify": os.getenv("TEST_GRAFANA_SSL_VERIFY", "true").lower() == "true"
            },
            "prometheus": {
                "enabled": self._is_enabled("PROMETHEUS"),
                "url": os.getenv("TEST_PROMETHEUS_URL"),
                "pushgateway_url": os.getenv("TEST_PROMETHEUS_PUSHGATEWAY_URL")
            },
            "infoblox": {
                "enabled": self._is_enabled("INFOBLOX"),
                "url": os.getenv("TEST_INFOBLOX_URL"),
                "username": os.getenv("TEST_INFOBLOX_USER"),
                "password": os.getenv("TEST_INFOBLOX_PASS"),
                "wapi_version": os.getenv("TEST_INFOBLOX_WAPI_VERSION", "v2.12")
            },
            "servicenow": {
                "enabled": self._is_enabled("SERVICENOW"),
                "instance_url": os.getenv("TEST_SERVICENOW_URL"),
                "username": os.getenv("TEST_SERVICENOW_USER"),
                "password": os.getenv("TEST_SERVICENOW_PASS")
            },
            "jira": {
                "enabled": self._is_enabled("JIRA"),
                "server_url": os.getenv("TEST_JIRA_URL"),
                "username": os.getenv("TEST_JIRA_USER"),
                "api_token": os.getenv("TEST_JIRA_TOKEN"),
                "test_project": os.getenv("TEST_JIRA_PROJECT", "TEST")
            }
        }
        
        return config
    
    def _is_enabled(self, service: str) -> bool:
        """Check if integration testing is enabled for a service."""
        return os.getenv(f"TEST_{service}_ENABLED", "false").lower() == "true"
    
    def get_config(self, service: str) -> Dict[str, Any]:
        """Get configuration for a specific service."""
        return self.config.get(service, {})
    
    def is_enabled(self, service: str) -> bool:
        """Check if integration testing is enabled for a service."""
        return self.config.get(service, {}).get("enabled", False)
    
    def get_enabled_services(self) -> List[str]:
        """Get list of enabled services for integration testing."""
        return [service for service, config in self.config.items() if config.get("enabled", False)]


class MockExternalSystems:
    """Mock external systems for integration testing when real systems aren't available."""
    
    @staticmethod
    def setup_mock_netbox():
        """Setup mock NetBox server."""
        from unittest.mock import Mock
        import json
        
        mock_server = Mock()
        
        # Mock device endpoints
        mock_server.get.side_effect = lambda url, **kwargs: MockExternalSystems._create_netbox_response(url)
        mock_server.post.side_effect = lambda url, **kwargs: MockExternalSystems._create_netbox_response(url, method="POST")
        
        return mock_server
    
    @staticmethod
    def _create_netbox_response(url: str, method: str = "GET"):
        """Create mock NetBox API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        if "devices" in url:
            mock_response.json.return_value = {
                "count": 1,
                "results": [
                    {
                        "id": 1,
                        "name": "test-device",
                        "device_type": {"display": "Test Device Type"},
                        "device_role": {"display": "Test Role"},
                        "status": {"value": "active"},
                        "primary_ip4": {"address": "192.168.1.1/24"}
                    }
                ]
            }
        elif "prefixes" in url:
            mock_response.json.return_value = {
                "count": 1,
                "results": [
                    {
                        "id": 1,
                        "prefix": "192.168.1.0/24",
                        "available_ips": ["192.168.1.100", "192.168.1.101"]
                    }
                ]
            }
        
        return mock_response
    
    @staticmethod
    def setup_mock_git_repo(repo_path: str):
        """Setup mock Git repository."""
        import git
        from unittest.mock import Mock
        
        # Create temporary directory if it doesn't exist
        Path(repo_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize real Git repo for testing
        try:
            repo = git.Repo.init(repo_path)
            
            # Create initial commit
            readme_file = Path(repo_path) / "README.md"
            readme_file.write_text("# Test Repository\n")
            repo.index.add(["README.md"])
            repo.index.commit("Initial commit")
            
            return repo
        except Exception:
            # Fall back to mock if Git is not available
            mock_repo = Mock()
            mock_repo.working_dir = repo_path
            mock_repo.active_branch = "main"
            mock_repo.is_dirty.return_value = False
            return mock_repo
    
    @staticmethod
    def setup_mock_api_server(port: int = 8080):
        """Setup mock API server for testing."""
        from unittest.mock import Mock
        
        mock_server = Mock()
        mock_server.url = f"http://localhost:{port}"
        
        # Mock common API responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {}}
        
        mock_server.get.return_value = mock_response
        mock_server.post.return_value = mock_response
        mock_server.put.return_value = mock_response
        mock_server.delete.return_value = mock_response
        
        return mock_server


class IntegrationTestRunner:
    """Runner for integration tests with real or mock external systems."""
    
    def __init__(self):
        self.config = IntegrationTestConfig()
        self.mock_systems = MockExternalSystems()
        self.logger = logging.getLogger(__name__)
    
    def run_connectivity_tests(self) -> Dict[str, Any]:
        """Run connectivity tests for all enabled services."""
        results = {}
        
        for service in self.config.get_enabled_services():
            self.logger.info(f"Testing connectivity to {service}")
            results[service] = self._test_service_connectivity(service)
        
        return results
    
    def _test_service_connectivity(self, service: str) -> Dict[str, Any]:
        """Test connectivity to a specific service."""
        config = self.config.get_config(service)
        
        try:
            if service == "netbox":
                return self._test_netbox_connectivity(config)
            elif service == "git":
                return self._test_git_connectivity(config)
            elif service == "grafana":
                return self._test_grafana_connectivity(config)
            elif service == "prometheus":
                return self._test_prometheus_connectivity(config)
            elif service == "infoblox":
                return self._test_infoblox_connectivity(config)
            elif service == "servicenow":
                return self._test_servicenow_connectivity(config)
            elif service == "jira":
                return self._test_jira_connectivity(config)
            else:
                return {"success": False, "error": f"Unknown service: {service}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_netbox_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test NetBox connectivity."""
        if not config.get("url") or not config.get("token"):
            return {"success": False, "error": "Missing NetBox configuration"}
        
        try:
            from enhancements.integrations.netbox_integration import NetBoxIntegration
            integration = NetBoxIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "NetBox integration not available"}
    
    def _test_git_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Git connectivity."""
        try:
            from enhancements.integrations.git_integration import GitIntegration
            integration = GitIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "Git integration not available"}
    
    def _test_grafana_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Grafana connectivity."""
        if not config.get("url") or not config.get("api_key"):
            return {"success": False, "error": "Missing Grafana configuration"}
        
        try:
            from enhancements.integrations.monitoring_integration import GrafanaIntegration
            integration = GrafanaIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "Grafana integration not available"}
    
    def _test_prometheus_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Prometheus connectivity."""
        if not config.get("url"):
            return {"success": False, "error": "Missing Prometheus configuration"}
        
        try:
            from enhancements.integrations.monitoring_integration import PrometheusIntegration
            integration = PrometheusIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "Prometheus integration not available"}
    
    def _test_infoblox_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Infoblox connectivity."""
        if not all([config.get("url"), config.get("username"), config.get("password")]):
            return {"success": False, "error": "Missing Infoblox configuration"}
        
        try:
            from enhancements.integrations.monitoring_integration import InfobloxIntegration
            integration = InfobloxIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "Infoblox integration not available"}
    
    def _test_servicenow_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test ServiceNow connectivity."""
        if not all([config.get("instance_url"), config.get("username"), config.get("password")]):
            return {"success": False, "error": "Missing ServiceNow configuration"}
        
        try:
            from enhancements.integrations.itsm_integration import ServiceNowIntegration
            integration = ServiceNowIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "ServiceNow integration not available"}
    
    def _test_jira_connectivity(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Jira connectivity."""
        if not all([config.get("server_url"), config.get("username")]):
            return {"success": False, "error": "Missing Jira configuration"}
        
        if not config.get("api_token") and not config.get("password"):
            return {"success": False, "error": "Missing Jira authentication"}
        
        try:
            from enhancements.integrations.itsm_integration import JiraIntegration
            integration = JiraIntegration(config)
            return integration.test_connection()
        except ImportError:
            return {"success": False, "error": "Jira integration not available"}


# Pytest fixtures for integration testing
@pytest.fixture(scope="session")
def integration_config():
    """Provide integration test configuration."""
    return IntegrationTestConfig()

@pytest.fixture(scope="session")
def integration_runner():
    """Provide integration test runner."""
    return IntegrationTestRunner()

@pytest.fixture
def mock_external_systems():
    """Provide mock external systems."""
    return MockExternalSystems()

@pytest.fixture
def temp_git_repo():
    """Provide temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test-repo"
        mock_systems = MockExternalSystems()
        repo = mock_systems.setup_mock_git_repo(str(repo_path))
        yield repo


# Integration test markers
pytestmark = pytest.mark.integration


class TestIntegrationFramework:
    """Test the integration testing framework itself."""
    
    def test_config_loading(self, integration_config):
        """Test integration configuration loading."""
        config = integration_config
        
        # Should have all expected services
        expected_services = ["netbox", "git", "grafana", "prometheus", "infoblox", "servicenow", "jira"]
        for service in expected_services:
            assert service in config.config
            assert "enabled" in config.config[service]
    
    def test_mock_systems_setup(self, mock_external_systems):
        """Test mock external systems setup."""
        # Test NetBox mock
        mock_netbox = mock_external_systems.setup_mock_netbox()
        assert mock_netbox is not None
        
        # Test API server mock
        mock_api = mock_external_systems.setup_mock_api_server()
        assert mock_api is not None
        assert mock_api.url == "http://localhost:8080"
    
    def test_git_repo_setup(self, temp_git_repo):
        """Test Git repository setup for testing."""
        assert temp_git_repo is not None
        
        # Should have basic Git functionality
        if hasattr(temp_git_repo, 'working_dir'):
            assert Path(temp_git_repo.working_dir).exists()
    
    def test_connectivity_runner(self, integration_runner):
        """Test integration connectivity runner."""
        runner = integration_runner
        
        # Should be able to get enabled services
        enabled_services = runner.config.get_enabled_services()
        assert isinstance(enabled_services, list)
        
        # Should be able to run connectivity tests (even if none are enabled)
        results = runner.run_connectivity_tests()
        assert isinstance(results, dict)


# Example integration tests (only run if services are enabled)
class TestRealIntegrations:
    """Integration tests with real external systems."""
    
    @pytest.mark.skipif(not IntegrationTestConfig().is_enabled("netbox"), reason="NetBox integration not enabled")
    def test_netbox_real_integration(self, integration_config):
        """Test real NetBox integration."""
        config = integration_config.get_config("netbox")
        
        from enhancements.integrations.netbox_integration import NetBoxIntegration
        integration = NetBoxIntegration(config)
        
        # Test connection
        result = integration.test_connection()
        assert result["success"] is True
    
    @pytest.mark.skipif(not IntegrationTestConfig().is_enabled("git"), reason="Git integration not enabled")
    def test_git_real_integration(self, integration_config):
        """Test real Git integration."""
        config = integration_config.get_config("git")
        
        from enhancements.integrations.git_integration import GitIntegration
        integration = GitIntegration(config)
        
        # Test connection
        result = integration.test_connection()
        assert result["success"] is True
    
    @pytest.mark.skipif(not IntegrationTestConfig().is_enabled("jira"), reason="Jira integration not enabled")
    def test_jira_real_integration(self, integration_config):
        """Test real Jira integration."""
        config = integration_config.get_config("jira")
        
        from enhancements.integrations.itsm_integration import JiraIntegration
        integration = JiraIntegration(config)
        
        # Test connection
        result = integration.test_connection()
        assert result["success"] is True
