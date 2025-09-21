"""
Unit tests for NetBox integration tasks.

Tests all NetBox integration functionality including:
- Device management operations
- IP address management
- Configuration context retrieval
- Interface synchronization
- Site device queries
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from enhancements.integrations.netbox_integration import (
    NetBoxIntegration,
    netbox_get_device,
    netbox_update_device,
    netbox_get_available_ip,
    netbox_assign_ip,
    netbox_get_config_context,
    netbox_sync_interfaces,
    netbox_get_site_devices
)
from enhancements.testing.test_framework import IntegrationTestBase


class TestNetBoxIntegration(IntegrationTestBase):
    """Test NetBox integration class."""
    
    def test_integration_validation_success(self, sample_config):
        """Test successful NetBox integration validation."""
        config = {
            "url": "https://netbox.example.com",
            "token": "test-token-123"
        }
        
        integration = NetBoxIntegration(config)
        
        assert integration.url == "https://netbox.example.com"
        assert integration.token == "test-token-123"
        assert integration.timeout == 30  # default
        assert integration.ssl_verify is True  # default
    
    def test_integration_validation_missing_url(self):
        """Test NetBox integration validation with missing URL."""
        config = {"token": "test-token"}
        
        with pytest.raises(ValueError, match="url.*required"):
            NetBoxIntegration(config)
    
    def test_integration_validation_missing_token(self):
        """Test NetBox integration validation with missing token."""
        config = {"url": "https://netbox.example.com"}
        
        with pytest.raises(ValueError, match="token.*required"):
            NetBoxIntegration(config)
    
    @patch('enhancements.integrations.netbox_integration.pynetbox')
    def test_get_api_success(self, mock_pynetbox, sample_config):
        """Test successful API connection."""
        config = {
            "url": "https://netbox.example.com",
            "token": "test-token"
        }
        
        mock_api = Mock()
        mock_pynetbox.api.return_value = mock_api
        
        integration = NetBoxIntegration(config)
        api = integration.get_api()
        
        mock_pynetbox.api.assert_called_once_with(
            "https://netbox.example.com",
            token="test-token"
        )
        assert api == mock_api
    
    @patch('enhancements.integrations.netbox_integration.pynetbox')
    def test_test_connection_success(self, mock_pynetbox):
        """Test successful connection test."""
        config = {
            "url": "https://netbox.example.com",
            "token": "test-token"
        }
        
        mock_api = Mock()
        mock_api.version = "3.5.0"
        mock_pynetbox.api.return_value = mock_api
        
        integration = NetBoxIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to NetBox" in result["message"]
        assert result["version"] == "3.5.0"
    
    @patch('enhancements.integrations.netbox_integration.pynetbox')
    def test_test_connection_failure(self, mock_pynetbox):
        """Test connection test failure."""
        config = {
            "url": "https://netbox.example.com",
            "token": "invalid-token"
        }
        
        mock_pynetbox.api.side_effect = Exception("Authentication failed")
        
        integration = NetBoxIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is False
        assert "Authentication failed" in result["message"]


class TestNetBoxDeviceTasks(IntegrationTestBase):
    """Test NetBox device management tasks."""
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_get_device_success(self, mock_integration_class, mock_task):
        """Test successful device retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API and device
        mock_api = Mock()
        mock_device = Mock()
        mock_device.id = 123
        mock_device.name = "test-device"
        mock_device.device_type = "Cisco ISR 4321"
        mock_device.device_role = "Router"
        mock_device.status = "active"
        mock_device.primary_ip4 = "192.168.1.1"
        
        mock_api.dcim.devices.get.return_value = mock_device
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_get_device(mock_task, device_name="test-device")
        
        # Assertions
        self.assert_result_success(result, ["device_name", "device_id", "device_type"])
        assert result.result["device_name"] == "test-device"
        assert result.result["device_id"] == 123
        assert result.result["device_type"] == "Cisco ISR 4321"
        
        mock_api.dcim.devices.get.assert_called_once_with(name="test-device")
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_get_device_not_found(self, mock_integration_class, mock_task):
        """Test device not found scenario."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API
        mock_api = Mock()
        mock_api.dcim.devices.get.return_value = None
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_get_device(mock_task, device_name="nonexistent-device")
        
        # Assertions
        self.assert_result_failed(result, "not found")
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_update_device_success(self, mock_integration_class, mock_task):
        """Test successful device update."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API and device
        mock_api = Mock()
        mock_device = Mock()
        mock_device.id = 123
        mock_device.name = "test-device"
        mock_device.save.return_value = None
        
        mock_api.dcim.devices.get.return_value = mock_device
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        updates = {"status": "maintenance", "comments": "Under maintenance"}
        result = netbox_update_device(mock_task, device_name="test-device", updates=updates)
        
        # Assertions
        self.assert_result_success(result, ["device_name", "device_id", "updated_fields"])
        assert result.result["device_name"] == "test-device"
        assert result.result["updated_fields"] == ["status", "comments"]
        
        # Verify device was updated
        assert mock_device.status == "maintenance"
        assert mock_device.comments == "Under maintenance"
        mock_device.save.assert_called_once()


class TestNetBoxIPManagement(IntegrationTestBase):
    """Test NetBox IP address management tasks."""
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_get_available_ip_success(self, mock_integration_class, mock_task):
        """Test successful available IP retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API
        mock_api = Mock()
        mock_prefix = Mock()
        mock_prefix.available_ips.list.return_value = ["192.168.1.10", "192.168.1.11"]
        
        mock_api.ipam.prefixes.get.return_value = mock_prefix
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_get_available_ip(mock_task, prefix="192.168.1.0/24", count=2)
        
        # Assertions
        self.assert_result_success(result, ["prefix", "available_ips", "count"])
        assert result.result["prefix"] == "192.168.1.0/24"
        assert result.result["available_ips"] == ["192.168.1.10", "192.168.1.11"]
        assert result.result["count"] == 2
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_assign_ip_success(self, mock_integration_class, mock_task):
        """Test successful IP assignment."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API
        mock_api = Mock()
        mock_device = Mock()
        mock_device.id = 123
        mock_interface = Mock()
        mock_interface.id = 456
        
        mock_ip = Mock()
        mock_ip.id = 789
        mock_ip.address = "192.168.1.10/24"
        
        mock_api.dcim.devices.get.return_value = mock_device
        mock_api.dcim.interfaces.get.return_value = mock_interface
        mock_api.ipam.ip_addresses.create.return_value = mock_ip
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_assign_ip(
            mock_task,
            device_name="test-device",
            interface_name="GigE0/1",
            ip_address="192.168.1.10/24"
        )
        
        # Assertions
        self.assert_result_success(result, ["device_name", "interface_name", "ip_address", "ip_id"])
        assert result.result["device_name"] == "test-device"
        assert result.result["interface_name"] == "GigE0/1"
        assert result.result["ip_address"] == "192.168.1.10/24"
        assert result.result["ip_id"] == 789


class TestNetBoxConfigContext(IntegrationTestBase):
    """Test NetBox configuration context tasks."""
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_get_config_context_success(self, mock_integration_class, mock_task):
        """Test successful config context retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API and device
        mock_api = Mock()
        mock_device = Mock()
        mock_device.config_context = {
            "ntp_servers": ["10.0.0.1", "10.0.0.2"],
            "dns_servers": ["8.8.8.8", "8.8.4.4"],
            "snmp_community": "public"
        }
        
        mock_api.dcim.devices.get.return_value = mock_device
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_get_config_context(mock_task, device_name="test-device")
        
        # Assertions
        self.assert_result_success(result, ["device_name", "config_context", "context_keys"])
        assert result.result["device_name"] == "test-device"
        assert "ntp_servers" in result.result["config_context"]
        assert "dns_servers" in result.result["config_context"]
        assert len(result.result["context_keys"]) == 3


class TestNetBoxSiteOperations(IntegrationTestBase):
    """Test NetBox site-level operations."""
    
    @patch('enhancements.integrations.netbox_integration.NetBoxIntegration')
    def test_netbox_get_site_devices_success(self, mock_integration_class, mock_task):
        """Test successful site devices retrieval."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock API
        mock_api = Mock()
        mock_site = Mock()
        mock_site.id = 1
        mock_site.name = "test-site"
        
        mock_device1 = Mock()
        mock_device1.id = 123
        mock_device1.name = "router-01"
        mock_device1.device_type = "Cisco ISR 4321"
        mock_device1.device_role = "Router"
        mock_device1.status = "active"
        mock_device1.primary_ip4 = "192.168.1.1"
        mock_device1.platform = "cisco_ios"
        mock_device1.rack = None
        mock_device1.position = None
        
        mock_device2 = Mock()
        mock_device2.id = 124
        mock_device2.name = "switch-01"
        mock_device2.device_type = "Cisco Catalyst 9300"
        mock_device2.device_role = "Switch"
        mock_device2.status = "active"
        mock_device2.primary_ip4 = "192.168.1.2"
        mock_device2.platform = "cisco_ios"
        mock_device2.rack = None
        mock_device2.position = None
        
        mock_api.dcim.sites.get.return_value = mock_site
        mock_api.dcim.devices.filter.return_value = [mock_device1, mock_device2]
        mock_integration.get_api.return_value = mock_api
        
        # Execute task
        result = netbox_get_site_devices(mock_task, site_name="test-site")
        
        # Assertions
        self.assert_result_success(result, ["site_name", "site_id", "device_count", "devices"])
        assert result.result["site_name"] == "test-site"
        assert result.result["site_id"] == 1
        assert result.result["device_count"] == 2
        assert len(result.result["devices"]) == 2
        
        # Check device details
        devices = result.result["devices"]
        assert devices[0]["name"] == "router-01"
        assert devices[1]["name"] == "switch-01"
