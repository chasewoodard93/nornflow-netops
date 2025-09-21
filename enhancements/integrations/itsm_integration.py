"""
ITSM Integration for NornFlow.

This module provides integration with IT Service Management platforms:
- ServiceNow: Change management, incident tracking, and CMDB integration
- Jira: Issue tracking, project management, and workflow automation

ITSM integrations enable NornFlow workflows to create change requests,
track incidents, and maintain proper change management processes.
"""

from typing import Dict, Any, List, Optional, Union
from nornir.core.task import Task, Result
import logging
import json
from datetime import datetime, timedelta

from . import (
    register_integration,
    BaseIntegration,
    require_dependency,
    validate_url,
    validate_required_field,
    build_headers,
    handle_api_response,
    IntegrationError,
    DependencyError
)

logger = logging.getLogger(__name__)


@register_integration(
    name="servicenow",
    description="ServiceNow ITSM integration for change management",
    dependencies=["requests"],
    tasks=[
        "servicenow_create_change",
        "servicenow_update_change",
        "servicenow_get_change",
        "servicenow_create_incident",
        "servicenow_update_cmdb",
        "servicenow_get_approval_status"
    ]
)
class ServiceNowIntegration(BaseIntegration):
    """ServiceNow integration class."""
    
    def validate_config(self) -> None:
        """Validate ServiceNow configuration."""
        self.instance_url = validate_url(validate_required_field(self.config.get("instance_url"), "instance_url"))
        self.username = validate_required_field(self.config.get("username"), "username")
        self.password = validate_required_field(self.config.get("password"), "password")
        self.timeout = self.config.get("timeout", 30)
        self.ssl_verify = self.config.get("ssl_verify", True)
    
    def get_auth(self) -> tuple:
        """Get ServiceNow authentication."""
        return (self.username, self.password)
    
    def get_headers(self) -> Dict[str, str]:
        """Get ServiceNow API headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test ServiceNow connection."""
        try:
            import requests
            
            response = requests.get(
                f"{self.instance_url}/api/now/table/sys_user",
                params={"sysparm_limit": 1},
                auth=self.get_auth(),
                headers=self.get_headers(),
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Connected to ServiceNow",
                    "instance": self.instance_url
                }
            else:
                return {
                    "success": False,
                    "message": f"ServiceNow API returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to ServiceNow: {str(e)}"
            }


@register_integration(
    name="jira",
    description="Jira issue tracking and project management integration",
    dependencies=["requests"],
    tasks=[
        "jira_create_issue",
        "jira_update_issue",
        "jira_get_issue",
        "jira_transition_issue",
        "jira_add_comment",
        "jira_create_project"
    ]
)
class JiraIntegration(BaseIntegration):
    """Jira integration class."""
    
    def validate_config(self) -> None:
        """Validate Jira configuration."""
        self.server_url = validate_url(validate_required_field(self.config.get("server_url"), "server_url"))
        self.username = validate_required_field(self.config.get("username"), "username")
        
        # Support both password and API token authentication
        self.password = self.config.get("password")
        self.api_token = self.config.get("api_token")
        
        if not self.password and not self.api_token:
            raise ValueError("Either 'password' or 'api_token' must be provided")
        
        self.timeout = self.config.get("timeout", 30)
        self.ssl_verify = self.config.get("ssl_verify", True)
    
    def get_auth(self) -> tuple:
        """Get Jira authentication."""
        auth_token = self.api_token if self.api_token else self.password
        return (self.username, auth_token)
    
    def get_headers(self) -> Dict[str, str]:
        """Get Jira API headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Jira connection."""
        try:
            import requests
            
            response = requests.get(
                f"{self.server_url}/rest/api/2/serverInfo",
                auth=self.get_auth(),
                headers=self.get_headers(),
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            if response.status_code == 200:
                server_info = response.json()
                return {
                    "success": True,
                    "message": "Connected to Jira",
                    "server_title": server_info.get("serverTitle"),
                    "version": server_info.get("version"),
                    "build_number": server_info.get("buildNumber")
                }
            else:
                return {
                    "success": False,
                    "message": f"Jira API returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to Jira: {str(e)}"
            }


# ServiceNow Task Functions

@require_dependency("requests", "servicenow")
def servicenow_create_change(
    task: Task,
    short_description: str,
    description: str,
    category: str = "Network",
    impact: str = "3",
    urgency: str = "3",
    risk: str = "3",
    change_type: str = "Normal",
    assignment_group: Optional[str] = None,
    requested_by: Optional[str] = None,
    servicenow_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create a change request in ServiceNow.
    
    Args:
        task: Nornir task object
        short_description: Brief description of the change
        description: Detailed description of the change
        category: Change category (default: "Network")
        impact: Impact level (1-3, default: "3")
        urgency: Urgency level (1-3, default: "3")
        risk: Risk level (1-4, default: "3")
        change_type: Type of change (default: "Normal")
        assignment_group: Assignment group for the change
        requested_by: User requesting the change
        servicenow_config: ServiceNow configuration
        
    Returns:
        Result containing change request information
    """
    config = servicenow_config or getattr(task.host, "servicenow_config", {})
    
    try:
        integration = ServiceNowIntegration(config)
        import requests
        
        change_data = {
            "short_description": short_description,
            "description": description,
            "category": category,
            "impact": impact,
            "urgency": urgency,
            "risk": risk,
            "type": change_type,
            "state": "1",  # New
            "requested_by": requested_by or integration.username
        }
        
        if assignment_group:
            change_data["assignment_group"] = assignment_group
        
        response = requests.post(
            f"{integration.instance_url}/api/now/table/change_request",
            json=change_data,
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )
        
        result_data = handle_api_response(response, "servicenow")
        
        change_info = result_data.get("result", {})
        
        return Result(
            host=task.host,
            result={
                "change_number": change_info.get("number"),
                "sys_id": change_info.get("sys_id"),
                "state": change_info.get("state"),
                "short_description": short_description,
                "category": category,
                "impact": impact,
                "urgency": urgency,
                "risk": risk,
                "change_type": change_type,
                "url": f"{integration.instance_url}/nav_to.do?uri=change_request.do?sys_id={change_info.get('sys_id')}",
                "message": f"Change request {change_info.get('number')} created successfully"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create ServiceNow change request: {str(e)}"
        )


@require_dependency("requests", "servicenow")
def servicenow_update_change(
    task: Task,
    change_number: Optional[str] = None,
    sys_id: Optional[str] = None,
    updates: Optional[Dict[str, Any]] = None,
    state: Optional[str] = None,
    work_notes: Optional[str] = None,
    servicenow_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Update a change request in ServiceNow.
    
    Args:
        task: Nornir task object
        change_number: Change request number
        sys_id: System ID of the change request
        updates: Dictionary of fields to update
        state: New state for the change request
        work_notes: Work notes to add
        servicenow_config: ServiceNow configuration
        
    Returns:
        Result containing update status
    """
    config = servicenow_config or getattr(task.host, "servicenow_config", {})
    updates = updates or {}
    
    try:
        integration = ServiceNowIntegration(config)
        import requests
        
        # Find change request if sys_id not provided
        if not sys_id and change_number:
            response = requests.get(
                f"{integration.instance_url}/api/now/table/change_request",
                params={"sysparm_query": f"number={change_number}"},
                auth=integration.get_auth(),
                headers=integration.get_headers(),
                timeout=integration.timeout,
                verify=integration.ssl_verify
            )
            
            search_result = handle_api_response(response, "servicenow")
            changes = search_result.get("result", [])
            
            if not changes:
                return Result(
                    host=task.host,
                    failed=True,
                    result=f"Change request '{change_number}' not found"
                )
            
            sys_id = changes[0]["sys_id"]
        
        if not sys_id:
            return Result(
                host=task.host,
                failed=True,
                result="Either change_number or sys_id must be provided"
            )
        
        # Prepare update data
        update_data = updates.copy()
        if state:
            update_data["state"] = state
        if work_notes:
            update_data["work_notes"] = work_notes
        
        # Update change request
        response = requests.put(
            f"{integration.instance_url}/api/now/table/change_request/{sys_id}",
            json=update_data,
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )
        
        result_data = handle_api_response(response, "servicenow")
        change_info = result_data.get("result", {})
        
        return Result(
            host=task.host,
            result={
                "change_number": change_info.get("number"),
                "sys_id": sys_id,
                "updated_fields": list(update_data.keys()),
                "new_state": change_info.get("state"),
                "message": f"Change request {change_info.get('number')} updated successfully"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to update ServiceNow change request: {str(e)}"
        )


# Jira Task Functions

@require_dependency("requests", "jira")
def jira_create_issue(
    task: Task,
    project_key: str,
    issue_type: str,
    summary: str,
    description: str,
    priority: str = "Medium",
    assignee: Optional[str] = None,
    labels: Optional[List[str]] = None,
    components: Optional[List[str]] = None,
    custom_fields: Optional[Dict[str, Any]] = None,
    jira_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create an issue in Jira.

    Args:
        task: Nornir task object
        project_key: Jira project key
        issue_type: Type of issue (e.g., "Task", "Bug", "Story")
        summary: Issue summary
        description: Issue description
        priority: Issue priority (default: "Medium")
        assignee: Username to assign the issue to
        labels: List of labels to add
        components: List of components
        custom_fields: Dictionary of custom field values
        jira_config: Jira configuration

    Returns:
        Result containing issue information
    """
    config = jira_config or getattr(task.host, "jira_config", {})

    try:
        integration = JiraIntegration(config)
        import requests

        issue_data = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": description,
                "priority": {"name": priority}
            }
        }

        if assignee:
            issue_data["fields"]["assignee"] = {"name": assignee}

        if labels:
            issue_data["fields"]["labels"] = labels

        if components:
            issue_data["fields"]["components"] = [{"name": comp} for comp in components]

        if custom_fields:
            issue_data["fields"].update(custom_fields)

        response = requests.post(
            f"{integration.server_url}/rest/api/2/issue",
            json=issue_data,
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        result_data = handle_api_response(response, "jira")

        return Result(
            host=task.host,
            result={
                "issue_key": result_data.get("key"),
                "issue_id": result_data.get("id"),
                "project_key": project_key,
                "issue_type": issue_type,
                "summary": summary,
                "priority": priority,
                "assignee": assignee,
                "url": f"{integration.server_url}/browse/{result_data.get('key')}",
                "message": f"Issue {result_data.get('key')} created successfully"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create Jira issue: {str(e)}"
        )


@require_dependency("requests", "jira")
def jira_update_issue(
    task: Task,
    issue_key: str,
    updates: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[List[str]] = None,
    jira_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Update an issue in Jira.

    Args:
        task: Nornir task object
        issue_key: Jira issue key
        updates: Dictionary of fields to update
        summary: New summary
        description: New description
        priority: New priority
        assignee: New assignee
        labels: New labels
        jira_config: Jira configuration

    Returns:
        Result containing update status
    """
    config = jira_config or getattr(task.host, "jira_config", {})

    try:
        integration = JiraIntegration(config)
        import requests

        update_data = {"fields": {}}

        if updates:
            update_data["fields"].update(updates)

        if summary:
            update_data["fields"]["summary"] = summary

        if description:
            update_data["fields"]["description"] = description

        if priority:
            update_data["fields"]["priority"] = {"name": priority}

        if assignee:
            update_data["fields"]["assignee"] = {"name": assignee}

        if labels:
            update_data["fields"]["labels"] = labels

        response = requests.put(
            f"{integration.server_url}/rest/api/2/issue/{issue_key}",
            json=update_data,
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        response.raise_for_status()

        return Result(
            host=task.host,
            result={
                "issue_key": issue_key,
                "updated_fields": list(update_data["fields"].keys()),
                "summary": summary,
                "priority": priority,
                "assignee": assignee,
                "message": f"Issue {issue_key} updated successfully"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to update Jira issue: {str(e)}"
        )


@require_dependency("requests", "jira")
def jira_transition_issue(
    task: Task,
    issue_key: str,
    transition_name: str,
    comment: Optional[str] = None,
    jira_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Transition an issue in Jira.

    Args:
        task: Nornir task object
        issue_key: Jira issue key
        transition_name: Name of the transition to execute
        comment: Optional comment to add during transition
        jira_config: Jira configuration

    Returns:
        Result containing transition status
    """
    config = jira_config or getattr(task.host, "jira_config", {})

    try:
        integration = JiraIntegration(config)
        import requests

        # Get available transitions
        response = requests.get(
            f"{integration.server_url}/rest/api/2/issue/{issue_key}/transitions",
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        transitions_data = handle_api_response(response, "jira")
        transitions = transitions_data.get("transitions", [])

        # Find the transition ID
        transition_id = None
        for transition in transitions:
            if transition["name"].lower() == transition_name.lower():
                transition_id = transition["id"]
                break

        if not transition_id:
            available_transitions = [t["name"] for t in transitions]
            return Result(
                host=task.host,
                failed=True,
                result=f"Transition '{transition_name}' not available. Available: {available_transitions}"
            )

        # Execute transition
        transition_data = {
            "transition": {"id": transition_id}
        }

        if comment:
            transition_data["update"] = {
                "comment": [{"add": {"body": comment}}]
            }

        response = requests.post(
            f"{integration.server_url}/rest/api/2/issue/{issue_key}/transitions",
            json=transition_data,
            auth=integration.get_auth(),
            headers=integration.get_headers(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        response.raise_for_status()

        return Result(
            host=task.host,
            result={
                "issue_key": issue_key,
                "transition_name": transition_name,
                "transition_id": transition_id,
                "comment": comment,
                "message": f"Issue {issue_key} transitioned to '{transition_name}'"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to transition Jira issue: {str(e)}"
        )
