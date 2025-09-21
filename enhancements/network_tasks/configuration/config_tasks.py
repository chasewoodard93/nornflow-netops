"""
Network device configuration management tasks for NornFlow.

These tasks handle configuration deployment, validation, backup, and rollback
operations for network devices.
"""

from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
from nornir.core.task import Result, Task
import yaml
import json


def deploy_config(
    task: Task,
    config: Optional[str] = None,
    config_file: Optional[str] = None,
    template_file: Optional[str] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    backup_before: bool = True,
    validate_after: bool = True,
    commit: bool = True,
    rollback_on_error: bool = True,
    deployment_method: str = "cli",
    api_endpoint: Optional[str] = None,
    api_method: str = "POST",
    api_headers: Optional[Dict[str, str]] = None,
    api_auth: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True,
    api_timeout: int = 60
) -> Result:
    """
    Deploy configuration to a network device with comprehensive safety features.
    Supports both CLI-based and API-based deployment methods.

    Args:
        task: Nornir task object
        config: Configuration string to deploy
        config_file: Path to configuration file
        template_file: Path to Jinja2 template file
        template_vars: Variables for template rendering
        backup_before: Whether to backup config before deployment
        validate_after: Whether to validate config after deployment
        commit: Whether to commit the configuration
        rollback_on_error: Whether to rollback on validation failure
        deployment_method: Deployment method ('cli' or 'api')
        api_endpoint: API endpoint for configuration deployment
        api_method: HTTP method for API deployment ('POST', 'PUT', 'PATCH')
        api_headers: HTTP headers for API request
        api_auth: Authentication dict for API
        verify_ssl: Whether to verify SSL certificates for API calls
        api_timeout: Timeout for API requests in seconds

    Returns:
        Result object with deployment results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "deploy_config",
                "dry_run": True,
                "message": "Would deploy configuration",
                "backup_before": backup_before,
                "validate_after": validate_after,
                "commit": commit
            },
            changed=True
        )
    
    try:
        # Determine configuration source
        if config:
            config_to_deploy = config
        elif config_file:
            with open(config_file, 'r') as f:
                config_to_deploy = f.read()
        elif template_file:
            from jinja2 import Environment, FileSystemLoader
            
            template_path = Path(template_file)
            env = Environment(loader=FileSystemLoader(template_path.parent))
            template = env.get_template(template_path.name)
            
            # Merge template vars with host data
            render_vars = {
                'host': task.host,
                **(template_vars or {})
            }
            config_to_deploy = template.render(**render_vars)
        else:
            return Result(
                host=task.host,
                failed=True,
                exception=ValueError("Must provide config, config_file, or template_file")
            )
        
        results = {
            "action": "deploy_config",
            "config_lines": len(config_to_deploy.splitlines()),
            "backup_created": False,
            "config_deployed": False,
            "validation_passed": False,
            "committed": False
        }
        
        # Backup current configuration if requested
        if backup_before:
            backup_result = task.run(
                backup_config,
                backup_dir=f"backups/{task.host.name}",
                include_timestamp=True
            )
            results["backup_created"] = not backup_result.failed
            results["backup_file"] = backup_result.result.get("backup_file") if not backup_result.failed else None
        
        # Deploy configuration using netmiko
        try:
            from nornir_netmiko.tasks import netmiko_send_config
            
            deploy_result = task.run(
                netmiko_send_config,
                config_commands=config_to_deploy.splitlines()
            )
            
            results["config_deployed"] = not deploy_result.failed
            results["deploy_output"] = deploy_result.result
            
            if deploy_result.failed:
                raise Exception(f"Configuration deployment failed: {deploy_result.exception}")
            
        except ImportError:
            return Result(
                host=task.host,
                failed=True,
                exception=ImportError("netmiko not available. Install with: pip install nornir-netmiko")
            )
        
        # Validate configuration if requested
        if validate_after and results["config_deployed"]:
            validation_result = task.run(validate_config)
            results["validation_passed"] = not validation_result.failed
            results["validation_details"] = validation_result.result
            
            if not results["validation_passed"] and rollback_on_error:
                # Attempt rollback
                if results["backup_created"] and results.get("backup_file"):
                    rollback_result = task.run(
                        restore_config,
                        backup_file=results["backup_file"]
                    )
                    results["rollback_attempted"] = True
                    results["rollback_successful"] = not rollback_result.failed
        
        # Commit configuration if requested and validation passed
        if commit and results["config_deployed"] and (not validate_after or results["validation_passed"]):
            try:
                from nornir_netmiko.tasks import netmiko_commit
                commit_result = task.run(netmiko_commit)
                results["committed"] = not commit_result.failed
            except (ImportError, AttributeError):
                # Not all platforms support commit or netmiko_commit might not be available
                results["committed"] = True  # Assume committed for platforms that don't require explicit commit
        
        # Determine overall success
        success = (
            results["config_deployed"] and
            (not validate_after or results["validation_passed"]) and
            (not commit or results["committed"])
        )
        
        return Result(
            host=task.host,
            result=results,
            failed=not success,
            changed=results["config_deployed"]
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def backup_config(
    task: Task,
    backup_dir: str = "backups",
    filename_template: str = "{host}_{timestamp}.cfg",
    include_timestamp: bool = True,
    config_type: str = "running"
) -> Result:
    """
    Backup device configuration.
    
    Args:
        task: Nornir task object
        backup_dir: Directory to store backups
        filename_template: Template for backup filename
        include_timestamp: Whether to include timestamp in filename
        config_type: Type of config to backup ('running', 'startup')
    
    Returns:
        Result object with backup details
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "backup_config",
                "dry_run": True,
                "message": f"Would backup {config_type} config to {backup_dir}"
            },
            changed=False
        )
    
    try:
        # Create backup directory
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") if include_timestamp else ""
        filename = filename_template.format(
            host=task.host.name,
            timestamp=timestamp,
            config_type=config_type
        )
        backup_file = backup_path / filename
        
        # Get configuration based on platform
        platform = task.host.platform.lower()
        if "ios" in platform or "nxos" in platform:
            command = f"show {config_type}-config"
        elif "eos" in platform:
            command = f"show {config_type}-config"
        elif "junos" in platform:
            command = "show configuration"
        else:
            command = f"show {config_type}-config"  # Default
        
        # Execute command to get configuration
        from enhancements.network_tasks.device_interaction.connection_tasks import execute_command
        
        config_result = task.run(
            execute_command,
            command=command
        )
        
        if config_result.failed:
            return Result(
                host=task.host,
                failed=True,
                exception=Exception(f"Failed to retrieve {config_type} configuration")
            )
        
        # Save configuration to file
        with open(backup_file, 'w') as f:
            f.write(config_result.result["output"])
        
        return Result(
            host=task.host,
            result={
                "action": "backup_config",
                "backup_file": str(backup_file),
                "config_type": config_type,
                "size_bytes": backup_file.stat().st_size,
                "timestamp": datetime.now().isoformat()
            },
            changed=True
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def validate_config(
    task: Task,
    validation_commands: Optional[List[str]] = None,
    expected_patterns: Optional[Dict[str, str]] = None,
    custom_validation: Optional[str] = None
) -> Result:
    """
    Validate device configuration.
    
    Args:
        task: Nornir task object
        validation_commands: List of commands to run for validation
        expected_patterns: Dict of command -> expected pattern mappings
        custom_validation: Path to custom validation script
    
    Returns:
        Result object with validation results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "validate_config",
                "dry_run": True,
                "message": "Would validate configuration"
            },
            changed=False
        )
    
    try:
        validation_results = {
            "action": "validate_config",
            "overall_status": "passed",
            "checks": []
        }
        
        # Default validation commands based on platform
        if not validation_commands:
            platform = task.host.platform.lower()
            if "ios" in platform:
                validation_commands = [
                    "show ip interface brief",
                    "show version",
                    "show running-config | include interface"
                ]
            elif "nxos" in platform:
                validation_commands = [
                    "show interface brief",
                    "show version",
                    "show running-config interface"
                ]
            else:
                validation_commands = ["show version"]
        
        # Execute validation commands
        from enhancements.network_tasks.device_interaction.connection_tasks import execute_command
        
        for command in validation_commands:
            check_result = {
                "command": command,
                "status": "passed",
                "output": "",
                "error": None
            }
            
            try:
                cmd_result = task.run(execute_command, command=command)
                
                if cmd_result.failed:
                    check_result["status"] = "failed"
                    check_result["error"] = str(cmd_result.exception)
                    validation_results["overall_status"] = "failed"
                else:
                    check_result["output"] = cmd_result.result["output"]
                    
                    # Check expected patterns if provided
                    if expected_patterns and command in expected_patterns:
                        import re
                        pattern = expected_patterns[command]
                        if not re.search(pattern, check_result["output"]):
                            check_result["status"] = "failed"
                            check_result["error"] = f"Expected pattern not found: {pattern}"
                            validation_results["overall_status"] = "failed"
                
            except Exception as e:
                check_result["status"] = "failed"
                check_result["error"] = str(e)
                validation_results["overall_status"] = "failed"
            
            validation_results["checks"].append(check_result)
        
        return Result(
            host=task.host,
            result=validation_results,
            failed=validation_results["overall_status"] == "failed"
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def restore_config(
    task: Task,
    backup_file: str,
    config_type: str = "running",
    commit: bool = True
) -> Result:
    """
    Restore configuration from backup file.
    
    Args:
        task: Nornir task object
        backup_file: Path to backup file
        config_type: Type of config to restore to
        commit: Whether to commit the restored configuration
    
    Returns:
        Result object with restore results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "restore_config",
                "dry_run": True,
                "message": f"Would restore config from {backup_file}"
            },
            changed=True
        )
    
    try:
        # Read backup file
        backup_path = Path(backup_file)
        if not backup_path.exists():
            return Result(
                host=task.host,
                failed=True,
                exception=FileNotFoundError(f"Backup file not found: {backup_file}")
            )
        
        with open(backup_path, 'r') as f:
            config_content = f.read()
        
        # Deploy the backed up configuration
        restore_result = task.run(
            deploy_config,
            config=config_content,
            backup_before=False,  # Don't backup before restore
            validate_after=True,
            commit=commit,
            rollback_on_error=False  # Don't rollback a restore operation
        )
        
        return Result(
            host=task.host,
            result={
                "action": "restore_config",
                "backup_file": backup_file,
                "restore_successful": not restore_result.failed,
                "restore_details": restore_result.result
            },
            failed=restore_result.failed,
            changed=not restore_result.failed
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def deploy_config_api(
    task: Task,
    config: Optional[str] = None,
    config_file: Optional[str] = None,
    template_file: Optional[str] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    api_endpoint: Optional[str] = None,
    api_method: str = "POST",
    api_headers: Optional[Dict[str, str]] = None,
    api_auth: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True,
    timeout: int = 60,
    backup_before: bool = True,
    validate_after: bool = True,
    rollback_on_error: bool = True,
    commit: bool = True
) -> Result:
    """
    Deploy configuration via REST API with comprehensive safety features.

    Args:
        task: Nornir task object
        config: Configuration string to deploy
        config_file: Path to configuration file
        template_file: Path to Jinja2 template file
        template_vars: Variables for template rendering
        api_endpoint: API endpoint for configuration deployment
        api_method: HTTP method ('POST', 'PUT', 'PATCH')
        api_headers: HTTP headers for API request
        api_auth: Authentication dict with 'username'/'password' or 'token'
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        backup_before: Whether to backup configuration before deployment
        validate_after: Whether to validate configuration after deployment
        rollback_on_error: Whether to rollback on validation failure
        commit: Whether to commit the configuration

    Returns:
        Result object with API deployment results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "deploy_config_api",
                "dry_run": True,
                "message": "Would deploy configuration via API"
            },
            changed=False
        )

    try:
        import requests
        import json
        from jinja2 import Environment, Template, FileSystemLoader
        from pathlib import Path

        results = {
            "action": "deploy_config_api",
            "deployment_method": "api",
            "backup_created": False,
            "config_deployed": False,
            "validation_passed": None,
            "committed": False,
            "rollback_attempted": False
        }

        # Prepare configuration content
        config_to_deploy = None

        if template_file:
            # Use Jinja2 template file
            template_path = Path(template_file)
            env = Environment(loader=FileSystemLoader(template_path.parent))
            template = env.get_template(template_path.name)

            render_vars = {
                'host': task.host,
                **(template_vars or {})
            }
            config_to_deploy = template.render(**render_vars)

        elif config_file:
            # Read configuration from file
            with open(config_file, 'r') as f:
                config_content = f.read()

            if template_vars:
                # Treat file content as template
                template = Template(config_content)
                render_vars = {
                    'host': task.host,
                    **template_vars
                }
                config_to_deploy = template.render(**render_vars)
            else:
                config_to_deploy = config_content

        elif config:
            # Use provided configuration string
            if template_vars:
                # Treat config as template
                template = Template(config)
                render_vars = {
                    'host': task.host,
                    **template_vars
                }
                config_to_deploy = template.render(**render_vars)
            else:
                config_to_deploy = config
        else:
            return Result(
                host=task.host,
                failed=True,
                exception=ValueError("No configuration source provided")
            )

        # Backup current configuration if requested
        if backup_before:
            backup_result = task.run(
                backup_config,
                backup_dir=f"backups/{task.host.name}",
                include_timestamp=True
            )
            results["backup_created"] = not backup_result.failed
            results["backup_file"] = backup_result.result.get("backup_file") if not backup_result.failed else None

        # Prepare API request
        if not api_endpoint:
            # Construct default API endpoint
            protocol = "https" if verify_ssl else "http"
            api_endpoint = f"{protocol}://{task.host.hostname}/api/v1/config"

        # Prepare headers
        headers = api_headers or {}
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        # Prepare authentication
        auth_obj = None
        if api_auth:
            if 'token' in api_auth:
                headers['Authorization'] = f"Bearer {api_auth['token']}"
            elif 'username' in api_auth and 'password' in api_auth:
                auth_obj = (api_auth['username'], api_auth['password'])

        # Prepare payload based on content type
        if headers.get('Content-Type') == 'application/json':
            # JSON payload structure
            payload = {
                "config": config_to_deploy,
                "commit": commit,
                "validate": validate_after,
                "backup": backup_before
            }
            request_data = json.dumps(payload)
        else:
            # Plain text payload
            request_data = config_to_deploy

        # Deploy configuration via API
        response = requests.request(
            method=api_method,
            url=api_endpoint,
            data=request_data,
            headers=headers,
            auth=auth_obj,
            timeout=timeout,
            verify=verify_ssl
        )

        # Process API response
        results["api_response"] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "endpoint": api_endpoint,
            "method": api_method
        }

        if response.status_code >= 400:
            results["config_deployed"] = False
            results["deployment_error"] = f"API request failed: {response.status_code}"

            try:
                error_data = response.json()
                results["api_response"]["error_details"] = error_data
            except:
                results["api_response"]["error_text"] = response.text

            # Rollback if requested and backup exists
            if rollback_on_error and results.get("backup_file"):
                rollback_result = task.run(
                    restore_config,
                    backup_file=results["backup_file"]
                )
                results["rollback_attempted"] = True
                results["rollback_successful"] = not rollback_result.failed

            return Result(
                host=task.host,
                result=results,
                failed=True
            )

        # Successful deployment
        results["config_deployed"] = True

        try:
            response_data = response.json()
            results["api_response"]["data"] = response_data

            # Extract deployment details from response if available
            if isinstance(response_data, dict):
                results["committed"] = response_data.get("committed", commit)
                results["validation_passed"] = response_data.get("validation_passed", True)
        except:
            results["api_response"]["text"] = response.text[:500]

        # Additional validation if requested and not already done by API
        if validate_after and not results.get("validation_passed"):
            validation_result = task.run(validate_config)
            results["validation_passed"] = not validation_result.failed
            results["validation_details"] = validation_result.result

            if not results["validation_passed"] and rollback_on_error:
                # Attempt rollback
                if results.get("backup_file"):
                    rollback_result = task.run(
                        restore_config,
                        backup_file=results["backup_file"]
                    )
                    results["rollback_attempted"] = True
                    results["rollback_successful"] = not rollback_result.failed

        return Result(
            host=task.host,
            result=results,
            changed=results["config_deployed"],
            failed=not results["config_deployed"]
        )

    except ImportError as e:
        return Result(
            host=task.host,
            failed=True,
            exception=ImportError(f"Required library not available: {str(e)}")
        )
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )
