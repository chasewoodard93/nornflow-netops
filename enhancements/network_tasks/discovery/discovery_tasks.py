"""
Network discovery tasks for NornFlow.

These tasks handle network topology discovery, device capability detection,
and neighbor discovery using various protocols like LLDP, CDP, and SNMP.
"""

from typing import Any, Dict, List, Optional, Union
from nornir.core.task import Result, Task
import re
import json


def discover_neighbors(
    task: Task,
    protocol: str = "lldp",
    parse_output: bool = True,
    include_details: bool = True
) -> Result:
    """
    Discover network neighbors using LLDP, CDP, or other protocols.
    
    Args:
        task: Nornir task object
        protocol: Discovery protocol ('lldp', 'cdp', 'both')
        parse_output: Whether to parse the output into structured data
        include_details: Whether to include detailed neighbor information
    
    Returns:
        Result object with neighbor discovery results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "discover_neighbors",
                "protocol": protocol,
                "dry_run": True,
                "message": f"Would discover neighbors using {protocol}"
            },
            changed=False
        )
    
    try:
        from enhancements.network_tasks.device_interaction.connection_tasks import execute_command
        
        neighbors = {
            "protocol": protocol,
            "neighbors": [],
            "raw_output": {},
            "summary": {
                "total_neighbors": 0,
                "protocols_used": []
            }
        }
        
        protocols_to_check = []
        if protocol.lower() == "both":
            protocols_to_check = ["lldp", "cdp"]
        else:
            protocols_to_check = [protocol.lower()]
        
        for proto in protocols_to_check:
            try:
                # Determine command based on protocol and platform
                platform = task.host.platform.lower()
                
                if proto == "lldp":
                    if "ios" in platform or "nxos" in platform:
                        command = "show lldp neighbors detail" if include_details else "show lldp neighbors"
                    elif "eos" in platform:
                        command = "show lldp neighbors detail" if include_details else "show lldp neighbors"
                    elif "junos" in platform:
                        command = "show lldp neighbors detail" if include_details else "show lldp neighbors"
                    else:
                        command = "show lldp neighbors"
                        
                elif proto == "cdp":
                    if "ios" in platform or "nxos" in platform:
                        command = "show cdp neighbors detail" if include_details else "show cdp neighbors"
                    else:
                        continue  # CDP not supported on this platform
                
                # Execute discovery command
                cmd_result = task.run(
                    execute_command,
                    command=command,
                    use_textfsm=parse_output
                )
                
                if not cmd_result.failed:
                    neighbors["raw_output"][proto] = cmd_result.result["output"]
                    neighbors["summary"]["protocols_used"].append(proto)
                    
                    if parse_output and isinstance(cmd_result.result["output"], list):
                        # TextFSM parsed output
                        parsed_neighbors = cmd_result.result["output"]
                    else:
                        # Parse manually if TextFSM not available or failed
                        parsed_neighbors = _parse_neighbor_output(
                            cmd_result.result["output"], 
                            proto, 
                            platform
                        )
                    
                    # Add protocol info to each neighbor
                    for neighbor in parsed_neighbors:
                        if isinstance(neighbor, dict):
                            neighbor["discovery_protocol"] = proto
                            neighbors["neighbors"].append(neighbor)
                
            except Exception as e:
                # Continue with other protocols if one fails
                neighbors["raw_output"][f"{proto}_error"] = str(e)
                continue
        
        neighbors["summary"]["total_neighbors"] = len(neighbors["neighbors"])
        
        return Result(
            host=task.host,
            result=neighbors,
            changed=False
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def discover_interfaces(
    task: Task,
    interface_type: str = "all",
    include_status: bool = True,
    include_config: bool = False
) -> Result:
    """
    Discover device interfaces and their properties.
    
    Args:
        task: Nornir task object
        interface_type: Type of interfaces to discover ('all', 'physical', 'logical')
        include_status: Whether to include interface status information
        include_config: Whether to include interface configuration
    
    Returns:
        Result object with interface discovery results
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "discover_interfaces",
                "interface_type": interface_type,
                "dry_run": True,
                "message": f"Would discover {interface_type} interfaces"
            },
            changed=False
        )
    
    try:
        from enhancements.network_tasks.device_interaction.connection_tasks import execute_command
        
        interfaces = {
            "interface_type": interface_type,
            "interfaces": [],
            "summary": {
                "total_interfaces": 0,
                "up_interfaces": 0,
                "down_interfaces": 0,
                "admin_down_interfaces": 0
            }
        }
        
        # Determine commands based on platform
        platform = task.host.platform.lower()
        
        if "ios" in platform:
            status_command = "show ip interface brief"
            config_command = "show running-config | section interface"
        elif "nxos" in platform:
            status_command = "show interface brief"
            config_command = "show running-config interface"
        elif "eos" in platform:
            status_command = "show interfaces status"
            config_command = "show running-config | section interface"
        elif "junos" in platform:
            status_command = "show interfaces terse"
            config_command = "show configuration interfaces"
        else:
            status_command = "show interfaces"
            config_command = "show running-config"
        
        # Get interface status
        if include_status:
            status_result = task.run(
                execute_command,
                command=status_command,
                use_textfsm=True
            )
            
            if not status_result.failed:
                if isinstance(status_result.result["output"], list):
                    interfaces["interfaces"] = status_result.result["output"]
                else:
                    # Parse manually if TextFSM failed
                    interfaces["interfaces"] = _parse_interface_output(
                        status_result.result["output"], 
                        platform
                    )
        
        # Get interface configuration if requested
        if include_config:
            config_result = task.run(
                execute_command,
                command=config_command
            )
            
            if not config_result.failed:
                # Parse and merge configuration data
                config_data = _parse_interface_config(
                    config_result.result["output"], 
                    platform
                )
                
                # Merge config data with interface data
                for interface in interfaces["interfaces"]:
                    if isinstance(interface, dict) and "interface" in interface:
                        int_name = interface["interface"]
                        if int_name in config_data:
                            interface["configuration"] = config_data[int_name]
        
        # Calculate summary statistics
        for interface in interfaces["interfaces"]:
            if isinstance(interface, dict):
                interfaces["summary"]["total_interfaces"] += 1
                
                status = interface.get("status", "").lower()
                protocol = interface.get("protocol", "").lower()
                
                if "up" in status and "up" in protocol:
                    interfaces["summary"]["up_interfaces"] += 1
                elif "administratively down" in status or "admin down" in status:
                    interfaces["summary"]["admin_down_interfaces"] += 1
                else:
                    interfaces["summary"]["down_interfaces"] += 1
        
        return Result(
            host=task.host,
            result=interfaces,
            changed=False
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def discover_device_info(
    task: Task,
    include_hardware: bool = True,
    include_software: bool = True,
    include_inventory: bool = False
) -> Result:
    """
    Discover comprehensive device information.
    
    Args:
        task: Nornir task object
        include_hardware: Whether to include hardware information
        include_software: Whether to include software information
        include_inventory: Whether to include detailed inventory
    
    Returns:
        Result object with device information
    """
    if task.is_dry_run():
        return Result(
            host=task.host,
            result={
                "action": "discover_device_info",
                "dry_run": True,
                "message": "Would discover device information"
            },
            changed=False
        )
    
    try:
        from enhancements.network_tasks.device_interaction.connection_tasks import execute_command
        
        device_info = {
            "hostname": task.host.name,
            "platform": task.host.platform,
            "management_ip": task.host.hostname,
            "discovery_timestamp": task.host.defaults.get("timestamp"),
            "hardware": {},
            "software": {},
            "inventory": []
        }
        
        platform = task.host.platform.lower()
        
        # Get basic version information
        if "ios" in platform or "nxos" in platform:
            version_command = "show version"
        elif "eos" in platform:
            version_command = "show version"
        elif "junos" in platform:
            version_command = "show version"
        else:
            version_command = "show version"
        
        version_result = task.run(
            execute_command,
            command=version_command,
            use_textfsm=True
        )
        
        if not version_result.failed:
            version_data = version_result.result["output"]
            if isinstance(version_data, list) and version_data:
                version_info = version_data[0] if isinstance(version_data[0], dict) else {}
            else:
                version_info = _parse_version_output(version_result.result["output"], platform)
            
            if include_software:
                device_info["software"] = {
                    "version": version_info.get("version", ""),
                    "image": version_info.get("image", ""),
                    "uptime": version_info.get("uptime", ""),
                    "reload_reason": version_info.get("reload_reason", "")
                }
            
            if include_hardware:
                device_info["hardware"] = {
                    "model": version_info.get("hardware", [version_info.get("model", "")])[0] if version_info.get("hardware") else version_info.get("model", ""),
                    "serial": version_info.get("serial", ""),
                    "memory": version_info.get("memory", ""),
                    "processor": version_info.get("processor", "")
                }
        
        # Get detailed inventory if requested
        if include_inventory:
            if "ios" in platform:
                inventory_command = "show inventory"
            elif "nxos" in platform:
                inventory_command = "show inventory"
            elif "eos" in platform:
                inventory_command = "show inventory"
            elif "junos" in platform:
                inventory_command = "show chassis hardware"
            else:
                inventory_command = "show inventory"
            
            inventory_result = task.run(
                execute_command,
                command=inventory_command,
                use_textfsm=True
            )
            
            if not inventory_result.failed:
                if isinstance(inventory_result.result["output"], list):
                    device_info["inventory"] = inventory_result.result["output"]
                else:
                    device_info["inventory"] = _parse_inventory_output(
                        inventory_result.result["output"], 
                        platform
                    )
        
        return Result(
            host=task.host,
            result=device_info,
            changed=False
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            exception=e
        )


def _parse_neighbor_output(output: str, protocol: str, platform: str) -> List[Dict[str, Any]]:
    """Parse neighbor discovery output manually."""
    neighbors = []
    # Basic parsing logic - would need to be expanded for production use
    lines = output.split('\n')
    for line in lines:
        if protocol.upper() in line or 'Device ID' in line:
            # Simple parsing - would need more sophisticated logic
            parts = line.split()
            if len(parts) >= 3:
                neighbor = {
                    "neighbor_device": parts[0] if parts else "",
                    "local_interface": parts[1] if len(parts) > 1 else "",
                    "remote_interface": parts[2] if len(parts) > 2 else ""
                }
                neighbors.append(neighbor)
    return neighbors


def _parse_interface_output(output: str, platform: str) -> List[Dict[str, Any]]:
    """Parse interface output manually."""
    interfaces = []
    # Basic parsing logic - would need to be expanded for production use
    lines = output.split('\n')
    for line in lines:
        if 'Interface' in line or any(x in line for x in ['Gi', 'Fa', 'Et', 'Se']):
            parts = line.split()
            if len(parts) >= 3:
                interface = {
                    "interface": parts[0] if parts else "",
                    "ip_address": parts[1] if len(parts) > 1 else "",
                    "status": parts[2] if len(parts) > 2 else "",
                    "protocol": parts[3] if len(parts) > 3 else ""
                }
                interfaces.append(interface)
    return interfaces


def _parse_interface_config(output: str, platform: str) -> Dict[str, Dict[str, Any]]:
    """Parse interface configuration."""
    config_data = {}
    # Basic parsing logic - would need to be expanded for production use
    current_interface = None
    
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('interface '):
            current_interface = line.split()[1]
            config_data[current_interface] = {"commands": []}
        elif current_interface and line and not line.startswith('!'):
            config_data[current_interface]["commands"].append(line)
    
    return config_data


def _parse_version_output(output: str, platform: str) -> Dict[str, Any]:
    """Parse version output manually."""
    version_info = {}
    # Basic parsing logic - would need to be expanded for production use
    lines = output.split('\n')
    
    for line in lines:
        if 'Version' in line:
            version_info["version"] = line.split()[-1] if line.split() else ""
        elif 'uptime' in line.lower():
            version_info["uptime"] = line.strip()
        elif 'System image file' in line:
            version_info["image"] = line.split('"')[1] if '"' in line else ""
    
    return version_info


def _parse_inventory_output(output: str, platform: str) -> List[Dict[str, Any]]:
    """Parse inventory output manually."""
    inventory = []
    # Basic parsing logic - would need to be expanded for production use
    lines = output.split('\n')
    
    for line in lines:
        if 'PID:' in line or 'SN:' in line:
            item = {}
            parts = line.split()
            for part in parts:
                if part.startswith('PID:'):
                    item["pid"] = part.split(':')[1] if ':' in part else ""
                elif part.startswith('SN:'):
                    item["serial"] = part.split(':')[1] if ':' in part else ""
            if item:
                inventory.append(item)
    
    return inventory
