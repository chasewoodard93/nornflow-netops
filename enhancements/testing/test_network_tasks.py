"""
Unit tests for enhanced network automation tasks.

Tests all enhanced network task functionality including:
- Device interaction tasks (connection testing, API support)
- Configuration management tasks (deployment, backup, validation)
- Discovery tasks (device discovery, topology mapping)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from enhancements.network_tasks.device_interaction.connection_tasks import (
    test_connectivity,
    test_api_payload,
    get_device_info
)
from enhancements.network_tasks.configuration.config_tasks import (
    backup_config,
    deploy_config,
    deploy_config_api,
    validate_config,
    restore_config
)
from enhancements.network_tasks.discovery.discovery_tasks import (
    discover_neighbors,
    map_network_topology,
    scan_network_range
)
from enhancements.testing.test_framework import NetworkTaskTestBase


class TestDeviceInteractionTasks(NetworkTaskTestBase):
    """Test device interaction tasks."""
    
    @patch('enhancements.network_tasks.device_interaction.connection_tasks.netmiko')
    def test_connectivity_ssh_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Test successful SSH connectivity test."""
        # Setup mock connection
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_command.return_value = "Router#"
        
        # Execute task
        result = test_connectivity(mock_task, method="ssh", test_command="show version")
        
        # Assertions
        self.assert_result_success(result, ["method", "success", "response_time"])
        assert result.result["method"] == "ssh"
        assert result.result["success"] is True
        assert result.result["test_command"] == "show version"
        assert "response_time" in result.result
        
        # Verify netmiko calls
        mock_netmiko.ConnectHandler.assert_called_once()
        mock_netmiko_connection.send_command.assert_called_once_with("show version")
        mock_netmiko_connection.disconnect.assert_called_once()
    
    @patch('enhancements.network_tasks.device_interaction.connection_tasks.netmiko')
    def test_connectivity_ssh_failure(self, mock_netmiko, mock_task):
        """Test SSH connectivity test failure."""
        # Setup mock connection failure
        mock_netmiko.ConnectHandler.side_effect = Exception("Connection timeout")
        
        # Execute task
        result = test_connectivity(mock_task, method="ssh")
        
        # Assertions
        self.assert_result_failed(result, "Connection timeout")
    
    @patch('enhancements.network_tasks.device_interaction.connection_tasks.requests')
    def test_connectivity_api_success(self, mock_requests, mock_task):
        """Test successful API connectivity test."""
        # Setup mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "version": "16.09.03"}
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_requests.get.return_value = mock_response
        
        # Execute task
        api_config = {
            "url": "https://192.168.1.1/restconf/data/ietf-system:system/platform",
            "username": "admin",
            "password": "password",
            "verify_ssl": False
        }
        result = test_connectivity(mock_task, method="api", api_config=api_config)
        
        # Assertions
        self.assert_result_success(result, ["method", "success", "status_code", "response_time"])
        assert result.result["method"] == "api"
        assert result.result["success"] is True
        assert result.result["status_code"] == 200
        assert result.result["response_time"] == 0.5
        
        # Verify API call
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        assert api_config["url"] in call_args[0]
    
    @patch('enhancements.network_tasks.device_interaction.connection_tasks.requests')
    def test_api_payload_success(self, mock_requests, mock_task):
        """Test successful API payload testing."""
        # Setup mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success", "data": {"interface": "configured"}}
        mock_response.text = '{"result": "success"}'
        mock_requests.post.return_value = mock_response
        
        # Execute task
        api_config = {
            "url": "https://192.168.1.1/restconf/data/ietf-interfaces:interfaces",
            "username": "admin",
            "password": "password"
        }
        payload_template = {
            "ietf-interfaces:interface": {
                "name": "{{ interface_name }}",
                "description": "{{ description }}",
                "enabled": True
            }
        }
        template_vars = {
            "interface_name": "GigabitEthernet0/1",
            "description": "Test interface"
        }
        
        result = test_api_payload(
            mock_task,
            api_config=api_config,
            payload_template=payload_template,
            template_vars=template_vars,
            method="POST"
        )
        
        # Assertions
        self.assert_result_success(result, ["method", "status_code", "response_data", "rendered_payload"])
        assert result.result["method"] == "POST"
        assert result.result["status_code"] == 200
        assert "GigabitEthernet0/1" in result.result["rendered_payload"]
        assert "Test interface" in result.result["rendered_payload"]
        
        # Verify API call
        mock_requests.post.assert_called_once()
    
    @patch('enhancements.network_tasks.device_interaction.connection_tasks.netmiko')
    def test_get_device_info_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Test successful device information retrieval."""
        # Setup mock connection and responses
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_command.side_effect = [
            "Cisco IOS Software, Version 16.09.03",  # show version
            "GigabitEthernet0/1 is up, line protocol is up",  # show ip interface brief
            "Total number of Spanning tree instances: 1"  # show spanning-tree
        ]
        
        # Execute task
        result = get_device_info(mock_task, info_commands=["show version", "show ip interface brief"])
        
        # Assertions
        self.assert_result_success(result, ["device_name", "platform", "commands_executed", "command_outputs"])
        assert result.result["device_name"] == mock_task.host.name
        assert result.result["platform"] == mock_task.host.platform
        assert len(result.result["command_outputs"]) == 2
        assert "show version" in result.result["command_outputs"]
        assert "Cisco IOS Software" in result.result["command_outputs"]["show version"]


class TestConfigurationTasks(NetworkTaskTestBase):
    """Test configuration management tasks."""
    
    @patch('enhancements.network_tasks.configuration.config_tasks.netmiko')
    def test_backup_config_success(self, mock_netmiko, mock_task, mock_netmiko_connection, sample_config_content):
        """Test successful configuration backup."""
        # Setup mock connection
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_command.return_value = sample_config_content
        
        # Mock file operations
        with patch('enhancements.network_tasks.configuration.config_tasks.Path') as mock_path:
            mock_backup_file = Mock()
            mock_path.return_value = mock_backup_file
            mock_backup_file.parent.mkdir = Mock()
            mock_backup_file.write_text = Mock()
            mock_backup_file.exists.return_value = True
            
            # Execute task
            result = backup_config(
                mock_task,
                backup_dir="/tmp/backups",
                include_timestamp=True,
                config_command="show running-config"
            )
            
            # Assertions
            self.assert_result_success(result, ["device_name", "backup_file", "config_size", "timestamp"])
            assert result.result["device_name"] == mock_task.host.name
            assert "/tmp/backups" in result.result["backup_file"]
            assert result.result["config_size"] > 0
            
            # Verify file operations
            mock_backup_file.write_text.assert_called_once_with(sample_config_content)
    
    @patch('enhancements.network_tasks.configuration.config_tasks.netmiko')
    def test_deploy_config_success(self, mock_netmiko, mock_task, mock_netmiko_connection, sample_config_content):
        """Test successful configuration deployment."""
        # Setup mock connection
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_config_set.return_value = "Configuration applied successfully"
        mock_netmiko_connection.send_command.return_value = sample_config_content
        
        # Mock template rendering
        with patch('enhancements.network_tasks.configuration.config_tasks.Environment') as mock_jinja_env:
            mock_template = Mock()
            mock_template.render.return_value = "hostname test-device\ninterface GigE0/1\n description Test"
            mock_jinja_env.return_value.get_template.return_value = mock_template
            
            # Execute task
            result = deploy_config(
                mock_task,
                template_file="templates/base_config.j2",
                template_vars={"hostname": "test-device"},
                backup_before=True,
                validate_after=True
            )
            
            # Assertions
            self.assert_result_success(result, ["device_name", "success", "config_applied", "backup_file"])
            assert result.result["device_name"] == mock_task.host.name
            assert result.result["success"] is True
            assert result.result["config_applied"] is True
            
            # Verify netmiko calls
            mock_netmiko_connection.send_config_set.assert_called()
    
    @patch('enhancements.network_tasks.configuration.config_tasks.requests')
    def test_deploy_config_api_success(self, mock_requests, mock_task):
        """Test successful API-based configuration deployment."""
        # Setup mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "message": "Configuration applied"}
        mock_requests.post.return_value = mock_response
        mock_requests.get.return_value = mock_response  # For validation
        
        # Execute task
        api_config = {
            "url": "https://192.168.1.1/restconf/data",
            "username": "admin",
            "password": "password"
        }
        config_data = {
            "ietf-interfaces:interfaces": {
                "interface": [
                    {"name": "GigabitEthernet0/1", "description": "Test interface"}
                ]
            }
        }
        
        result = deploy_config_api(
            mock_task,
            api_config=api_config,
            config_data=config_data,
            method="POST",
            validate_after=True
        )
        
        # Assertions
        self.assert_result_success(result, ["device_name", "success", "status_code", "response_data"])
        assert result.result["device_name"] == mock_task.host.name
        assert result.result["success"] is True
        assert result.result["status_code"] == 200
        
        # Verify API calls
        mock_requests.post.assert_called_once()
    
    @patch('enhancements.network_tasks.configuration.config_tasks.netmiko')
    def test_validate_config_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Test successful configuration validation."""
        # Setup mock connection and validation responses
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_command.side_effect = [
            "test-device",  # hostname validation
            "GigabitEthernet0/1 is up, line protocol is up",  # interface validation
            "Router uptime is 1 day, 2 hours"  # uptime validation
        ]
        
        # Execute task
        validation_commands = [
            {"command": "show running-config | include hostname", "expected": "test-device"},
            {"command": "show ip interface brief", "expected": "GigabitEthernet0/1"},
            {"command": "show version | include uptime", "expected": "uptime"}
        ]
        
        result = validate_config(mock_task, validation_commands=validation_commands)
        
        # Assertions
        self.assert_result_success(result, ["device_name", "validation_passed", "total_validations", "results"])
        assert result.result["device_name"] == mock_task.host.name
        assert result.result["validation_passed"] is True
        assert result.result["total_validations"] == 3
        assert result.result["passed_validations"] == 3
        assert result.result["failed_validations"] == 0
        
        # Check individual validation results
        results = result.result["results"]
        assert len(results) == 3
        assert all(r["passed"] for r in results)
    
    @patch('enhancements.network_tasks.configuration.config_tasks.netmiko')
    def test_restore_config_success(self, mock_netmiko, mock_task, mock_netmiko_connection, sample_config_content):
        """Test successful configuration restore."""
        # Setup mock connection
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_config_set.return_value = "Configuration restored successfully"
        
        # Mock file operations
        with patch('enhancements.network_tasks.configuration.config_tasks.Path') as mock_path:
            mock_backup_file = Mock()
            mock_path.return_value = mock_backup_file
            mock_backup_file.exists.return_value = True
            mock_backup_file.read_text.return_value = sample_config_content
            
            # Execute task
            result = restore_config(
                mock_task,
                backup_file="/tmp/backups/test-device_backup.txt",
                validate_after=True
            )
            
            # Assertions
            self.assert_result_success(result, ["device_name", "success", "backup_file", "config_restored"])
            assert result.result["device_name"] == mock_task.host.name
            assert result.result["success"] is True
            assert result.result["config_restored"] is True
            
            # Verify file and netmiko operations
            mock_backup_file.read_text.assert_called_once()
            mock_netmiko_connection.send_config_set.assert_called()


class TestDiscoveryTasks(NetworkTaskTestBase):
    """Test network discovery tasks."""
    
    @patch('enhancements.network_tasks.discovery.discovery_tasks.netmiko')
    def test_discover_neighbors_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Test successful neighbor discovery."""
        # Setup mock connection and CDP output
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        cdp_output = """
Device ID: switch-01.example.com
Entry address(es): 
  IP address: 192.168.1.2
Platform: cisco WS-C3850-24T,  Capabilities: Router Switch IGMP 
Interface: GigabitEthernet0/1,  Port ID (outgoing port): GigabitEthernet1/0/1

Device ID: router-02.example.com
Entry address(es): 
  IP address: 192.168.1.3
Platform: cisco ISR4321,  Capabilities: Router Source-Route-Bridge
Interface: GigabitEthernet0/2,  Port ID (outgoing port): GigabitEthernet0/0/0
        """
        mock_netmiko_connection.send_command.return_value = cdp_output
        
        # Execute task
        result = discover_neighbors(mock_task, protocol="cdp")
        
        # Assertions
        self.assert_result_success(result, ["device_name", "protocol", "neighbor_count", "neighbors"])
        assert result.result["device_name"] == mock_task.host.name
        assert result.result["protocol"] == "cdp"
        assert result.result["neighbor_count"] == 2
        
        # Check neighbor details
        neighbors = result.result["neighbors"]
        assert len(neighbors) == 2
        assert neighbors[0]["device_id"] == "switch-01.example.com"
        assert neighbors[0]["ip_address"] == "192.168.1.2"
        assert neighbors[1]["device_id"] == "router-02.example.com"
    
    @patch('enhancements.network_tasks.discovery.discovery_tasks.subprocess')
    def test_scan_network_range_success(self, mock_subprocess, mock_task):
        """Test successful network range scanning."""
        # Setup mock ping responses
        mock_subprocess.run.side_effect = [
            Mock(returncode=0),  # 192.168.1.1 - success
            Mock(returncode=1),  # 192.168.1.2 - failure
            Mock(returncode=0),  # 192.168.1.3 - success
        ]
        
        # Execute task
        result = scan_network_range(
            mock_task,
            network_range="192.168.1.1-192.168.1.3",
            timeout=1,
            include_hostnames=False
        )
        
        # Assertions
        self.assert_result_success(result, ["network_range", "total_scanned", "active_hosts", "scan_results"])
        assert result.result["network_range"] == "192.168.1.1-192.168.1.3"
        assert result.result["total_scanned"] == 3
        assert result.result["active_hosts"] == 2
        
        # Check scan results
        scan_results = result.result["scan_results"]
        assert len(scan_results) == 3
        assert scan_results["192.168.1.1"]["reachable"] is True
        assert scan_results["192.168.1.2"]["reachable"] is False
        assert scan_results["192.168.1.3"]["reachable"] is True
    
    @patch('enhancements.network_tasks.discovery.discovery_tasks.netmiko')
    def test_map_network_topology_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Test successful network topology mapping."""
        # Setup mock connection and LLDP output
        mock_netmiko.ConnectHandler.return_value = mock_netmiko_connection
        lldp_output = """
Local Intf: Gi0/1
Chassis id: 001a.2b3c.4d5e
Port id: Gi1/0/1
Port Description: GigabitEthernet1/0/1
System Name: switch-01.example.com

Local Intf: Gi0/2
Chassis id: 001f.2e3d.4c5b
Port id: Gi0/0/0
Port Description: GigabitEthernet0/0/0
System Name: router-02.example.com
        """
        mock_netmiko_connection.send_command.return_value = lldp_output
        
        # Execute task
        result = map_network_topology(mock_task, discovery_protocol="lldp", max_depth=2)
        
        # Assertions
        self.assert_result_success(result, ["device_name", "protocol", "topology_depth", "connections"])
        assert result.result["device_name"] == mock_task.host.name
        assert result.result["protocol"] == "lldp"
        assert result.result["topology_depth"] == 1  # Only discovered direct neighbors
        
        # Check topology connections
        connections = result.result["connections"]
        assert len(connections) == 2
        assert connections[0]["local_interface"] == "Gi0/1"
        assert connections[0]["neighbor_name"] == "switch-01.example.com"
        assert connections[1]["local_interface"] == "Gi0/2"
        assert connections[1]["neighbor_name"] == "router-02.example.com"
