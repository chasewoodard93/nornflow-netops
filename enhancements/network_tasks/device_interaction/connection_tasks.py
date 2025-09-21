"""
Network device connection and basic interaction tasks for NornFlow.

These tasks provide the foundation for network device automation by handling
connections, command execution, and basic device interaction patterns.
"""

from typing import Any, Dict, List, Optional, Union
from nornir.core.task import Result, Task
from nornir.core.exceptions import NornirExecutionError


def test_connectivity(
    task: Task,
    timeout: int = 5,
    count: int = 3,
    method: str = "ping",
    api_endpoint: Optional[str] = None,
    api_method: str = "GET",
    api_headers: Optional[Dict[str, str]] = None,
    api_payload: Optional[Dict[str, Any]] = None,
    api_auth: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True
) -> Result:
    """
    Test network connectivity to a device using various methods including API testing.

    Args:
        task: Nornir task object
        timeout: Connection timeout in seconds
        count: Number of ping attempts (for ping method)
        method: Test method ('ping', 'tcp', 'ssh', 'api')
        api_endpoint: API endpoint to test (for api method)
        api_method: HTTP method for API test ('GET', 'POST', 'PUT', 'DELETE')
        api_headers: HTTP headers for API request
        api_payload: JSON payload for API request
        api_auth: Authentication dict with 'username' and 'password' or 'token'
        verify_ssl: Whether to verify SSL certificates for API calls

    Returns:
        Result object with connectivity test results
    """
    import subprocess
    import socket
    from time import time
    
    host_ip = task.host.hostname or task.host.name
    start_time = time()
    
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "method": method,
                "target": host_ip,
                "dry_run": True,
                "message": f"Would test connectivity to {host_ip} using {method}"
            },
            changed=False
        )
    
    try:
        if method == "ping":
            # Use ping command
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout * 1000), host_ip],
                capture_output=True,
                text=True,
                timeout=timeout * count + 5
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            
        elif method == "tcp":
            # Test TCP connection to SSH port (22) or specified port
            port = getattr(task.host, 'port', 22)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host_ip, port))
            sock.close()
            success = result == 0
            output = f"TCP connection to {host_ip}:{port} {'successful' if success else 'failed'}"
            
        elif method == "ssh":
            # Test SSH connection (requires paramiko or netmiko)
            try:
                from netmiko import ConnectHandler

                device = {
                    'device_type': task.host.platform,
                    'host': host_ip,
                    'username': task.host.username,
                    'password': task.host.password,
                    'timeout': timeout,
                }

                connection = ConnectHandler(**device)
                connection.disconnect()
                success = True
                output = f"SSH connection to {host_ip} successful"

            except ImportError:
                return Result(
                    host=task.host,
                    failed=True,
                    exception=ImportError("netmiko not available for SSH connectivity test")
                )
            except Exception as e:
                success = False
                output = f"SSH connection failed: {str(e)}"

        elif method == "api":
            # Test API connectivity
            try:
                import requests

                if not api_endpoint:
                    # Default API endpoint construction
                    protocol = "https" if verify_ssl else "http"
                    api_endpoint = f"{protocol}://{host_ip}/api/v1/status"

                # Prepare headers
                headers = api_headers or {}
                if 'Content-Type' not in headers and api_payload:
                    headers['Content-Type'] = 'application/json'

                # Prepare authentication
                auth = None
                if api_auth:
                    if 'token' in api_auth:
                        headers['Authorization'] = f"Bearer {api_auth['token']}"
                    elif 'username' in api_auth and 'password' in api_auth:
                        auth = (api_auth['username'], api_auth['password'])

                # Make API request
                response = requests.request(
                    method=api_method,
                    url=api_endpoint,
                    headers=headers,
                    json=api_payload,
                    auth=auth,
                    timeout=timeout,
                    verify=verify_ssl
                )

                success = response.status_code < 400
                output = f"API {api_method} to {api_endpoint} returned {response.status_code}"

                # Store additional API response info
                api_response_data = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "response_size": len(response.content),
                    "endpoint": api_endpoint,
                    "method": api_method
                }

            except ImportError:
                return Result(
                    host=task.host,
                    failed=True,
                    exception=ImportError("requests library not available for API connectivity test")
                )
            except Exception as e:
                success = False
                output = f"API connection failed: {str(e)}"
                api_response_data = {"error": str(e)}
        else:
            return Result(
                host=task.host,
                failed=True,
                exception=ValueError(f"Unknown connectivity test method: {method}")
            )
        
        end_time = time()
        response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds

        result_data = {
            "method": method,
            "target": host_ip,
            "success": success,
            "response_time_ms": response_time,
            "output": output,
            "timestamp": start_time
        }

        # Add API-specific data if this was an API test
        if method == "api" and 'api_response_data' in locals():
            result_data["api_response"] = api_response_data

        return Result(
            host=task.host,
            result=result_data,
            failed=not success
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def execute_command(
    task: Task,
    command: str,
    use_textfsm: bool = False,
    textfsm_template: Optional[str] = None,
    expect_string: Optional[str] = None,
    delay_factor: float = 1.0,
    max_loops: int = 500
) -> Result:
    """
    Execute a command on a network device.
    
    Args:
        task: Nornir task object
        command: Command to execute
        use_textfsm: Whether to use TextFSM parsing
        textfsm_template: Specific TextFSM template to use
        expect_string: String to expect in output
        delay_factor: Delay factor for command execution
        max_loops: Maximum loops for command completion
    
    Returns:
        Result object with command output
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "command": command,
                "dry_run": True,
                "message": f"Would execute command: {command}"
            },
            changed=False
        )
    
    try:
        # Try to use netmiko if available
        try:
            from nornir_netmiko.tasks import netmiko_send_command
            
            kwargs = {
                "command_string": command,
                "delay_factor": delay_factor,
                "max_loops": max_loops
            }
            
            if use_textfsm:
                kwargs["use_textfsm"] = True
                if textfsm_template:
                    kwargs["textfsm_template"] = textfsm_template
            
            if expect_string:
                kwargs["expect_string"] = expect_string
            
            result = task.run(netmiko_send_command, **kwargs)
            
            return Result(
                host=task.host,
                result={
                    "command": command,
                    "output": result.result,
                    "parsed": use_textfsm,
                    "success": True
                }
            )
            
        except ImportError:
            # Fallback to basic implementation if netmiko not available
            return Result(
                host=task.host,
                failed=True,
                exception=ImportError(
                    "netmiko not available. Install with: pip install nornir-netmiko"
                )
            )
            
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def test_api_payload(
    task: Task,
    endpoint: str,
    method: str = "POST",
    payload_template: Optional[str] = None,
    payload_file: Optional[str] = None,
    payload_data: Optional[Dict[str, Any]] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    auth: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True,
    timeout: int = 30,
    expected_status: Union[int, List[int]] = 200
) -> Result:
    """
    Test API payloads with Jinja2 template support for dynamic payload generation.

    Args:
        task: Nornir task object
        endpoint: API endpoint URL
        method: HTTP method ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        payload_template: Jinja2 template string for payload
        payload_file: Path to Jinja2 template file for payload
        payload_data: Direct payload data (dict)
        template_vars: Variables for Jinja2 template rendering
        headers: HTTP headers
        auth: Authentication dict with 'username'/'password' or 'token'
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        expected_status: Expected HTTP status code(s)

    Returns:
        Result object with API test results including payload validation
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "test_api_payload",
                "endpoint": endpoint,
                "method": method,
                "dry_run": True,
                "message": f"Would test API payload: {method} {endpoint}"
            },
            changed=False
        )

    try:
        import requests
        from jinja2 import Environment, Template, FileSystemLoader
        import json
        from pathlib import Path

        # Prepare payload
        if payload_template:
            # Use inline template
            template = Template(payload_template)
            render_vars = {
                'host': task.host,
                **(template_vars or {})
            }
            payload_json = template.render(**render_vars)
            payload = json.loads(payload_json)

        elif payload_file:
            # Use template file
            template_path = Path(payload_file)
            env = Environment(loader=FileSystemLoader(template_path.parent))
            template = env.get_template(template_path.name)

            render_vars = {
                'host': task.host,
                **(template_vars or {})
            }
            payload_json = template.render(**render_vars)
            payload = json.loads(payload_json)

        elif payload_data:
            # Use direct payload data
            payload = payload_data
        else:
            payload = {}

        # Prepare headers
        request_headers = headers or {}
        if 'Content-Type' not in request_headers and payload:
            request_headers['Content-Type'] = 'application/json'

        # Prepare authentication
        auth_obj = None
        if auth:
            if 'token' in auth:
                request_headers['Authorization'] = f"Bearer {auth['token']}"
            elif 'username' in auth and 'password' in auth:
                auth_obj = (auth['username'], auth['password'])

        # Make API request
        start_time = time()
        response = requests.request(
            method=method,
            url=endpoint,
            json=payload,
            headers=request_headers,
            auth=auth_obj,
            timeout=timeout,
            verify=verify_ssl
        )
        end_time = time()

        # Validate response
        expected_codes = expected_status if isinstance(expected_status, list) else [expected_status]
        status_valid = response.status_code in expected_codes

        # Parse response
        try:
            response_data = response.json()
        except:
            response_data = response.text

        result_data = {
            "action": "test_api_payload",
            "endpoint": endpoint,
            "method": method,
            "request": {
                "payload": payload,
                "headers": request_headers,
                "payload_size": len(json.dumps(payload)) if payload else 0
            },
            "response": {
                "status_code": response.status_code,
                "status_valid": status_valid,
                "headers": dict(response.headers),
                "data": response_data,
                "size": len(response.content),
                "response_time_ms": round((end_time - start_time) * 1000, 2)
            },
            "success": status_valid,
            "timestamp": start_time
        }

        return Result(
            host=task.host,
            result=result_data,
            failed=not status_valid
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
