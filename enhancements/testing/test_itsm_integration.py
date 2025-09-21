"""
Unit tests for ITSM integration tasks.

Tests all ITSM platform integrations including:
- ServiceNow change management and incident tracking
- Jira issue tracking and project management
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from enhancements.integrations.itsm_integration import (
    ServiceNowIntegration,
    JiraIntegration,
    servicenow_create_change,
    servicenow_update_change,
    jira_create_issue,
    jira_update_issue,
    jira_transition_issue
)
from enhancements.testing.test_framework import IntegrationTestBase


class TestServiceNowIntegration(IntegrationTestBase):
    """Test ServiceNow integration class."""
    
    def test_integration_validation_success(self):
        """Test successful ServiceNow integration validation."""
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "password123"
        }
        
        integration = ServiceNowIntegration(config)
        
        assert integration.instance_url == "https://company.service-now.com"
        assert integration.username == "admin"
        assert integration.password == "password123"
        assert integration.timeout == 30  # default
        assert integration.ssl_verify is True  # default
    
    def test_integration_validation_missing_instance_url(self):
        """Test ServiceNow integration validation with missing instance URL."""
        config = {"username": "admin", "password": "password"}
        
        with pytest.raises(ValueError, match="instance_url.*required"):
            ServiceNowIntegration(config)
    
    def test_integration_validation_missing_credentials(self):
        """Test ServiceNow integration validation with missing credentials."""
        config = {"instance_url": "https://company.service-now.com"}
        
        with pytest.raises(ValueError, match="username.*required"):
            ServiceNowIntegration(config)
    
    def test_get_auth(self):
        """Test ServiceNow authentication tuple generation."""
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "secret"
        }
        
        integration = ServiceNowIntegration(config)
        auth = integration.get_auth()
        
        assert auth == ("admin", "secret")
    
    def test_get_headers(self):
        """Test ServiceNow API headers generation."""
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "password"
        }
        
        integration = ServiceNowIntegration(config)
        headers = integration.get_headers()
        
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
    
    @patch('enhancements.integrations.itsm_integration.requests')
    def test_test_connection_success(self, mock_requests):
        """Test successful ServiceNow connection test."""
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "password"
        }
        
        mock_response = self.create_mock_response(200)
        mock_requests.get.return_value = mock_response
        
        integration = ServiceNowIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to ServiceNow" in result["message"]
        assert result["instance"] == "https://company.service-now.com"
    
    @patch('enhancements.integrations.itsm_integration.requests')
    def test_test_connection_failure(self, mock_requests):
        """Test ServiceNow connection test failure."""
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "wrong-password"
        }
        
        mock_response = self.create_mock_response(401)
        mock_requests.get.return_value = mock_response
        
        integration = ServiceNowIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is False
        assert "401" in result["message"]


class TestServiceNowTasks(IntegrationTestBase):
    """Test ServiceNow task functions."""
    
    @patch('enhancements.integrations.itsm_integration.ServiceNowIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_servicenow_create_change_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful change request creation."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.instance_url = "https://company.service-now.com"
        mock_integration.username = "admin"
        mock_integration.get_auth.return_value = ("admin", "password")
        mock_integration.get_headers.return_value = {"Content-Type": "application/json"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(201)
        mock_requests.post.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = {
            "result": {
                "number": "CHG0001234",
                "sys_id": "abc123def456",
                "state": "1"
            }
        }
        
        # Execute task
        result = servicenow_create_change(
            mock_task,
            short_description="Network maintenance",
            description="Automated network configuration update",
            category="Network",
            impact="3",
            urgency="3"
        )
        
        # Assertions
        self.assert_result_success(result, ["change_number", "sys_id", "state", "url"])
        assert result.result["change_number"] == "CHG0001234"
        assert result.result["sys_id"] == "abc123def456"
        assert result.result["state"] == "1"
        assert result.result["category"] == "Network"
        assert "change_request.do" in result.result["url"]
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "change_request" in call_args[0][0]
        
        # Verify request data
        request_data = call_args[1]["json"]
        assert request_data["short_description"] == "Network maintenance"
        assert request_data["category"] == "Network"
        assert request_data["impact"] == "3"
    
    @patch('enhancements.integrations.itsm_integration.ServiceNowIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_servicenow_update_change_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful change request update."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.instance_url = "https://company.service-now.com"
        mock_integration.get_auth.return_value = ("admin", "password")
        mock_integration.get_headers.return_value = {"Content-Type": "application/json"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock responses for search and update
        search_response = self.create_mock_response(200)
        update_response = self.create_mock_response(200)
        mock_requests.get.return_value = search_response
        mock_requests.put.return_value = update_response
        
        # Setup mock API response handlers
        mock_handle_response.side_effect = [
            {"result": [{"sys_id": "abc123def456", "number": "CHG0001234"}]},
            {"result": {"number": "CHG0001234", "state": "3"}}
        ]
        
        # Execute task
        result = servicenow_update_change(
            mock_task,
            change_number="CHG0001234",
            state="3",
            work_notes="Configuration deployment completed successfully"
        )
        
        # Assertions
        self.assert_result_success(result, ["change_number", "sys_id", "updated_fields", "new_state"])
        assert result.result["change_number"] == "CHG0001234"
        assert result.result["sys_id"] == "abc123def456"
        assert "state" in result.result["updated_fields"]
        assert "work_notes" in result.result["updated_fields"]
        assert result.result["new_state"] == "3"
        
        # Verify API calls
        assert mock_requests.get.call_count == 1  # Search call
        assert mock_requests.put.call_count == 1  # Update call
    
    @patch('enhancements.integrations.itsm_integration.ServiceNowIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_servicenow_update_change_not_found(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test change request update when change not found."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response for search (no results)
        search_response = self.create_mock_response(200)
        mock_requests.get.return_value = search_response
        
        # Setup mock API response handler (empty result)
        mock_handle_response.return_value = {"result": []}
        
        # Execute task
        result = servicenow_update_change(mock_task, change_number="CHG9999999")
        
        # Assertions
        self.assert_result_failed(result, "not found")


class TestJiraIntegration(IntegrationTestBase):
    """Test Jira integration class."""
    
    def test_integration_validation_success_with_password(self):
        """Test successful Jira integration validation with password."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin",
            "password": "password123"
        }
        
        integration = JiraIntegration(config)
        
        assert integration.server_url == "https://company.atlassian.net"
        assert integration.username == "admin"
        assert integration.password == "password123"
        assert integration.api_token is None
    
    def test_integration_validation_success_with_api_token(self):
        """Test successful Jira integration validation with API token."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin@company.com",
            "api_token": "api-token-123"
        }
        
        integration = JiraIntegration(config)
        
        assert integration.server_url == "https://company.atlassian.net"
        assert integration.username == "admin@company.com"
        assert integration.api_token == "api-token-123"
        assert integration.password is None
    
    def test_integration_validation_missing_server_url(self):
        """Test Jira integration validation with missing server URL."""
        config = {"username": "admin", "password": "password"}
        
        with pytest.raises(ValueError, match="server_url.*required"):
            JiraIntegration(config)
    
    def test_integration_validation_missing_auth(self):
        """Test Jira integration validation with missing authentication."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin"
        }
        
        with pytest.raises(ValueError, match="password.*api_token.*must be provided"):
            JiraIntegration(config)
    
    def test_get_auth_with_password(self):
        """Test Jira authentication with password."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin",
            "password": "secret"
        }
        
        integration = JiraIntegration(config)
        auth = integration.get_auth()
        
        assert auth == ("admin", "secret")
    
    def test_get_auth_with_api_token(self):
        """Test Jira authentication with API token."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin@company.com",
            "api_token": "token123"
        }
        
        integration = JiraIntegration(config)
        auth = integration.get_auth()
        
        assert auth == ("admin@company.com", "token123")
    
    @patch('enhancements.integrations.itsm_integration.requests')
    def test_test_connection_success(self, mock_requests):
        """Test successful Jira connection test."""
        config = {
            "server_url": "https://company.atlassian.net",
            "username": "admin",
            "api_token": "token123"
        }
        
        mock_response = self.create_mock_response(200, {
            "serverTitle": "JIRA",
            "version": "8.20.0",
            "buildNumber": "820000"
        })
        mock_requests.get.return_value = mock_response
        
        integration = JiraIntegration(config)
        result = integration.test_connection()
        
        assert result["success"] is True
        assert "Connected to Jira" in result["message"]
        assert result["server_title"] == "JIRA"
        assert result["version"] == "8.20.0"


class TestJiraTasks(IntegrationTestBase):
    """Test Jira task functions."""
    
    @patch('enhancements.integrations.itsm_integration.JiraIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_jira_create_issue_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful issue creation."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.server_url = "https://company.atlassian.net"
        mock_integration.get_auth.return_value = ("admin", "token")
        mock_integration.get_headers.return_value = {"Content-Type": "application/json"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(201)
        mock_requests.post.return_value = mock_response
        
        # Setup mock API response handler
        mock_handle_response.return_value = {
            "key": "NET-123",
            "id": "10001"
        }
        
        # Execute task
        result = jira_create_issue(
            mock_task,
            project_key="NET",
            issue_type="Task",
            summary="Network automation task",
            description="Automated network configuration deployment",
            priority="Medium",
            labels=["automation", "network"]
        )
        
        # Assertions
        self.assert_result_success(result, ["issue_key", "issue_id", "project_key", "url"])
        assert result.result["issue_key"] == "NET-123"
        assert result.result["issue_id"] == "10001"
        assert result.result["project_key"] == "NET"
        assert result.result["issue_type"] == "Task"
        assert result.result["priority"] == "Medium"
        assert "browse/NET-123" in result.result["url"]
        
        # Verify API call
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "issue" in call_args[0][0]
        
        # Verify request data
        request_data = call_args[1]["json"]
        fields = request_data["fields"]
        assert fields["project"]["key"] == "NET"
        assert fields["issuetype"]["name"] == "Task"
        assert fields["summary"] == "Network automation task"
        assert fields["labels"] == ["automation", "network"]
    
    @patch('enhancements.integrations.itsm_integration.JiraIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    def test_jira_update_issue_success(self, mock_requests, mock_integration_class, mock_task):
        """Test successful issue update."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.server_url = "https://company.atlassian.net"
        mock_integration.get_auth.return_value = ("admin", "token")
        mock_integration.get_headers.return_value = {"Content-Type": "application/json"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        mock_response = self.create_mock_response(204)  # No content for update
        mock_requests.put.return_value = mock_response
        
        # Execute task
        result = jira_update_issue(
            mock_task,
            issue_key="NET-123",
            summary="Updated network automation task",
            priority="High",
            assignee="john.doe"
        )
        
        # Assertions
        self.assert_result_success(result, ["issue_key", "updated_fields"])
        assert result.result["issue_key"] == "NET-123"
        assert "summary" in result.result["updated_fields"]
        assert "priority" in result.result["updated_fields"]
        assert "assignee" in result.result["updated_fields"]
        assert result.result["summary"] == "Updated network automation task"
        assert result.result["priority"] == "High"
        
        # Verify API call
        mock_requests.put.assert_called_once()
        call_args = mock_requests.put.call_args
        assert "NET-123" in call_args[0][0]
    
    @patch('enhancements.integrations.itsm_integration.JiraIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_jira_transition_issue_success(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test successful issue transition."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration.server_url = "https://company.atlassian.net"
        mock_integration.get_auth.return_value = ("admin", "token")
        mock_integration.get_headers.return_value = {"Content-Type": "application/json"}
        mock_integration.timeout = 30
        mock_integration.ssl_verify = True
        mock_integration_class.return_value = mock_integration
        
        # Setup mock responses
        transitions_response = self.create_mock_response(200)
        transition_response = self.create_mock_response(204)
        mock_requests.get.return_value = transitions_response
        mock_requests.post.return_value = transition_response
        
        # Setup mock API response handler for transitions
        mock_handle_response.return_value = {
            "transitions": [
                {"id": "11", "name": "Done"},
                {"id": "21", "name": "In Progress"}
            ]
        }
        
        # Execute task
        result = jira_transition_issue(
            mock_task,
            issue_key="NET-123",
            transition_name="Done",
            comment="Task completed successfully"
        )
        
        # Assertions
        self.assert_result_success(result, ["issue_key", "transition_name", "transition_id"])
        assert result.result["issue_key"] == "NET-123"
        assert result.result["transition_name"] == "Done"
        assert result.result["transition_id"] == "11"
        assert result.result["comment"] == "Task completed successfully"
        
        # Verify API calls
        assert mock_requests.get.call_count == 1  # Get transitions
        assert mock_requests.post.call_count == 1  # Execute transition
    
    @patch('enhancements.integrations.itsm_integration.JiraIntegration')
    @patch('enhancements.integrations.itsm_integration.requests')
    @patch('enhancements.integrations.itsm_integration.handle_api_response')
    def test_jira_transition_issue_invalid_transition(self, mock_handle_response, mock_requests, mock_integration_class, mock_task):
        """Test issue transition with invalid transition name."""
        # Setup mock integration
        mock_integration = Mock()
        mock_integration_class.return_value = mock_integration
        
        # Setup mock response
        transitions_response = self.create_mock_response(200)
        mock_requests.get.return_value = transitions_response
        
        # Setup mock API response handler with available transitions
        mock_handle_response.return_value = {
            "transitions": [
                {"id": "11", "name": "Done"},
                {"id": "21", "name": "In Progress"}
            ]
        }
        
        # Execute task with invalid transition
        result = jira_transition_issue(mock_task, issue_key="NET-123", transition_name="Invalid")
        
        # Assertions
        self.assert_result_failed(result, "not available")
        assert "Done" in result.result  # Should list available transitions
        assert "In Progress" in result.result
