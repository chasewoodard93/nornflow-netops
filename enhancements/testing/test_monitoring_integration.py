"""
Unit tests for monitoring integration tasks.

Tests all monitoring platform integrations including:
- Grafana dashboard and alert management
- Prometheus metrics and querying
- Infoblox DNS/DHCP/IPAM operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from enhancements.integrations.monitoring_integration import (
    GrafanaIntegration,
    PrometheusIntegration,
    InfobloxIntegration,
    grafana_create_dashboard,
    grafana_silence_alert,
    prometheus_query,
    prometheus_push_metrics,
    infoblox_get_next_ip,
    infoblox_create_host_record
)
from enhancements.testing.test_framework import IntegrationTestBase


class TestGrafanaIntegration(IntegrationTestBase):
    """Test Grafana integration class."""
    
    def test_integration_validation_success(self):
        """Test successful Grafana integration validation."""
        config = {
            "url": "https://grafana.example.com",
            "api_key": "test-api-key-123"
        }
        
        integration = GrafanaIntegration(config)
        
        assert integration.url == "https://grafana.example.com"
        assert integration.api_key == "test-api-key-123"
        assert integration.timeout == 30  # default
        assert integration.ssl_verify is True  # default
    
    def test_integration_validation_missing_url(self):
        """Test Grafana integration validation with missing URL."""
        config = {"api_key": "test-key"}
        
        with pytest.raises(ValueError, match="url.*required"):
            GrafanaIntegration(config)
    
    def test_integration_validation_missing_api_key(self):
        """Test Grafana integration validation with missing API key."""
        config = {"url": "https://grafana.example.com"}
        
        with pytest.raises(ValueError, match="api_key.*required"):
            GrafanaIntegration(config)
    
    def test_get_headers(self):
        """Test Grafana API headers generation."""
        config = {
            "url": "https://grafana.example.com",
            "api_key": "test-key"
        }
        
        integration = GrafanaIntegration(config)
        headers = integration.get_headers()
        
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
    
    @patch('enhancements.integrations.monitoring_integration.requests')
    def test_test_connection_success(self, mock_requests):
        """Test successful Grafana connection test."""
        config = {
            "url": "https://grafana.example.com",
            "api_key": "test-key"
        }
        
        mock_response = self.create_mock_response(200, {
            "version": "9.5.0",
            "database": "ok"
        })
        mock_requests.get.return_value = mock_response
        
        integration = GrafanaIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to Grafana" in result["message"]
        assert result["version"] == "9.5.0"
        assert result["database"] == "ok"
    
    @patch('enhancements.integrations.monitoring_integration.requests')
    def test_test_connection_failure(self, mock_requests):
        """Test Grafana connection test failure."""
        config = {
            "url": "https://grafana.example.com",
            "api_key": "invalid-key"
        }
        
        mock_response = self.create_mock_response(401)
        mock_requests.get.return_value = mock_response
        
        integration = GrafanaIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is False
        assert "401" in result["message"]


class TestGrafanaTasks(IntegrationTestBase):
    """Test Grafana task functions."""
    
    @patch('enhancements.integrations.monitoring_integration.GrafanaIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    @patch('enhancements.integrations.monitoring_integration.handle_api_response')
    def test_grafana_create_dashboard_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful dashboard creation."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.url = "https://grafana.example.com"
        mock_integration.get_headers.return_value = {"Authorization": "Bearer test-key"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(200)
        mock_requests.post.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = {
            "id": 123,
            "uid": "dashboard-uid",
            "url": "/d/dashboard-uid/test-dashboard",
            "version": 1,
            "status": "success"
        }
        
        # Execute task
        dashboard_config = {
            "title": "Test Dashboard",
            "panels": [{"title": "Test Panel", "type": "graph"}]
        }
        result = grafana_create_dashboard(mock_task, dashboard_config=dashboard_config)
        
        # Assertions
        self.assert_result_success(result, ["dashboard_id", "dashboard_uid", "dashboard_url"])
        assert result.result["dashboard_id"] == 123
        assert result.result["dashboard_uid"] == "dashboard-uid"
        assert result.result["status"] == "success"
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "dashboards/db" in call_args[0][0]
    
    @patch('enhancements.integrations.monitoring_integration.GrafanaIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    @patch('enhancements.integrations.monitoring_integration.handle_api_response')
    def test_grafana_silence_alert_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful alert silencing."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.url = "https://grafana.example.com"
        mock_integration.get_headers.return_value = {"Authorization": "Bearer test-key"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(200)
        mock_requests.post.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = {"silenceID": "silence-123"}
        
        # Execute task
        result = grafana_silence_alert(
            mock_task,
            alert_name="test-alert",
            duration_minutes=60,
            comment="Maintenance window"
        )
        
        # Assertions
        self.assert_result_success(result, ["silence_id", "alert_name", "duration_minutes"])
        assert result.result["silence_id"] == "silence-123"
        assert result.result["alert_name"] == "test-alert"
        assert result.result["duration_minutes"] == 60
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "silences" in call_args[0][0]


class TestPrometheusIntegration(IntegrationTestBase):
    """Test Prometheus integration class."""
    
    def test_integration_validation_success(self):
        """Test successful Prometheus integration validation."""
        config = {
            "url": "https://prometheus.example.com",
            "pushgateway_url": "https://pushgateway.example.com"
        }
        
        integration = PrometheusIntegration(config)
        
        assert integration.url == "https://prometheus.example.com"
        assert integration.pushgateway_url == "https://pushgateway.example.com"
        assert integration.timeout == 30  # default
        assert integration.ssl_verify is True  # default
    
    def test_integration_validation_missing_url(self):
        """Test Prometheus integration validation with missing URL."""
        config = {}
        
        with pytest.raises(ValueError, match="url.*required"):
            PrometheusIntegration(config)
    
    @patch('enhancements.integrations.monitoring_integration.requests')
    def test_test_connection_success(self, mock_requests):
        """Test successful Prometheus connection test."""
        config = {"url": "https://prometheus.example.com"}
        
        mock_response = self.create_mock_response(200)
        mock_requests.get.return_value = mock_response
        
        integration = PrometheusIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to Prometheus" in result["message"]


class TestPrometheusTasks(IntegrationTestBase):
    """Test Prometheus task functions."""
    
    @patch('enhancements.integrations.monitoring_integration.PrometheusIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    @patch('enhancements.integrations.monitoring_integration.handle_api_response')
    def test_prometheus_query_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful Prometheus query."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.url = "https://prometheus.example.com"
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(200)
        mock_requests.get.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": {"instance": "localhost:9090"}, "value": [1640995200, "1"]}
                ]
            }
        }
        
        # Execute task
        result = prometheus_query(mock_task, query="up")
        
        # Assertions
        self.assert_result_success(result, ["query", "status", "data", "result_type"])
        assert result.result["query"] == "up"
        assert result.result["status"] == "success"
        assert result.result["result_type"] == "vector"
        assert result.result["result_count"] == 1
        
        # Verify API call
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        assert "query" in call_args[1]["params"]
    
    @patch('enhancements.integrations.monitoring_integration.PrometheusIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    def test_prometheus_push_metrics_success(self, mock_requests, mock_integration_class, mock_task):
        """Test successful metrics push to Pushgateway."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.pushgateway_url = "https://pushgateway.example.com"
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(200)
        mock_requests.post.return_value = mock_response
        
        # Execute task
        metrics = {
            "nornflow_task_duration_seconds": 45.2,
            "nornflow_task_success": 1,
            "nornflow_devices_processed": 10
        }
        result = prometheus_push_metrics(
            mock_task,
            job_name="nornflow_automation",
            metrics=metrics,
            instance="test-instance"
        )
        
        # Assertions
        self.assert_result_success(result, ["job_name", "instance", "metrics_pushed", "metrics"])
        assert result.result["job_name"] == "nornflow_automation"
        assert result.result["instance"] == "test-instance"
        assert result.result["metrics_pushed"] == 3
        assert "nornflow_task_duration_seconds" in result.result["metrics"]
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "nornflow_automation" in call_args[0][0]
        assert "test-instance" in call_args[0][0]


class TestInfobloxIntegration(IntegrationTestBase):
    """Test Infoblox integration class."""
    
    def test_integration_validation_success(self):
        """Test successful Infoblox integration validation."""
        config = {
            "url": "https://infoblox.example.com",
            "username": "admin",
            "password": "password123"
        }
        
        integration = InfobloxIntegration(config)
        
        assert integration.url == "https://infoblox.example.com"
        assert integration.username == "admin"
        assert integration.password == "password123"
        assert integration.wapi_version == "v2.12"  # default
        assert integration.timeout == 30  # default
    
    def test_integration_validation_missing_credentials(self):
        """Test Infoblox integration validation with missing credentials."""
        config = {"url": "https://infoblox.example.com"}
        
        with pytest.raises(ValueError, match="username.*required"):
            InfobloxIntegration(config)
    
    def test_get_auth(self):
        """Test Infoblox authentication tuple generation."""
        config = {
            "url": "https://infoblox.example.com",
            "username": "admin",
            "password": "secret"
        }
        
        integration = InfobloxIntegration(config)
        auth = integration.get_auth()
        
        assert auth == ("admin", "secret")
    
    @patch('enhancements.integrations.monitoring_integration.requests')
    def test_test_connection_success(self, mock_requests):
        """Test successful Infoblox connection test."""
        config = {
            "url": "https://infoblox.example.com",
            "username": "admin",
            "password": "password"
        }
        
        mock_response = self.create_mock_response(200, [{"name": "grid1"}])
        mock_requests.get.return_value = mock_response
        
        integration = InfobloxIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to Infoblox" in result["message"]
        assert result["grid_count"] == 1


class TestInfobloxTasks(IntegrationTestBase):
    """Test Infoblox task functions."""
    
    @patch('enhancements.integrations.monitoring_integration.InfobloxIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    @patch('enhancements.integrations.monitoring_integration.handle_api_response')
    def test_infoblox_get_next_ip_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful next IP retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.url = "https://infoblox.example.com"
        mock_integration.wapi_version = "v2.12"
        mock_integration.get_auth.return_value = ("admin", "password")
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock responses
        network_response = self.create_mock_response(200)
        next_ip_response = self.create_mock_response(200)
        mock_requests.get.return_value = network_response
        mock_requests.post.return_value = next_ip_response
        
        # Setup mock API response handlers
        mock_handle_response.side_effect = [
            [{"_ref": "network/ZG5ldHdvcmskMTkyLjE2OC4xLjAvMjQvMA:192.168.1.0/24/default"}],
            {"ips": ["192.168.1.100"]}
        ]
        
        # Execute task
        result = infoblox_get_next_ip(mock_task, network="192.168.1.0/24")
        
        # Assertions
        self.assert_result_success(result, ["network", "next_ip", "network_ref"])
        assert result.result["network"] == "192.168.1.0/24"
        assert result.result["next_ip"] == "192.168.1.100"
        assert "network/" in result.result["network_ref"]
        
        # Verify API calls
        assert mock_requests.get.call_count == 1
        assert mock_requests.post.call_count == 1
    
    @patch('enhancements.integrations.monitoring_integration.InfobloxIntegration')
    @patch('enhancements.integrations.monitoring_integration.requests')
    @patch('enhancements.integrations.monitoring_integration.handle_api_response')
    def test_infoblox_create_host_record_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful host record creation."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.url = "https://infoblox.example.com"
        mock_integration.wapi_version = "v2.12"
        mock_integration.get_auth.return_value = ("admin", "password")
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(201)
        mock_requests.post.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = "record:host/ZG5ldHdvcmskMTkyLjE2OC4xLjAvMjQvMA:test-host.example.com/default"
        
        # Execute task
        result = infoblox_create_host_record(
            mock_task,
            hostname="test-host.example.com",
            ip_address="192.168.1.100"
        )
        
        # Assertions
        self.assert_result_success(result, ["hostname", "ip_address", "host_ref"])
        assert result.result["hostname"] == "test-host.example.com"
        assert result.result["ip_address"] == "192.168.1.100"
        assert result.result["view"] == "default"
        assert "record:host/" in result.result["host_ref"]
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "record:host" in call_args[0][0]
        
        # Verify request data
        request_data = call_args[1]["json"]
        assert request_data["name"] == "test-host.example.com"
        assert request_data["ipv4addrs"][0]["ipv4addr"] == "192.168.1.100"
