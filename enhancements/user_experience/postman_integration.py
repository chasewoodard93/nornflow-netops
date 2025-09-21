"""
Postman Integration for NornFlow API Testing.

This module provides integration with Postman for testing NornFlow API tasks:
- Auto-generate Postman collections from NornFlow API tasks
- Create test cases for Jinja2 templates and API payloads
- Generate environment variables for different network environments
- Export collections for team collaboration and CI/CD integration

This enables network engineers to test and debug API payloads and Jinja2 templates
using the familiar Postman interface before deploying workflows.
"""

import json
import yaml
import uuid
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
import re

logger = logging.getLogger(__name__)


@dataclass
class PostmanVariable:
    """Postman collection variable."""
    key: str
    value: str
    type: str = "string"
    description: str = ""


@dataclass
class PostmanHeader:
    """Postman request header."""
    key: str
    value: str
    description: str = ""
    disabled: bool = False


@dataclass
class PostmanAuth:
    """Postman authentication configuration."""
    type: str
    bearer: Optional[Dict[str, str]] = None
    basic: Optional[Dict[str, str]] = None
    apikey: Optional[Dict[str, str]] = None


@dataclass
class PostmanTest:
    """Postman test script."""
    listen: str = "test"
    script: Dict[str, Any] = None


@dataclass
class PostmanRequest:
    """Postman request configuration."""
    method: str
    header: List[PostmanHeader]
    body: Optional[Dict[str, Any]] = None
    url: Dict[str, Any] = None
    auth: Optional[PostmanAuth] = None
    description: str = ""


@dataclass
class PostmanItem:
    """Postman collection item (request or folder)."""
    name: str
    request: Optional[PostmanRequest] = None
    item: Optional[List['PostmanItem']] = None
    event: Optional[List[PostmanTest]] = None
    description: str = ""


@dataclass
class PostmanCollection:
    """Postman collection structure."""
    info: Dict[str, Any]
    item: List[PostmanItem]
    variable: List[PostmanVariable] = None
    auth: Optional[PostmanAuth] = None
    event: Optional[List[PostmanTest]] = None


class PostmanIntegration:
    """
    Postman integration for NornFlow API testing.
    
    Provides methods to:
    - Generate Postman collections from NornFlow API tasks
    - Create test environments for different network setups
    - Export collections for team collaboration
    - Generate test scripts for API validation
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Postman integration.
        
        Args:
            config: Configuration for Postman integration
        """
        self.config = config or {}
        self.collections_dir = Path(self.config.get("collections_dir", "postman_collections"))
        self.environments_dir = Path(self.config.get("environments_dir", "postman_environments"))
        
        # Ensure directories exist
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        self.environments_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_collection_from_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Generate Postman collection from NornFlow workflow containing API tasks.
        
        Args:
            workflow_file: Path to NornFlow workflow YAML file
            
        Returns:
            Generation result with collection data
        """
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            workflow = workflow_data.get("workflow", {})
            workflow_name = workflow.get("name", workflow_file.stem)
            
            # Create collection info
            collection_info = {
                "name": f"NornFlow API Tests - {workflow_name}",
                "description": f"API testing collection for NornFlow workflow: {workflow_name}\n\n{workflow.get('description', '')}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                "_postman_id": str(uuid.uuid4()),
                "version": {
                    "major": 1,
                    "minor": 0,
                    "patch": 0
                }
            }
            
            # Extract API tasks from workflow
            api_tasks = self._extract_api_tasks(workflow.get("tasks", []))
            
            if not api_tasks:
                return {
                    "success": False,
                    "message": "No API tasks found in workflow"
                }
            
            # Generate collection items
            collection_items = []
            variables = []
            
            # Create folder for each API integration
            api_folders = {}
            
            for task in api_tasks:
                integration = self._identify_integration(task)
                
                if integration not in api_folders:
                    api_folders[integration] = {
                        "name": f"{integration.title()} API Tests",
                        "description": f"API tests for {integration} integration",
                        "item": []
                    }
                
                # Generate request for this task
                request_item = self._generate_request_item(task, workflow.get("vars", {}))
                if request_item:
                    api_folders[integration]["item"].append(request_item)
                    
                    # Extract variables from task
                    task_vars = self._extract_variables_from_task(task)
                    variables.extend(task_vars)
            
            # Add folders to collection
            for folder_data in api_folders.values():
                collection_items.append(PostmanItem(
                    name=folder_data["name"],
                    description=folder_data["description"],
                    item=[PostmanItem(**item) for item in folder_data["item"]]
                ))
            
            # Remove duplicate variables
            unique_variables = []
            seen_keys = set()
            for var in variables:
                if var.key not in seen_keys:
                    unique_variables.append(var)
                    seen_keys.add(var.key)
            
            # Create collection
            collection = PostmanCollection(
                info=collection_info,
                item=collection_items,
                variable=unique_variables
            )
            
            # Save collection
            collection_file = self.collections_dir / f"{workflow_file.stem}_api_tests.json"
            collection_dict = self._collection_to_dict(collection)
            
            with open(collection_file, 'w') as f:
                json.dump(collection_dict, f, indent=2)
            
            return {
                "success": True,
                "collection_file": str(collection_file),
                "collection_name": collection_info["name"],
                "api_tasks_count": len(api_tasks),
                "variables_count": len(unique_variables),
                "message": f"Postman collection generated successfully for {len(api_tasks)} API tasks"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Collection generation failed: {str(e)}"
            }
    
    def _extract_api_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract API-related tasks from workflow tasks."""
        api_tasks = []
        
        # Known API task patterns
        api_task_patterns = [
            r".*_api_.*",
            r".*_rest_.*", 
            r".*_http_.*",
            r"netbox_.*",
            r"grafana_.*",
            r"servicenow_.*",
            r"jira_.*",
            r"infoblox_.*"
        ]
        
        for task in tasks:
            task_name = task.get("task", "")
            
            # Check if task is API-related
            is_api_task = any(re.match(pattern, task_name, re.IGNORECASE) for pattern in api_task_patterns)
            
            # Also check for HTTP methods in task variables
            task_vars = task.get("vars", {})
            has_http_method = any(key in task_vars for key in ["method", "http_method", "url", "endpoint"])
            
            if is_api_task or has_http_method:
                api_tasks.append(task)
        
        return api_tasks
    
    def _identify_integration(self, task: Dict[str, Any]) -> str:
        """Identify which integration this task belongs to."""
        task_name = task.get("task", "").lower()
        
        if "netbox" in task_name:
            return "netbox"
        elif "grafana" in task_name:
            return "grafana"
        elif "servicenow" in task_name:
            return "servicenow"
        elif "jira" in task_name:
            return "jira"
        elif "infoblox" in task_name:
            return "infoblox"
        elif any(keyword in task_name for keyword in ["api", "rest", "http"]):
            return "generic_api"
        else:
            return "custom"
    
    def _generate_request_item(self, task: Dict[str, Any], workflow_vars: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate Postman request item from NornFlow task."""
        task_name = task.get("name", task.get("task", "Unknown Task"))
        task_vars = task.get("vars", {})
        
        # Determine HTTP method
        method = task_vars.get("method", task_vars.get("http_method", "GET")).upper()
        
        # Build URL
        base_url = task_vars.get("url", task_vars.get("base_url", ""))
        endpoint = task_vars.get("endpoint", task_vars.get("path", ""))
        
        if not base_url:
            # Try to infer from integration type
            integration = self._identify_integration(task)
            base_url = f"{{{{ {integration}_url }}}}"
        
        url_parts = {
            "raw": f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}",
            "host": [f"{{{{ {self._identify_integration(task)}_host }}}}"],
            "path": endpoint.split('/') if endpoint else []
        }
        
        # Build headers
        headers = []
        
        # Content-Type header
        if method in ["POST", "PUT", "PATCH"]:
            headers.append(PostmanHeader(
                key="Content-Type",
                value="application/json",
                description="Request content type"
            ))
        
        # Authentication headers
        integration = self._identify_integration(task)
        if integration == "netbox":
            headers.append(PostmanHeader(
                key="Authorization",
                value="Token {{ netbox_token }}",
                description="NetBox API token"
            ))
        elif integration == "grafana":
            headers.append(PostmanHeader(
                key="Authorization",
                value="Bearer {{ grafana_api_key }}",
                description="Grafana API key"
            ))
        elif integration == "jira":
            headers.append(PostmanHeader(
                key="Authorization",
                value="Basic {{ jira_auth_token }}",
                description="Jira basic auth token"
            ))
        
        # Custom headers from task
        custom_headers = task_vars.get("headers", {})
        for key, value in custom_headers.items():
            headers.append(PostmanHeader(
                key=key,
                value=str(value),
                description=f"Custom header from task"
            ))
        
        # Build request body
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            payload = task_vars.get("payload", task_vars.get("data", task_vars.get("body")))
            if payload:
                body = {
                    "mode": "raw",
                    "raw": json.dumps(payload, indent=2) if isinstance(payload, dict) else str(payload),
                    "options": {
                        "raw": {
                            "language": "json"
                        }
                    }
                }
        
        # Generate test scripts
        test_scripts = self._generate_test_scripts(task, integration)
        
        # Create request
        request = PostmanRequest(
            method=method,
            header=headers,
            body=body,
            url=url_parts,
            description=f"API request for NornFlow task: {task_name}"
        )
        
        return {
            "name": task_name,
            "request": asdict(request),
            "event": test_scripts,
            "description": task.get("description", f"Generated from NornFlow task: {task.get('task', '')}")
        }
    
    def _generate_test_scripts(self, task: Dict[str, Any], integration: str) -> List[Dict[str, Any]]:
        """Generate Postman test scripts for the request."""
        test_script = """
// NornFlow API Test Script
pm.test("Status code is successful", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201, 202, 204]);
});

pm.test("Response time is less than 5000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(5000);
});

pm.test("Response has valid JSON", function () {
    pm.response.to.have.jsonBody();
});

// Integration-specific tests
"""
        
        if integration == "netbox":
            test_script += """
pm.test("NetBox response structure", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('results');
});
"""
        elif integration == "grafana":
            test_script += """
pm.test("Grafana API response", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('status');
});
"""
        elif integration == "servicenow":
            test_script += """
pm.test("ServiceNow response structure", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('result');
});
"""
        
        # Add variable extraction if needed
        task_vars = task.get("vars", {})
        if "extract_variable" in task_vars:
            extract_var = task_vars["extract_variable"]
            test_script += f"""
// Extract variable for next request
pm.test("Extract {extract_var}", function () {{
    const jsonData = pm.response.json();
    pm.environment.set("{extract_var}", jsonData.{extract_var});
}});
"""
        
        return [{
            "listen": "test",
            "script": {
                "exec": test_script.strip().split('\n'),
                "type": "text/javascript"
            }
        }]
    
    def _extract_variables_from_task(self, task: Dict[str, Any]) -> List[PostmanVariable]:
        """Extract variables from task for Postman environment."""
        variables = []
        task_vars = task.get("vars", {})
        integration = self._identify_integration(task)
        
        # Common variables based on integration
        if integration == "netbox":
            variables.extend([
                PostmanVariable("netbox_url", "https://netbox.company.com", "string", "NetBox instance URL"),
                PostmanVariable("netbox_token", "your-netbox-token", "string", "NetBox API token"),
                PostmanVariable("netbox_host", "netbox.company.com", "string", "NetBox hostname")
            ])
        elif integration == "grafana":
            variables.extend([
                PostmanVariable("grafana_url", "https://grafana.company.com", "string", "Grafana instance URL"),
                PostmanVariable("grafana_api_key", "your-grafana-key", "string", "Grafana API key"),
                PostmanVariable("grafana_host", "grafana.company.com", "string", "Grafana hostname")
            ])
        elif integration == "servicenow":
            variables.extend([
                PostmanVariable("servicenow_url", "https://company.service-now.com", "string", "ServiceNow instance URL"),
                PostmanVariable("servicenow_user", "api-user", "string", "ServiceNow username"),
                PostmanVariable("servicenow_pass", "api-password", "string", "ServiceNow password"),
                PostmanVariable("servicenow_host", "company.service-now.com", "string", "ServiceNow hostname")
            ])
        elif integration == "jira":
            variables.extend([
                PostmanVariable("jira_url", "https://company.atlassian.net", "string", "Jira instance URL"),
                PostmanVariable("jira_user", "api-user", "string", "Jira username"),
                PostmanVariable("jira_token", "api-token", "string", "Jira API token"),
                PostmanVariable("jira_auth_token", "base64-encoded-credentials", "string", "Jira basic auth token"),
                PostmanVariable("jira_host", "company.atlassian.net", "string", "Jira hostname")
            ])
        
        # Extract custom variables from task
        for key, value in task_vars.items():
            if isinstance(value, str) and value.startswith("{{ ") and value.endswith(" }}"):
                var_name = value.strip("{{ }}")
                variables.append(PostmanVariable(
                    var_name, 
                    f"value-for-{var_name}", 
                    "string", 
                    f"Variable from task: {task.get('name', task.get('task', ''))}"
                ))
        
        return variables
    
    def _collection_to_dict(self, collection: PostmanCollection) -> Dict[str, Any]:
        """Convert PostmanCollection to dictionary for JSON export."""
        def convert_item(item):
            if isinstance(item, PostmanItem):
                result = {"name": item.name}
                if item.description:
                    result["description"] = item.description
                if item.request:
                    result["request"] = item.request
                if item.item:
                    result["item"] = [convert_item(sub_item) for sub_item in item.item]
                if item.event:
                    result["event"] = item.event
                return result
            return item
        
        result = {
            "info": collection.info,
            "item": [convert_item(item) for item in collection.item]
        }
        
        if collection.variable:
            result["variable"] = [asdict(var) for var in collection.variable]
        if collection.auth:
            result["auth"] = asdict(collection.auth)
        if collection.event:
            result["event"] = collection.event
        
        return result

    def generate_environment(self, environment_name: str, variables: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate Postman environment file.

        Args:
            environment_name: Name of the environment
            variables: Dictionary of environment variables

        Returns:
            Environment generation result
        """
        try:
            environment = {
                "id": str(uuid.uuid4()),
                "name": environment_name,
                "values": [
                    {
                        "key": key,
                        "value": value,
                        "enabled": True,
                        "type": "text" if not any(secret in key.lower() for secret in ["password", "token", "key", "secret"]) else "secret"
                    }
                    for key, value in variables.items()
                ],
                "_postman_variable_scope": "environment",
                "_postman_exported_at": datetime.now().isoformat(),
                "_postman_exported_using": "NornFlow Postman Integration"
            }

            env_file = self.environments_dir / f"{environment_name.lower().replace(' ', '_')}.postman_environment.json"
            with open(env_file, 'w') as f:
                json.dump(environment, f, indent=2)

            return {
                "success": True,
                "environment_file": str(env_file),
                "environment_name": environment_name,
                "variables_count": len(variables),
                "message": f"Postman environment '{environment_name}' generated successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Environment generation failed: {str(e)}"
            }

    def generate_environments_from_config(self, config_file: Path) -> Dict[str, Any]:
        """
        Generate multiple Postman environments from configuration file.

        Args:
            config_file: Path to environment configuration YAML file

        Returns:
            Batch environment generation result
        """
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

            environments = config.get("environments", {})
            results = []

            for env_name, env_vars in environments.items():
                result = self.generate_environment(env_name, env_vars)
                results.append({
                    "environment": env_name,
                    "result": result
                })

            successful = sum(1 for r in results if r["result"]["success"])

            return {
                "success": successful > 0,
                "total_environments": len(environments),
                "successful_generations": successful,
                "failed_generations": len(environments) - successful,
                "results": results,
                "message": f"Generated {successful}/{len(environments)} environments successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Batch environment generation failed: {str(e)}"
            }

    def generate_collections_from_workflows(self, workflows_dir: Path) -> Dict[str, Any]:
        """
        Generate Postman collections from all workflows in a directory.

        Args:
            workflows_dir: Directory containing NornFlow workflow files

        Returns:
            Batch collection generation result
        """
        results = []

        if not workflows_dir.exists():
            return {
                "success": False,
                "message": f"Workflows directory not found: {workflows_dir}"
            }

        # Find all workflow files
        workflow_files = list(workflows_dir.glob("*.yaml")) + list(workflows_dir.glob("*.yml"))

        if not workflow_files:
            return {
                "success": False,
                "message": f"No workflow files found in: {workflows_dir}"
            }

        logger.info(f"Found {len(workflow_files)} workflow files to process")

        for workflow_file in workflow_files:
            logger.info(f"Processing workflow: {workflow_file.name}")
            result = self.generate_collection_from_workflow(workflow_file)
            results.append({
                "file": workflow_file.name,
                "result": result
            })

            if result["success"]:
                logger.info(f"✅ {workflow_file.name} collection generated successfully")
            else:
                logger.warning(f"⚠️ {workflow_file.name} skipped: {result['message']}")

        successful = sum(1 for r in results if r["result"]["success"])

        return {
            "success": successful > 0,
            "total_workflows": len(workflow_files),
            "successful_generations": successful,
            "failed_generations": len(workflow_files) - successful,
            "results": results,
            "message": f"Generated {successful}/{len(workflow_files)} collections successfully"
        }
