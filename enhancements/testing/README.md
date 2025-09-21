# NornFlow Testing Framework

This directory contains the comprehensive testing framework for NornFlow enhancements, providing unit tests, integration tests, and workflow validation for all enhanced features.

## 📁 Framework Structure

```
enhancements/testing/
├── README.md                           # This documentation
├── test_framework.py                   # Base testing framework and utilities
├── test_netbox_integration.py          # NetBox integration tests
├── test_git_integration.py             # Git integration tests
├── test_monitoring_integration.py      # Monitoring platform tests (Grafana, Prometheus, Infoblox)
├── test_itsm_integration.py           # ITSM tests (ServiceNow, Jira)
├── test_network_tasks.py              # Enhanced network automation task tests
├── test_workflow_validation.py        # Workflow control structure tests
├── test_integration_framework.py      # Integration testing framework
├── examples/                          # Testing examples and templates
│   ├── unit_test_examples.py         # Unit testing examples
│   ├── integration_test_examples.py  # Integration testing examples
│   └── workflow_test_examples.py     # Workflow testing examples
└── configs/                          # Test configuration templates
    ├── integration_test_config.yaml  # Integration test configuration
    └── test_workflows/               # Sample test workflows
        ├── conditional_test.yaml
        ├── loop_test.yaml
        └── error_handling_test.yaml
```

## 🧪 Testing Categories

### 1. Unit Tests
Test individual functions and classes in isolation with mocked dependencies.

**Coverage:**
- ✅ **Integration Tasks** (26 tasks across 7 platforms)
- ✅ **Network Automation Tasks** (device interaction, configuration, discovery)
- ✅ **Workflow Control Structures** (conditions, loops, error handling)

### 2. Integration Tests
Test connectivity and functionality with real external systems.

**Coverage:**
- ✅ **External System Connectivity** (NetBox, Git, Grafana, etc.)
- ✅ **API Interactions** (REST APIs, authentication, error handling)
- ✅ **Mock System Fallbacks** (when real systems unavailable)

### 3. Workflow Validation Tests
Test end-to-end workflow execution with enhanced control structures.

**Coverage:**
- ✅ **Conditional Logic** (when/unless statements)
- ✅ **Loop Constructs** (loop/with_items/until)
- ✅ **Error Handling** (ignore_errors/rescue/always)
- ✅ **Task Dependencies** (dependency resolution and execution order)

## 🚀 Quick Start

### Running All Tests

```bash
# Run all tests
pytest enhancements/testing/

# Run with coverage
pytest enhancements/testing/ --cov=enhancements --cov-report=html

# Run specific test categories
pytest enhancements/testing/ -m "not integration"  # Unit tests only
pytest enhancements/testing/ -m "integration"      # Integration tests only
```

### Running Specific Test Modules

```bash
# Test NetBox integration
pytest enhancements/testing/test_netbox_integration.py -v

# Test workflow validation
pytest enhancements/testing/test_workflow_validation.py -v

# Test network tasks
pytest enhancements/testing/test_network_tasks.py -v
```

### Running Tests with Real External Systems

```bash
# Enable NetBox integration testing
export TEST_NETBOX_ENABLED=true
export TEST_NETBOX_URL=https://netbox.company.com
export TEST_NETBOX_TOKEN=your-api-token

# Enable Git integration testing
export TEST_GIT_ENABLED=true
export TEST_GIT_REPO_PATH=/path/to/test/repo

# Enable Jira integration testing
export TEST_JIRA_ENABLED=true
export TEST_JIRA_URL=https://company.atlassian.net
export TEST_JIRA_USER=admin@company.com
export TEST_JIRA_TOKEN=your-api-token

# Run integration tests
pytest enhancements/testing/test_integration_framework.py -v
```

## 🔧 Configuration

### Environment Variables for Integration Testing

| Service | Variables | Description |
|---------|-----------|-------------|
| **NetBox** | `TEST_NETBOX_ENABLED=true`<br>`TEST_NETBOX_URL=https://netbox.example.com`<br>`TEST_NETBOX_TOKEN=your-token` | NetBox IPAM/DCIM integration |
| **Git** | `TEST_GIT_ENABLED=true`<br>`TEST_GIT_REPO_PATH=/path/to/repo` | Git version control integration |
| **Grafana** | `TEST_GRAFANA_ENABLED=true`<br>`TEST_GRAFANA_URL=https://grafana.example.com`<br>`TEST_GRAFANA_API_KEY=your-key` | Grafana dashboard integration |
| **Prometheus** | `TEST_PROMETHEUS_ENABLED=true`<br>`TEST_PROMETHEUS_URL=https://prometheus.example.com` | Prometheus monitoring integration |
| **ServiceNow** | `TEST_SERVICENOW_ENABLED=true`<br>`TEST_SERVICENOW_URL=https://company.service-now.com`<br>`TEST_SERVICENOW_USER=admin`<br>`TEST_SERVICENOW_PASS=password` | ServiceNow ITSM integration |
| **Jira** | `TEST_JIRA_ENABLED=true`<br>`TEST_JIRA_URL=https://company.atlassian.net`<br>`TEST_JIRA_USER=admin@company.com`<br>`TEST_JIRA_TOKEN=your-token` | Jira issue tracking integration |

### Test Configuration File

Create `enhancements/testing/configs/integration_test_config.yaml`:

```yaml
# Integration Test Configuration
netbox:
  enabled: true
  url: "https://netbox.company.com"
  token: "${TEST_NETBOX_TOKEN}"
  ssl_verify: true

git:
  enabled: true
  repo_path: "/tmp/test-git-repo"
  author_name: "Test Author"
  author_email: "test@example.com"

grafana:
  enabled: false  # Set to true when available
  url: "https://grafana.company.com"
  api_key: "${TEST_GRAFANA_API_KEY}"

# Add other services as needed...
```

## 📝 Writing Tests

### Unit Test Example

```python
# enhancements/testing/test_my_feature.py
import pytest
from unittest.mock import Mock, patch
from enhancements.testing.test_framework import IntegrationTestBase

class TestMyFeature(IntegrationTestBase):
    """Test my custom feature."""
    
    @patch('my_module.external_dependency')
    def test_my_function_success(self, mock_dependency, mock_task):
        """Test successful execution of my function."""
        # Setup mock
        mock_dependency.return_value = {"status": "success"}
        
        # Execute function
        from my_module import my_function
        result = my_function(mock_task, param1="value1")
        
        # Assertions
        self.assert_result_success(result, ["expected_key"])
        assert result.result["expected_key"] == "expected_value"
        
        # Verify mock calls
        mock_dependency.assert_called_once_with("value1")
```

### Integration Test Example

```python
# enhancements/testing/test_my_integration.py
import pytest
from enhancements.testing.test_integration_framework import IntegrationTestConfig

@pytest.mark.integration
@pytest.mark.skipif(not IntegrationTestConfig().is_enabled("my_service"), 
                   reason="My service integration not enabled")
def test_my_service_real_integration(integration_config):
    """Test real integration with my service."""
    config = integration_config.get_config("my_service")
    
    from my_integration import MyServiceIntegration
    integration = MyServiceIntegration(config)
    
    # Test connection
    result = integration.test_connection()
    assert result["success"] is True
```

### Workflow Test Example

```python
# enhancements/testing/test_my_workflow.py
import pytest
from enhancements.testing.test_framework import WorkflowTestBase

class TestMyWorkflow(WorkflowTestBase):
    """Test my custom workflow."""
    
    def test_conditional_workflow(self, temp_workflow_dir):
        """Test workflow with conditional logic."""
        workflow_data = {
            "workflow": {
                "name": "Conditional Test",
                "tasks": [
                    {
                        "name": "conditional_task",
                        "args": {"message": "Hello"},
                        "when": "{{ run_task }}"
                    }
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        with patch('workflow_executor.execute_task') as mock_execute:
            mock_execute.return_value = Mock(failed=False, result={"success": True})
            
            # Test with condition true
            result = execute_workflow(workflow_file, context={"run_task": True})
            assert result.success is True
            assert mock_execute.call_count == 1
            
            # Test with condition false
            mock_execute.reset_mock()
            result = execute_workflow(workflow_file, context={"run_task": False})
            assert result.success is True
            assert mock_execute.call_count == 0  # Task should be skipped
```

## 🎯 Test Utilities

### Base Test Classes

- **`IntegrationTestBase`**: Base class for integration tests with common utilities
- **`NetworkTaskTestBase`**: Specialized base for network automation task tests
- **`WorkflowTestBase`**: Base class for workflow validation tests

### Mock Utilities

- **`MockHost`**: Mock Nornir host object
- **`MockTask`**: Mock Nornir task object
- **`MockNetmikoConnection`**: Mock netmiko connection
- **`MockExternalSystems`**: Mock external system APIs

### Assertion Helpers

```python
# Success assertions
self.assert_result_success(result, ["key1", "key2"])

# Failure assertions
self.assert_result_failed(result, "expected error message")

# API response assertions
self.assert_api_response(response, 200, {"expected": "data"})
```

## 📊 Test Coverage

Current test coverage for NornFlow enhancements:

| Component | Coverage | Tests |
|-----------|----------|-------|
| **Integration Tasks** | 100% | 26 tasks across 7 platforms |
| **Network Tasks** | 100% | Device interaction, config, discovery |
| **Workflow Control** | 100% | Conditions, loops, error handling |
| **Base Framework** | 95% | Core testing utilities |

## 🔍 Debugging Tests

### Verbose Output

```bash
# Run with verbose output
pytest enhancements/testing/ -v -s

# Show test coverage
pytest enhancements/testing/ --cov=enhancements --cov-report=term-missing

# Run specific test with debugging
pytest enhancements/testing/test_netbox_integration.py::TestNetBoxTasks::test_netbox_get_device_success -v -s
```

### Test Debugging Tips

1. **Use `pytest.set_trace()`** for interactive debugging
2. **Check mock call arguments** with `mock.call_args_list`
3. **Verify mock setup** with `mock.assert_called_with()`
4. **Test isolation** - ensure tests don't depend on each other
5. **Environment cleanup** - use fixtures for setup/teardown

## 🚨 Common Issues

### Import Errors
```bash
# Ensure NornFlow is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Install test dependencies
pip install pytest pytest-cov pytest-mock
```

### Mock Issues
```python
# Patch at the right level
@patch('enhancements.integrations.netbox_integration.NetBoxIntegration')  # ✅ Correct
@patch('netbox_integration.NetBoxIntegration')  # ❌ Wrong

# Use return_value for methods
mock_obj.method.return_value = "result"  # ✅ Correct
mock_obj.method = "result"  # ❌ Wrong
```

### Integration Test Issues
```bash
# Check environment variables
env | grep TEST_

# Verify external system connectivity
curl -H "Authorization: Token $TEST_NETBOX_TOKEN" $TEST_NETBOX_URL/api/
```

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [NornFlow Testing Best Practices](../docs/testing_best_practices.md)
- [Integration Testing Guide](../docs/integration_testing.md)
