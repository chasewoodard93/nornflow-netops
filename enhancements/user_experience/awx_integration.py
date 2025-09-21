"""
Ansible AWX Integration for NornFlow.

This module provides comprehensive integration with Ansible AWX/Tower:
- Convert NornFlow workflows to AWX job templates
- Generate surveys for workflow variables
- Manage credentials and secrets
- Sync inventory from NetBox to AWX
- Execute NornFlow workflows through AWX UI

AWX integration enables teams to run NornFlow workflows through the familiar
Ansible AWX interface with proper RBAC, scheduling, and audit capabilities.
"""

import json
import yaml
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import logging
import requests
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AWXCredential:
    """AWX credential configuration."""
    name: str
    credential_type: str
    inputs: Dict[str, Any]
    description: Optional[str] = None
    organization: Optional[str] = None


@dataclass
class AWXSurveyField:
    """AWX survey field configuration."""
    variable: str
    question_name: str
    question_description: str
    type: str = "text"
    required: bool = True
    default: Optional[str] = None
    choices: Optional[List[str]] = None
    min: Optional[int] = None
    max: Optional[int] = None


@dataclass
class AWXJobTemplate:
    """AWX job template configuration."""
    name: str
    description: str
    job_type: str = "run"
    inventory: str = "NornFlow Inventory"
    project: str = "NornFlow Project"
    playbook: str = "nornflow_runner.yml"
    credentials: List[str] = None
    survey_enabled: bool = True
    survey_spec: Dict[str, Any] = None
    extra_vars: Dict[str, Any] = None
    limit: Optional[str] = None
    verbosity: int = 0
    ask_variables_on_launch: bool = True
    ask_limit_on_launch: bool = True


class AWXIntegration:
    """
    Ansible AWX integration for NornFlow workflows.
    
    Provides methods to:
    - Create job templates from NornFlow workflows
    - Generate surveys for workflow variables
    - Manage credentials and secrets
    - Sync inventory from external sources
    """
    
    def __init__(self, awx_config: Dict[str, Any]):
        """
        Initialize AWX integration.
        
        Args:
            awx_config: AWX configuration including URL, username, password/token
        """
        self.base_url = awx_config["url"].rstrip("/")
        self.username = awx_config["username"]
        self.password = awx_config.get("password")
        self.token = awx_config.get("token")
        self.organization = awx_config.get("organization", "Default")
        self.verify_ssl = awx_config.get("verify_ssl", True)
        self.timeout = awx_config.get("timeout", 30)
        
        # Setup authentication
        if self.token:
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            self.auth = None
        else:
            self.headers = {"Content-Type": "application/json"}
            self.auth = (self.username, self.password)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to AWX."""
        try:
            response = requests.get(
                f"{self.base_url}/api/v2/ping/",
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Connected to AWX: {data.get('version', 'Unknown version')}",
                    "version": data.get("version"),
                    "instance_uuid": data.get("instance_uuid")
                }
            else:
                return {
                    "success": False,
                    "message": f"AWX connection failed: {response.status_code}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"AWX connection error: {str(e)}"
            }
    
    def create_nornflow_project(self, git_repo_url: str, git_branch: str = "main") -> Dict[str, Any]:
        """
        Create AWX project for NornFlow workflows.
        
        Args:
            git_repo_url: Git repository URL containing NornFlow workflows
            git_branch: Git branch to use
            
        Returns:
            Project creation result
        """
        project_data = {
            "name": "NornFlow Project",
            "description": "NornFlow network automation workflows",
            "organization": self.organization,
            "scm_type": "git",
            "scm_url": git_repo_url,
            "scm_branch": git_branch,
            "scm_clean": True,
            "scm_delete_on_update": True,
            "scm_update_on_launch": True,
            "scm_update_cache_timeout": 0
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/projects/",
                json=project_data,
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            if response.status_code == 201:
                project = response.json()
                return {
                    "success": True,
                    "project_id": project["id"],
                    "project_name": project["name"],
                    "message": "NornFlow project created successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to create project: {response.text}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Project creation error: {str(e)}"
            }
    
    def create_nornflow_inventory(self, netbox_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create AWX inventory for NornFlow with optional NetBox sync.
        
        Args:
            netbox_config: NetBox configuration for inventory sync
            
        Returns:
            Inventory creation result
        """
        inventory_data = {
            "name": "NornFlow Inventory",
            "description": "Network devices managed by NornFlow",
            "organization": self.organization,
            "kind": "",
            "host_filter": "",
            "variables": json.dumps({
                "nornflow_managed": True,
                "ansible_connection": "local",
                "ansible_python_interpreter": "{{ ansible_playbook_python }}"
            })
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/inventories/",
                json=inventory_data,
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            if response.status_code == 201:
                inventory = response.json()
                result = {
                    "success": True,
                    "inventory_id": inventory["id"],
                    "inventory_name": inventory["name"],
                    "message": "NornFlow inventory created successfully"
                }
                
                # Create NetBox inventory source if configured
                if netbox_config:
                    netbox_result = self._create_netbox_inventory_source(
                        inventory["id"], netbox_config
                    )
                    result["netbox_sync"] = netbox_result
                
                return result
            else:
                return {
                    "success": False,
                    "message": f"Failed to create inventory: {response.text}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Inventory creation error: {str(e)}"
            }
    
    def _create_netbox_inventory_source(self, inventory_id: int, netbox_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create NetBox inventory source for AWX inventory."""
        source_data = {
            "name": "NetBox Inventory Source",
            "description": "Sync network devices from NetBox",
            "source": "netbox",
            "source_vars": json.dumps({
                "url": netbox_config["url"],
                "token": netbox_config["token"],
                "validate_certs": netbox_config.get("ssl_verify", True),
                "config_context": True,
                "flatten_config_context": True,
                "device_query_filters": ["status=active"],
                "vm_query_filters": ["status=active"]
            }),
            "inventory": inventory_id,
            "update_on_launch": True,
            "update_cache_timeout": 0,
            "overwrite": True,
            "overwrite_vars": True
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/inventory_sources/",
                json=source_data,
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            if response.status_code == 201:
                return {"success": True, "message": "NetBox inventory source created"}
            else:
                return {"success": False, "message": f"NetBox source failed: {response.text}"}
        
        except Exception as e:
            return {"success": False, "message": f"NetBox source error: {str(e)}"}
    
    def create_credentials(self, credentials: List[AWXCredential]) -> Dict[str, Any]:
        """
        Create AWX credentials for NornFlow workflows.
        
        Args:
            credentials: List of credential configurations
            
        Returns:
            Credential creation results
        """
        results = []
        
        for cred in credentials:
            cred_data = {
                "name": cred.name,
                "description": cred.description or f"NornFlow credential: {cred.name}",
                "organization": self.organization,
                "credential_type": cred.credential_type,
                "inputs": cred.inputs
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/api/v2/credentials/",
                    json=cred_data,
                    headers=self.headers,
                    auth=self.auth,
                    verify=self.verify_ssl,
                    timeout=self.timeout
                )
                
                if response.status_code == 201:
                    credential = response.json()
                    results.append({
                        "name": cred.name,
                        "success": True,
                        "credential_id": credential["id"],
                        "message": f"Credential '{cred.name}' created successfully"
                    })
                else:
                    results.append({
                        "name": cred.name,
                        "success": False,
                        "message": f"Failed to create credential: {response.text}"
                    })
            
            except Exception as e:
                results.append({
                    "name": cred.name,
                    "success": False,
                    "message": f"Credential creation error: {str(e)}"
                })
        
        return {
            "success": all(r["success"] for r in results),
            "results": results,
            "message": f"Created {sum(1 for r in results if r['success'])}/{len(results)} credentials"
        }
    
    def generate_survey_from_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Generate AWX survey from NornFlow workflow variables.
        
        Args:
            workflow_file: Path to NornFlow workflow YAML file
            
        Returns:
            Survey specification
        """
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            workflow = workflow_data.get("workflow", {})
            variables = workflow.get("vars", {})
            
            survey_fields = []
            
            # Generate survey fields from workflow variables
            for var_name, var_value in variables.items():
                field = self._create_survey_field(var_name, var_value)
                if field:
                    survey_fields.append(field)
            
            # Add common NornFlow fields
            survey_fields.extend([
                AWXSurveyField(
                    variable="nornflow_dry_run",
                    question_name="Dry Run Mode",
                    question_description="Run in dry-run mode (no actual changes)",
                    type="multiplechoice",
                    choices=["true", "false"],
                    default="true",
                    required=True
                ),
                AWXSurveyField(
                    variable="nornflow_limit",
                    question_name="Device Limit",
                    question_description="Limit execution to specific devices (comma-separated)",
                    type="text",
                    required=False
                ),
                AWXSurveyField(
                    variable="nornflow_verbosity",
                    question_name="Verbosity Level",
                    question_description="Logging verbosity level",
                    type="multiplechoice",
                    choices=["0", "1", "2", "3"],
                    default="1",
                    required=True
                )
            ])
            
            survey_spec = {
                "name": f"Survey for {workflow.get('name', 'NornFlow Workflow')}",
                "description": f"Variables for {workflow.get('description', 'NornFlow workflow execution')}",
                "spec": [asdict(field) for field in survey_fields]
            }
            
            return {
                "success": True,
                "survey_spec": survey_spec,
                "field_count": len(survey_fields)
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Survey generation error: {str(e)}"
            }
    
    def _create_survey_field(self, var_name: str, var_value: Any) -> Optional[AWXSurveyField]:
        """Create survey field from workflow variable."""
        # Skip environment variables and complex objects
        if isinstance(var_value, str) and var_value.startswith("{{ env."):
            return None
        
        if isinstance(var_value, dict):
            return None
        
        # Determine field type based on value
        field_type = "text"
        default_value = None
        choices = None
        
        if isinstance(var_value, bool):
            field_type = "multiplechoice"
            choices = ["true", "false"]
            default_value = str(var_value).lower()
        elif isinstance(var_value, int):
            field_type = "integer"
            default_value = str(var_value)
        elif isinstance(var_value, list):
            if all(isinstance(item, str) for item in var_value):
                field_type = "multiplechoice"
                choices = var_value
                default_value = var_value[0] if var_value else None
            else:
                return None  # Skip complex lists
        elif isinstance(var_value, str):
            field_type = "text"
            default_value = var_value
        
        # Create human-readable question name
        question_name = var_name.replace("_", " ").title()
        
        return AWXSurveyField(
            variable=var_name,
            question_name=question_name,
            question_description=f"Value for {var_name}",
            type=field_type,
            default=default_value,
            choices=choices,
            required=False
        )

    def create_job_template(self, job_template: AWXJobTemplate) -> Dict[str, Any]:
        """
        Create AWX job template for NornFlow workflow.

        Args:
            job_template: Job template configuration

        Returns:
            Job template creation result
        """
        template_data = {
            "name": job_template.name,
            "description": job_template.description,
            "job_type": job_template.job_type,
            "inventory": job_template.inventory,
            "project": job_template.project,
            "playbook": job_template.playbook,
            "verbosity": job_template.verbosity,
            "ask_variables_on_launch": job_template.ask_variables_on_launch,
            "ask_limit_on_launch": job_template.ask_limit_on_launch,
            "survey_enabled": job_template.survey_enabled,
            "extra_vars": json.dumps(job_template.extra_vars or {})
        }

        if job_template.limit:
            template_data["limit"] = job_template.limit

        try:
            response = requests.post(
                f"{self.base_url}/api/v2/job_templates/",
                json=template_data,
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )

            if response.status_code == 201:
                template = response.json()
                result = {
                    "success": True,
                    "job_template_id": template["id"],
                    "job_template_name": template["name"],
                    "message": f"Job template '{job_template.name}' created successfully"
                }

                # Add survey if specified
                if job_template.survey_enabled and job_template.survey_spec:
                    survey_result = self._add_survey_to_template(
                        template["id"], job_template.survey_spec
                    )
                    result["survey"] = survey_result

                # Associate credentials if specified
                if job_template.credentials:
                    cred_result = self._associate_credentials(
                        template["id"], job_template.credentials
                    )
                    result["credentials"] = cred_result

                return result
            else:
                return {
                    "success": False,
                    "message": f"Failed to create job template: {response.text}"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Job template creation error: {str(e)}"
            }

    def _add_survey_to_template(self, template_id: int, survey_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Add survey to job template."""
        try:
            response = requests.post(
                f"{self.base_url}/api/v2/job_templates/{template_id}/survey_spec/",
                json=survey_spec,
                headers=self.headers,
                auth=self.auth,
                verify=self.verify_ssl,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return {"success": True, "message": "Survey added successfully"}
            else:
                return {"success": False, "message": f"Survey creation failed: {response.text}"}

        except Exception as e:
            return {"success": False, "message": f"Survey error: {str(e)}"}

    def _associate_credentials(self, template_id: int, credential_names: List[str]) -> Dict[str, Any]:
        """Associate credentials with job template."""
        results = []

        for cred_name in credential_names:
            try:
                # Find credential by name
                cred_response = requests.get(
                    f"{self.base_url}/api/v2/credentials/",
                    params={"name": cred_name},
                    headers=self.headers,
                    auth=self.auth,
                    verify=self.verify_ssl,
                    timeout=self.timeout
                )

                if cred_response.status_code == 200:
                    credentials = cred_response.json()["results"]
                    if credentials:
                        cred_id = credentials[0]["id"]

                        # Associate credential with template
                        assoc_response = requests.post(
                            f"{self.base_url}/api/v2/job_templates/{template_id}/credentials/",
                            json={"id": cred_id},
                            headers=self.headers,
                            auth=self.auth,
                            verify=self.verify_ssl,
                            timeout=self.timeout
                        )

                        if assoc_response.status_code == 204:
                            results.append({"name": cred_name, "success": True})
                        else:
                            results.append({"name": cred_name, "success": False,
                                          "message": f"Association failed: {assoc_response.text}"})
                    else:
                        results.append({"name": cred_name, "success": False,
                                      "message": "Credential not found"})
                else:
                    results.append({"name": cred_name, "success": False,
                                  "message": f"Credential lookup failed: {cred_response.text}"})

            except Exception as e:
                results.append({"name": cred_name, "success": False,
                              "message": f"Credential association error: {str(e)}"})

        return {
            "success": all(r["success"] for r in results),
            "results": results
        }

    def convert_workflow_to_awx(self, workflow_file: Path, git_repo_url: str) -> Dict[str, Any]:
        """
        Convert NornFlow workflow to complete AWX setup.

        Args:
            workflow_file: Path to NornFlow workflow YAML file
            git_repo_url: Git repository URL for AWX project

        Returns:
            Complete conversion result
        """
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)

            workflow = workflow_data.get("workflow", {})
            workflow_name = workflow.get("name", workflow_file.stem)

            # Generate survey from workflow
            survey_result = self.generate_survey_from_workflow(workflow_file)
            if not survey_result["success"]:
                return survey_result

            # Create job template
            job_template = AWXJobTemplate(
                name=f"NornFlow: {workflow_name}",
                description=workflow.get("description", f"NornFlow workflow: {workflow_name}"),
                extra_vars={
                    "nornflow_workflow": workflow_file.name,
                    "nornflow_workflow_path": str(workflow_file.parent),
                    "nornflow_git_repo": git_repo_url
                },
                survey_spec=survey_result["survey_spec"]
            )

            template_result = self.create_job_template(job_template)

            return {
                "success": template_result["success"],
                "workflow_name": workflow_name,
                "job_template": template_result,
                "survey": survey_result,
                "message": f"Workflow '{workflow_name}' converted to AWX successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Workflow conversion error: {str(e)}"
            }
