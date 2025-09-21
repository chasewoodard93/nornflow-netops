"""
Unit testing examples for NornFlow enhancements.

This module provides comprehensive examples of how to write unit tests
for various NornFlow enhancement components including:
- Integration tasks
- Network automation tasks
- Workflow control structures
- Custom task development
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from enhancements.testing.test_framework import IntegrationTestBase, NetworkTaskTestBase


class ExampleIntegrationTaskTest(IntegrationTestBase):
    """
    Example: Testing an integration task with external API.
    
    This example shows how to test a task that interacts with an external
    API service, demonstrating proper mocking and assertion patterns.
    """
    
    @patch('requests.get')
    def test_api_integration_success(self, mock_requests, mock_task):
        """Example: Test successful API integration."""
        # 1. Setup mock response
        mock_response = self.create_mock_response(
            status_code=200,
            json_data={
                "status": "success",
                "data": {
                    "id": "12345",
                    "name": "test-device",
                    "ip_address": "192.168.1.1"
                }
            }
        )
        mock_requests.return_value = mock_response
        
        # 2. Import and execute the task function
        from enhancements.integrations.example_integration import get_device_info
        
        result = get_device_info(
            mock_task,
            device_id="12345",
            api_url="https://api.example.com",
            api_token="test-token"
        )
        
        # 3. Assert success and verify result structure
        self.assert_result_success(result, ["device_id", "device_name", "ip_address"])
        
        # 4. Verify specific result values
        assert result.result["device_id"] == "12345"
        assert result.result["device_name"] == "test-device"
        assert result.result["ip_address"] == "192.168.1.1"
        
        # 5. Verify API call was made correctly
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        assert "https://api.example.com" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
    
    @patch('requests.get')
    def test_api_integration_failure(self, mock_requests, mock_task):
        """Example: Test API integration failure handling."""
        # 1. Setup mock failure response
        mock_response = self.create_mock_response(
            status_code=404,
            json_data={"error": "Device not found"}
        )
        mock_requests.return_value = mock_response
        
        # 2. Execute task
        from enhancements.integrations.example_integration import get_device_info
        
        result = get_device_info(
            mock_task,
            device_id="nonexistent",
            api_url="https://api.example.com",
            api_token="test-token"
        )
        
        # 3. Assert failure and verify error message
        self.assert_result_failed(result, "Device not found")
    
    @patch('requests.post')
    def test_api_integration_with_payload(self, mock_requests, mock_task):
        """Example: Test API integration with JSON payload."""
        # 1. Setup mock response
        mock_response = self.create_mock_response(
            status_code=201,
            json_data={"id": "67890", "status": "created"}
        )
        mock_requests.return_value = mock_response
        
        # 2. Execute task with payload
        from enhancements.integrations.example_integration import create_device
        
        device_data = {
            "name": "new-device",
            "ip_address": "192.168.1.100",
            "device_type": "router"
        }
        
        result = create_device(
            mock_task,
            device_data=device_data,
            api_url="https://api.example.com",
            api_token="test-token"
        )
        
        # 3. Assert success
        self.assert_result_success(result, ["device_id", "status"])
        assert result.result["device_id"] == "67890"
        assert result.result["status"] == "created"
        
        # 4. Verify payload was sent correctly
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        sent_data = call_args[1]["json"]
        assert sent_data["name"] == "new-device"
        assert sent_data["ip_address"] == "192.168.1.100"


class ExampleNetworkTaskTest(NetworkTaskTestBase):
    """
    Example: Testing network automation tasks.
    
    This example shows how to test tasks that interact with network devices
    using netmiko or API connections.
    """
    
    @patch('netmiko.ConnectHandler')
    def test_device_configuration_success(self, mock_netmiko, mock_task, mock_netmiko_connection):
        """Example: Test successful device configuration."""
        # 1. Setup netmiko mock
        mock_netmiko.return_value = mock_netmiko_connection
        mock_netmiko_connection.send_config_set.return_value = "Configuration applied successfully"
        mock_netmiko_connection.send_command.return_value = "hostname test-device"
        
        # 2. Execute configuration task
        from enhancements.network_tasks.configuration.example_config import configure_hostname
        
        result = configure_hostname(
            mock_task,
            hostname="test-device",
            validate_after=True
        )
        
        # 3. Assert success
        self.assert_result_success(result, ["hostname", "config_applied", "validation_passed"])
        assert result.result["hostname"] == "test-device"
        assert result.result["config_applied"] is True
        assert result.result["validation_passed"] is True
        
        # 4. Verify netmiko calls
        mock_netmiko_connection.send_config_set.assert_called_once()
        config_commands = mock_netmiko_connection.send_config_set.call_args[0][0]
        assert "hostname test-device" in config_commands
        
        # 5. Verify validation command
        mock_netmiko_connection.send_command.assert_called_with("show running-config | include hostname")
    
    @patch('netmiko.ConnectHandler')
    def test_device_configuration_failure(self, mock_netmiko, mock_task):
        """Example: Test device configuration failure."""
        # 1. Setup netmiko mock to raise exception
        mock_netmiko.side_effect = Exception("Connection timeout")
        
        # 2. Execute task
        from enhancements.network_tasks.configuration.example_config import configure_hostname
        
        result = configure_hostname(mock_task, hostname="test-device")
        
        # 3. Assert failure
        self.assert_result_failed(result, "Connection timeout")
    
    @patch('requests.post')
    def test_api_configuration_success(self, mock_requests, mock_task):
        """Example: Test API-based device configuration."""
        # 1. Setup API mock response
        mock_response = self.create_mock_response(
            status_code=200,
            json_data={"status": "success", "message": "Configuration applied"}
        )
        mock_requests.return_value = mock_response
        
        # 2. Execute API configuration task
        from enhancements.network_tasks.configuration.example_config import configure_interface_api
        
        interface_config = {
            "name": "GigabitEthernet0/1",
            "description": "Test interface",
            "enabled": True,
            "ip_address": "192.168.1.1/24"
        }
        
        result = configure_interface_api(
            mock_task,
            interface_config=interface_config,
            api_url="https://device.example.com/restconf",
            username="admin",
            password="password"
        )
        
        # 3. Assert success
        self.assert_result_success(result, ["interface_name", "status", "api_response"])
        assert result.result["interface_name"] == "GigabitEthernet0/1"
        assert result.result["status"] == "success"
        
        # 4. Verify API call
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        assert "restconf" in call_args[0][0]
        
        # 5. Verify payload structure
        payload = call_args[1]["json"]
        assert payload["ietf-interfaces:interface"]["name"] == "GigabitEthernet0/1"


class ExampleWorkflowControlTest(IntegrationTestBase):
    """
    Example: Testing workflow control structures.
    
    This example shows how to test conditional logic, loops,
    and error handling in workflows.
    """
    
    def test_condition_evaluation(self):
        """Example: Test condition evaluation logic."""
        from enhancements.workflow_control.control_structures import ConditionEvaluator
        
        evaluator = ConditionEvaluator()
        
        # 1. Test simple boolean conditions
        context = {"deploy_config": True, "environment": "production"}
        
        assert evaluator.evaluate("{{ deploy_config }}", context) is True
        assert evaluator.evaluate("{{ not deploy_config }}", context) is False
        
        # 2. Test comparison conditions
        assert evaluator.evaluate("{{ environment == 'production' }}", context) is True
        assert evaluator.evaluate("{{ environment == 'test' }}", context) is False
        
        # 3. Test complex conditions
        context.update({"device_count": 10, "maintenance_window": True})
        
        complex_condition = "{{ device_count > 5 and environment == 'production' and maintenance_window }}"
        assert evaluator.evaluate(complex_condition, context) is True
        
        # 4. Test unless logic (inverse)
        assert evaluator.evaluate("{{ deploy_config }}", context, unless=True) is False
        assert evaluator.evaluate("{{ not deploy_config }}", context, unless=True) is True
    
    def test_loop_iteration(self):
        """Example: Test loop iteration logic."""
        from enhancements.workflow_control.control_structures import LoopController
        
        controller = LoopController()
        
        # 1. Test simple loop
        items = ["item1", "item2", "item3"]
        iterations = list(controller.iterate_loop(items))
        
        assert len(iterations) == 3
        assert iterations[0]["item"] == "item1"
        assert iterations[0]["loop_index"] == 0
        assert iterations[1]["item"] == "item2"
        assert iterations[2]["item"] == "item3"
        
        # 2. Test with_items loop (complex objects)
        items = [
            {"name": "interface1", "vlan": 100},
            {"name": "interface2", "vlan": 200}
        ]
        iterations = list(controller.iterate_with_items(items))
        
        assert len(iterations) == 2
        assert iterations[0]["item"]["name"] == "interface1"
        assert iterations[0]["item"]["vlan"] == 100
        
        # 3. Test until loop
        call_count = 0
        def condition_func(context):
            nonlocal call_count
            call_count += 1
            return call_count >= 3
        
        iterations = list(controller.iterate_until(condition_func, max_iterations=5))
        assert len(iterations) == 3  # Should stop when condition becomes true
    
    def test_retry_strategy(self):
        """Example: Test retry strategy logic."""
        from enhancements.workflow_control.control_structures import RetryStrategy
        
        # 1. Test exponential backoff
        strategy = RetryStrategy(
            max_attempts=3,
            delay=1,
            backoff_factor=2.0,
            max_delay=10
        )
        
        delays = [strategy.get_delay(i) for i in range(3)]
        assert delays == [1, 2, 4]  # 1, 1*2, 1*2*2
        
        # 2. Test max delay limit
        strategy = RetryStrategy(
            max_attempts=4,
            delay=1,
            backoff_factor=5.0,
            max_delay=3
        )
        
        delays = [strategy.get_delay(i) for i in range(4)]
        assert delays == [1, 3, 3, 3]  # Capped at max_delay=3


class ExampleCustomTaskTest(IntegrationTestBase):
    """
    Example: Testing custom task development.
    
    This example shows how to test custom tasks that you develop
    for your specific use cases.
    """
    
    def test_custom_task_template(self, mock_task):
        """Example: Template for testing custom tasks."""
        # This is a template you can copy and modify for your custom tasks
        
        # 1. Mock any external dependencies
        with patch('your_module.external_dependency') as mock_dependency:
            mock_dependency.return_value = {"expected": "response"}
            
            # 2. Import and execute your custom task
            from your_module import your_custom_task
            
            result = your_custom_task(
                mock_task,
                param1="value1",
                param2="value2"
            )
            
            # 3. Assert success and verify result structure
            self.assert_result_success(result, ["expected_key1", "expected_key2"])
            
            # 4. Verify specific result values
            assert result.result["expected_key1"] == "expected_value1"
            
            # 5. Verify external dependency calls
            mock_dependency.assert_called_once_with("value1", "value2")
    
    @patch('your_module.file_operations')
    def test_custom_task_with_file_operations(self, mock_file_ops, mock_task):
        """Example: Test custom task with file operations."""
        # 1. Mock file operations
        mock_file_ops.read_file.return_value = "file content"
        mock_file_ops.write_file.return_value = True
        
        # 2. Execute task
        from your_module import process_config_file
        
        result = process_config_file(
            mock_task,
            input_file="/path/to/input.txt",
            output_file="/path/to/output.txt",
            transform_rules={"rule1": "value1"}
        )
        
        # 3. Assert success
        self.assert_result_success(result, ["processed", "input_file", "output_file"])
        
        # 4. Verify file operations
        mock_file_ops.read_file.assert_called_once_with("/path/to/input.txt")
        mock_file_ops.write_file.assert_called_once()
    
    def test_custom_task_error_handling(self, mock_task):
        """Example: Test custom task error handling."""
        # 1. Mock dependency to raise exception
        with patch('your_module.risky_operation') as mock_risky:
            mock_risky.side_effect = ValueError("Something went wrong")
            
            # 2. Execute task
            from your_module import risky_custom_task
            
            result = risky_custom_task(mock_task, param="value")
            
            # 3. Assert failure with expected error
            self.assert_result_failed(result, "Something went wrong")
    
    def test_custom_task_dry_run(self, mock_task):
        """Example: Test custom task dry-run functionality."""
        # 1. Set task to dry-run mode
        mock_task.is_dry_run.return_value = True
        
        # 2. Execute task
        from your_module import your_custom_task
        
        result = your_custom_task(mock_task, param="value")
        
        # 3. Assert dry-run behavior
        self.assert_result_success(result, ["dry_run", "would_execute"])
        assert result.result["dry_run"] is True
        assert "would_execute" in result.result
        
        # 4. Verify no actual changes were made
        # (Add specific assertions based on your task's behavior)


# Pytest fixtures for examples
@pytest.fixture
def sample_api_response():
    """Provide sample API response data."""
    return {
        "status": "success",
        "data": {
            "devices": [
                {"id": "1", "name": "device1", "ip": "192.168.1.1"},
                {"id": "2", "name": "device2", "ip": "192.168.1.2"}
            ]
        },
        "metadata": {
            "total": 2,
            "page": 1
        }
    }

@pytest.fixture
def sample_config_template():
    """Provide sample configuration template."""
    return """
hostname {{ hostname }}
!
interface {{ interface_name }}
 description {{ description }}
 ip address {{ ip_address }} {{ subnet_mask }}
 no shutdown
!
"""

@pytest.fixture
def sample_workflow_context():
    """Provide sample workflow context variables."""
    return {
        "environment": "production",
        "deploy_config": True,
        "interfaces": ["GigE0/1", "GigE0/2", "GigE0/3"],
        "vlans": [100, 200, 300],
        "device_count": 10,
        "maintenance_window": True
    }
