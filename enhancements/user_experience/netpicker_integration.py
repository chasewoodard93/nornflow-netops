"""
NetPicker Integration for NornFlow.

NetPicker is a web-based tool for running Python scripts and workflows with a user-friendly interface.
This module provides integration to run NornFlow workflows through NetPicker:
- Register NornFlow workflows as NetPicker scripts
- Generate NetPicker variable forms
- Manage secrets and credentials
- Execute workflows through NetPicker UI

NetPicker integration enables network engineers to run NornFlow workflows through
a simple web interface without command-line knowledge.
"""

import json
import yaml
import os
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class NetPickerVariable:
    """NetPicker variable configuration."""
    name: str
    display_name: str
    description: str
    type: str = "text"
    required: bool = True
    default: Optional[str] = None
    options: Optional[List[str]] = None
    validation: Optional[str] = None
    group: Optional[str] = None
    order: int = 0


@dataclass
class NetPickerScript:
    """NetPicker script configuration."""
    name: str
    description: str
    category: str
    script_path: str
    variables: List[NetPickerVariable]
    tags: List[str] = None
    timeout: int = 3600
    requires_approval: bool = False
    dry_run_available: bool = True


class NetPickerIntegration:
    """
    NetPicker integration for NornFlow workflows.
    
    Provides methods to:
    - Register NornFlow workflows as NetPicker scripts
    - Generate variable forms for workflow parameters
    - Manage credentials and secrets
    - Execute workflows through NetPicker interface
    """
    
    def __init__(self, netpicker_config: Dict[str, Any]):
        """
        Initialize NetPicker integration.
        
        Args:
            netpicker_config: NetPicker configuration including paths and settings
        """
        self.scripts_dir = Path(netpicker_config.get("scripts_dir", "/opt/netpicker/scripts"))
        self.config_dir = Path(netpicker_config.get("config_dir", "/opt/netpicker/config"))
        self.secrets_dir = Path(netpicker_config.get("secrets_dir", "/opt/netpicker/secrets"))
        self.nornflow_path = netpicker_config.get("nornflow_path", "/opt/nornflow")
        self.workflows_path = Path(netpicker_config.get("workflows_path", "workflows"))
        self.category = netpicker_config.get("category", "Network Automation")
        
        # Ensure directories exist
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
    
    def register_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Register a NornFlow workflow as a NetPicker script.
        
        Args:
            workflow_file: Path to NornFlow workflow YAML file
            
        Returns:
            Registration result
        """
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            workflow = workflow_data.get("workflow", {})
            workflow_name = workflow.get("name", workflow_file.stem)
            
            # Generate NetPicker variables from workflow variables
            variables = self._generate_variables_from_workflow(workflow)
            
            # Create NetPicker script configuration
            script = NetPickerScript(
                name=f"nornflow_{workflow_file.stem}",
                description=workflow.get("description", f"NornFlow workflow: {workflow_name}"),
                category=self.category,
                script_path=f"nornflow_runner.py",
                variables=variables,
                tags=["nornflow", "network", "automation"],
                timeout=3600,
                requires_approval=self._requires_approval(workflow),
                dry_run_available=True
            )
            
            # Create the runner script
            runner_result = self._create_runner_script(workflow_file, script)
            if not runner_result["success"]:
                return runner_result
            
            # Create NetPicker configuration
            config_result = self._create_netpicker_config(script)
            if not config_result["success"]:
                return config_result
            
            # Create variable form
            form_result = self._create_variable_form(script)
            if not form_result["success"]:
                return form_result
            
            return {
                "success": True,
                "script_name": script.name,
                "workflow_name": workflow_name,
                "variables_count": len(variables),
                "message": f"Workflow '{workflow_name}' registered successfully in NetPicker"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Workflow registration failed: {str(e)}"
            }
    
    def _generate_variables_from_workflow(self, workflow: Dict[str, Any]) -> List[NetPickerVariable]:
        """Generate NetPicker variables from workflow variables."""
        variables = []
        workflow_vars = workflow.get("vars", {})
        
        # Add standard NornFlow variables
        variables.extend([
            NetPickerVariable(
                name="dry_run",
                display_name="Dry Run Mode",
                description="Run in dry-run mode (no actual changes)",
                type="boolean",
                default="true",
                required=True,
                group="Execution Options",
                order=1
            ),
            NetPickerVariable(
                name="verbosity",
                display_name="Verbosity Level",
                description="Logging verbosity level",
                type="select",
                options=["0", "1", "2", "3"],
                default="1",
                required=True,
                group="Execution Options",
                order=2
            ),
            NetPickerVariable(
                name="limit",
                display_name="Device Limit",
                description="Limit execution to specific devices (comma-separated)",
                type="text",
                required=False,
                group="Execution Options",
                order=3
            )
        ])
        
        # Generate variables from workflow vars
        order = 10
        for var_name, var_value in workflow_vars.items():
            # Skip environment variables and complex objects
            if isinstance(var_value, str) and var_value.startswith("{{ env."):
                continue
            if isinstance(var_value, dict):
                continue
            
            variable = self._create_netpicker_variable(var_name, var_value, order)
            if variable:
                variables.append(variable)
                order += 1
        
        return variables
    
    def _create_netpicker_variable(self, var_name: str, var_value: Any, order: int) -> Optional[NetPickerVariable]:
        """Create NetPicker variable from workflow variable."""
        # Determine variable type and options
        var_type = "text"
        default_value = None
        options = None
        validation = None
        
        if isinstance(var_value, bool):
            var_type = "boolean"
            default_value = str(var_value).lower()
        elif isinstance(var_value, int):
            var_type = "number"
            default_value = str(var_value)
            validation = "integer"
        elif isinstance(var_value, float):
            var_type = "number"
            default_value = str(var_value)
            validation = "float"
        elif isinstance(var_value, list):
            if all(isinstance(item, str) for item in var_value):
                var_type = "select"
                options = var_value
                default_value = var_value[0] if var_value else None
            else:
                return None  # Skip complex lists
        elif isinstance(var_value, str):
            var_type = "text"
            default_value = var_value
            
            # Check for password-like variables
            if any(keyword in var_name.lower() for keyword in ["password", "secret", "token", "key"]):
                var_type = "password"
        
        # Create human-readable display name
        display_name = var_name.replace("_", " ").title()
        
        return NetPickerVariable(
            name=var_name,
            display_name=display_name,
            description=f"Value for {display_name}",
            type=var_type,
            default=default_value,
            options=options,
            validation=validation,
            required=False,
            group="Workflow Variables",
            order=order
        )
    
    def _requires_approval(self, workflow: Dict[str, Any]) -> bool:
        """Determine if workflow requires approval based on content."""
        # Check for production indicators
        workflow_str = str(workflow).lower()
        production_indicators = [
            "production", "prod", "live", "critical",
            "delete", "remove", "shutdown", "reload"
        ]
        
        return any(indicator in workflow_str for indicator in production_indicators)
    
    def _create_runner_script(self, workflow_file: Path, script: NetPickerScript) -> Dict[str, Any]:
        """Create the Python runner script for NetPicker."""
        runner_script = f"""#!/usr/bin/env python3
\"\"\"
NetPicker runner script for NornFlow workflow: {workflow_file.name}
Generated automatically by NornFlow NetPicker integration.
\"\"\"

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# NetPicker integration
sys.path.insert(0, '{self.nornflow_path}')

def main():
    \"\"\"Main execution function for NetPicker.\"\"\"
    
    # Get variables from NetPicker environment
    variables = {{}}
    for var in {json.dumps([asdict(var) for var in script.variables])}:
        env_var = f"NP_{{var['name'].upper()}}"
        value = os.environ.get(env_var, var.get('default', ''))
        variables[var['name']] = value
    
    # Prepare NornFlow command
    cmd = [
        '{self.nornflow_path}/bin/nornflow',
        'run',
        '{workflow_file.stem}',
        '--config', '{self.nornflow_path}/config/nornflow.yaml'
    ]
    
    # Add execution options
    if variables.get('dry_run', 'false').lower() == 'true':
        cmd.append('--dry-run')
    
    if variables.get('verbosity'):
        cmd.extend(['--verbosity', variables['verbosity']])
    
    if variables.get('limit'):
        cmd.extend(['--limit', variables['limit']])
    
    # Set up environment
    env = os.environ.copy()
    
    # Pass workflow variables as environment variables
    for var_name, var_value in variables.items():
        if var_name not in ['dry_run', 'verbosity', 'limit']:
            env[f'NORNFLOW_{{var_name.upper()}}'] = str(var_value)
    
    # Execute NornFlow
    try:
        print(f"Executing NornFlow workflow: {workflow_file.name}")
        print(f"Command: {{' '.join(cmd)}}")
        print(f"Dry Run: {{variables.get('dry_run', 'false')}}")
        print("-" * 50)
        
        result = subprocess.run(
            cmd,
            cwd='{self.workflows_path.parent}',
            env=env,
            capture_output=False,
            text=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            print("-" * 50)
            print("✅ NornFlow workflow completed successfully!")
        else:
            print("-" * 50)
            print(f"❌ NornFlow workflow failed with return code: {{result.returncode}}")
            sys.exit(result.returncode)
    
    except subprocess.TimeoutExpired:
        print("❌ NornFlow workflow timed out after 1 hour")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error executing NornFlow workflow: {{str(e)}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
        
        try:
            script_file = self.scripts_dir / f"{script.name}.py"
            with open(script_file, 'w') as f:
                f.write(runner_script)
            
            # Make script executable
            script_file.chmod(0o755)
            
            return {
                "success": True,
                "script_file": str(script_file),
                "message": "Runner script created successfully"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create runner script: {str(e)}"
            }
    
    def _create_netpicker_config(self, script: NetPickerScript) -> Dict[str, Any]:
        """Create NetPicker configuration file."""
        config = {
            "name": script.name,
            "display_name": script.description,
            "description": script.description,
            "category": script.category,
            "script": f"{script.name}.py",
            "timeout": script.timeout,
            "requires_approval": script.requires_approval,
            "tags": script.tags or [],
            "variables": [asdict(var) for var in script.variables],
            "metadata": {
                "created_by": "nornflow_integration",
                "created_at": datetime.now().isoformat(),
                "nornflow_workflow": True,
                "dry_run_available": script.dry_run_available
            }
        }
        
        try:
            config_file = self.config_dir / f"{script.name}.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return {
                "success": True,
                "config_file": str(config_file),
                "message": "NetPicker configuration created successfully"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create NetPicker configuration: {str(e)}"
            }
    
    def _create_variable_form(self, script: NetPickerScript) -> Dict[str, Any]:
        """Create HTML form for NetPicker variables."""
        form_html = f\"\"\"
<!DOCTYPE html>
<html>
<head>
    <title>{script.description}</title>
    <style>
        .form-group {{ margin-bottom: 15px; }}
        .form-label {{ font-weight: bold; margin-bottom: 5px; display: block; }}
        .form-input {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
        .form-select {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
        .form-checkbox {{ margin-right: 8px; }}
        .form-description {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
        .form-section {{ border: 1px solid #eee; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
        .form-section h3 {{ margin-top: 0; color: #333; }}
        .required {{ color: red; }}
    </style>
</head>
<body>
    <h2>{script.description}</h2>
    <form id="nornflow-form">
\"\"\"
        
        # Group variables by group
        groups = {}
        for var in script.variables:
            group = var.group or "General"
            if group not in groups:
                groups[group] = []
            groups[group].append(var)
        
        # Generate form sections
        for group_name, group_vars in groups.items():
            form_html += f'        <div class="form-section">\\n'
            form_html += f'            <h3>{group_name}</h3>\\n'
            
            for var in sorted(group_vars, key=lambda x: x.order):
                form_html += self._generate_form_field(var)
            
            form_html += '        </div>\\n'
        
        form_html += \"\"\"
        <button type="submit" style="background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
            Execute Workflow
        </button>
    </form>
    
    <script>
        document.getElementById('nornflow-form').addEventListener('submit', function(e) {
            e.preventDefault();
            // NetPicker will handle form submission
            netpicker.submitForm(this);
        });
    </script>
</body>
</html>
\"\"\"
        
        try:
            form_file = self.config_dir / f"{script.name}_form.html"
            with open(form_file, 'w') as f:
                f.write(form_html)
            
            return {
                "success": True,
                "form_file": str(form_file),
                "message": "Variable form created successfully"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create variable form: {str(e)}"
            }
    
    def _generate_form_field(self, var: NetPickerVariable) -> str:
        """Generate HTML form field for a variable."""
        required_mark = '<span class="required">*</span>' if var.required else ''
        
        field_html = f'            <div class="form-group">\\n'
        field_html += f'                <label class="form-label" for="{var.name}">{var.display_name}{required_mark}</label>\\n'
        
        if var.type == "text":
            field_html += f'                <input type="text" id="{var.name}" name="{var.name}" class="form-input" value="{var.default or ""}" {"required" if var.required else ""}>\\n'
        elif var.type == "password":
            field_html += f'                <input type="password" id="{var.name}" name="{var.name}" class="form-input" {"required" if var.required else ""}>\\n'
        elif var.type == "number":
            field_html += f'                <input type="number" id="{var.name}" name="{var.name}" class="form-input" value="{var.default or ""}" {"required" if var.required else ""}>\\n'
        elif var.type == "boolean":
            checked = 'checked' if var.default == "true" else ''
            field_html += f'                <input type="checkbox" id="{var.name}" name="{var.name}" class="form-checkbox" {checked}>\\n'
        elif var.type == "select" and var.options:
            field_html += f'                <select id="{var.name}" name="{var.name}" class="form-select" {"required" if var.required else ""}>\\n'
            for option in var.options:
                selected = 'selected' if option == var.default else ''
                field_html += f'                    <option value="{option}" {selected}>{option}</option>\\n'
            field_html += '                </select>\\n'
        
        if var.description:
            field_html += f'                <div class="form-description">{var.description}</div>\\n'
        
        field_html += '            </div>\\n'
        
        return field_html

    def register_all_workflows(self, workflows_dir: Path) -> Dict[str, Any]:
        """
        Register all NornFlow workflows in a directory as NetPicker scripts.

        Args:
            workflows_dir: Directory containing NornFlow workflow YAML files

        Returns:
            Batch registration results
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

        logger.info(f"Found {len(workflow_files)} workflow files to register")

        for workflow_file in workflow_files:
            logger.info(f"Registering workflow: {workflow_file.name}")
            result = self.register_workflow(workflow_file)
            results.append({
                "file": workflow_file.name,
                "result": result
            })

            if result["success"]:
                logger.info(f"✅ {workflow_file.name} registered successfully")
            else:
                logger.error(f"❌ {workflow_file.name} registration failed: {result['message']}")

        successful = sum(1 for r in results if r["result"]["success"])

        return {
            "success": successful > 0,
            "total_workflows": len(workflow_files),
            "successful_registrations": successful,
            "failed_registrations": len(workflow_files) - successful,
            "results": results,
            "message": f"Registered {successful}/{len(workflow_files)} workflows successfully"
        }

    def create_secrets_config(self, secrets: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create NetPicker secrets configuration for NornFlow integrations.

        Args:
            secrets: Dictionary of secret configurations

        Returns:
            Secrets creation result
        """
        secrets_config = {
            "nornflow_secrets": {
                "description": "Secrets for NornFlow network automation workflows",
                "secrets": {}
            }
        }

        # Process different types of secrets
        for secret_name, secret_config in secrets.items():
            if secret_name == "network_devices":
                secrets_config["nornflow_secrets"]["secrets"]["device_username"] = {
                    "type": "string",
                    "description": "Network device SSH username",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["device_password"] = {
                    "type": "password",
                    "description": "Network device SSH password",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["enable_password"] = {
                    "type": "password",
                    "description": "Network device enable password",
                    "required": False
                }

            elif secret_name == "netbox":
                secrets_config["nornflow_secrets"]["secrets"]["netbox_url"] = {
                    "type": "string",
                    "description": "NetBox instance URL",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["netbox_token"] = {
                    "type": "password",
                    "description": "NetBox API token",
                    "required": True
                }

            elif secret_name == "grafana":
                secrets_config["nornflow_secrets"]["secrets"]["grafana_url"] = {
                    "type": "string",
                    "description": "Grafana instance URL",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["grafana_api_key"] = {
                    "type": "password",
                    "description": "Grafana API key",
                    "required": True
                }

            elif secret_name == "servicenow":
                secrets_config["nornflow_secrets"]["secrets"]["servicenow_url"] = {
                    "type": "string",
                    "description": "ServiceNow instance URL",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["servicenow_user"] = {
                    "type": "string",
                    "description": "ServiceNow username",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["servicenow_pass"] = {
                    "type": "password",
                    "description": "ServiceNow password",
                    "required": True
                }

            elif secret_name == "jira":
                secrets_config["nornflow_secrets"]["secrets"]["jira_url"] = {
                    "type": "string",
                    "description": "Jira instance URL",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["jira_user"] = {
                    "type": "string",
                    "description": "Jira username",
                    "required": True
                }
                secrets_config["nornflow_secrets"]["secrets"]["jira_token"] = {
                    "type": "password",
                    "description": "Jira API token",
                    "required": True
                }

        try:
            secrets_file = self.secrets_dir / "nornflow_secrets.json"
            with open(secrets_file, 'w') as f:
                json.dump(secrets_config, f, indent=2)

            return {
                "success": True,
                "secrets_file": str(secrets_file),
                "secrets_count": len(secrets_config["nornflow_secrets"]["secrets"]),
                "message": "NetPicker secrets configuration created successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create secrets configuration: {str(e)}"
            }

    def generate_setup_documentation(self) -> str:
        """Generate documentation for NetPicker setup."""
        doc = f"""
# NetPicker Setup for NornFlow

## Directory Structure
- Scripts Directory: {self.scripts_dir}
- Config Directory: {self.config_dir}
- Secrets Directory: {self.secrets_dir}
- NornFlow Path: {self.nornflow_path}
- Workflows Path: {self.workflows_path}

## Setup Steps

### 1. Install NetPicker
Follow NetPicker installation instructions for your platform.

### 2. Configure NornFlow Integration
1. Copy NornFlow workflows to: {self.workflows_path}
2. Run the NetPicker setup utility:
   ```bash
   python netpicker_setup.py --workflows-dir {self.workflows_path}
   ```

### 3. Configure Secrets
Create secrets in NetPicker for:
- Network device credentials (SSH username/password)
- NetBox API token
- Grafana API key
- ServiceNow credentials
- Jira API token

### 4. Access NetPicker Web Interface
1. Open NetPicker web interface
2. Navigate to "Scripts" section
3. Find NornFlow workflows in "{self.category}" category
4. Click on a workflow to see the variable form
5. Fill in required variables and execute

## Script Categories
All NornFlow workflows will be registered under the "{self.category}" category.

## Variable Types
- Text: String inputs
- Password: Secure password inputs
- Boolean: Checkbox inputs
- Select: Dropdown selections
- Number: Numeric inputs

## Execution Features
- Dry-run mode available for all workflows
- Variable validation before execution
- Real-time execution output
- Execution history and logging
- Approval workflows for production changes

## Security
- All sensitive variables are marked as password type
- Secrets are managed through NetPicker's secure storage
- Execution logs exclude sensitive information
- RBAC through NetPicker's user management
"""

        return doc
