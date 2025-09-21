"""
NetBox Integration for NornFlow.

This module provides comprehensive NetBox integration including:
- Dynamic inventory from NetBox
- IP address management (IPAM)
- Device status synchronization
- Configuration context integration
- Site and rack management

NetBox serves as the "source of truth" for network infrastructure,
and this integration allows NornFlow workflows to interact with
NetBox data and keep it synchronized.
"""

from typing import Dict, Any, List, Optional, Union
from nornir.core.task import Task, Result
import logging

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
    name="netbox",
    description="NetBox IPAM and DCIM integration for network automation",
    dependencies=["pynetbox", "requests"],
    tasks=[
        "netbox_get_device",
        "netbox_update_device", 
        "netbox_get_available_ip",
        "netbox_assign_ip",
        "netbox_get_config_context",
        "netbox_sync_interfaces",
        "netbox_create_device",
        "netbox_get_site_devices"
    ]
)
class NetBoxIntegration(BaseIntegration):
    """NetBox integration class."""
    
    def validate_config(self) -> None:
        """Validate NetBox configuration."""
        self.url = validate_url(validate_required_field(self.config.get("url"), "url"))
        self.token = validate_required_field(self.config.get("token"), "token")
        self.ssl_verify = self.config.get("ssl_verify", True)
        self.timeout = self.config.get("timeout", 30)
    
    @require_dependency("pynetbox", "netbox")
    def get_api(self):
        """Get NetBox API client."""
        import pynetbox
        
        api = pynetbox.api(
            url=self.url,
            token=self.token
        )
        api.http_session.verify = self.ssl_verify
        api.http_session.timeout = self.timeout
        
        return api
    
    def test_connection(self) -> Dict[str, Any]:
        """Test NetBox connection."""
        try:
            api = self.get_api()
            # Test by getting NetBox status
            status = api.status()
            return {
                "success": True,
                "message": f"Connected to NetBox {status.get('netbox-version', 'unknown')}",
                "netbox_version": status.get("netbox-version"),
                "python_version": status.get("python-version"),
                "plugins": status.get("plugins", {})
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to NetBox: {str(e)}"
            }


# NetBox Task Functions

@require_dependency("pynetbox", "netbox")
def netbox_get_device(
    task: Task,
    device_name: Optional[str] = None,
    device_id: Optional[int] = None,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get device information from NetBox.
    
    Args:
        task: Nornir task object
        device_name: Device name to lookup (defaults to task.host.name)
        device_id: Device ID to lookup (alternative to device_name)
        netbox_config: NetBox configuration (url, token, etc.)
        
    Returns:
        Result containing device information
    """
    device_name = device_name or task.host.name
    config = netbox_config or getattr(task.host, "netbox_config", {})
    
    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()
        
        if device_id:
            device = api.dcim.devices.get(device_id)
        else:
            device = api.dcim.devices.get(name=device_name)
        
        if not device:
            return Result(
                host=task.host,
                failed=True,
                result=f"Device '{device_name}' not found in NetBox"
            )
        
        device_data = {
            "id": device.id,
            "name": device.name,
            "device_type": str(device.device_type),
            "device_role": str(device.device_role),
            "platform": str(device.platform) if device.platform else None,
            "site": str(device.site),
            "rack": str(device.rack) if device.rack else None,
            "position": device.position,
            "serial": device.serial,
            "asset_tag": device.asset_tag,
            "status": str(device.status),
            "primary_ip4": str(device.primary_ip4) if device.primary_ip4 else None,
            "primary_ip6": str(device.primary_ip6) if device.primary_ip6 else None,
            "config_context": device.config_context,
            "custom_fields": device.custom_fields,
            "tags": [str(tag) for tag in device.tags.all()],
            "url": device.url
        }
        
        return Result(
            host=task.host,
            result=device_data
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get device from NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_update_device(
    task: Task,
    device_name: Optional[str] = None,
    device_id: Optional[int] = None,
    updates: Optional[Dict[str, Any]] = None,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Update device information in NetBox.
    
    Args:
        task: Nornir task object
        device_name: Device name to update (defaults to task.host.name)
        device_id: Device ID to update (alternative to device_name)
        updates: Dictionary of fields to update
        netbox_config: NetBox configuration
        
    Returns:
        Result containing update status
    """
    device_name = device_name or task.host.name
    config = netbox_config or getattr(task.host, "netbox_config", {})
    updates = updates or {}
    
    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()
        
        if device_id:
            device = api.dcim.devices.get(device_id)
        else:
            device = api.dcim.devices.get(name=device_name)
        
        if not device:
            return Result(
                host=task.host,
                failed=True,
                result=f"Device '{device_name}' not found in NetBox"
            )
        
        # Apply updates
        for field, value in updates.items():
            if hasattr(device, field):
                setattr(device, field, value)
        
        # Save changes
        device.save()
        
        return Result(
            host=task.host,
            result={
                "device_id": device.id,
                "device_name": device.name,
                "updated_fields": list(updates.keys()),
                "message": f"Successfully updated device '{device.name}'"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to update device in NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_get_available_ip(
    task: Task,
    prefix: str,
    description: Optional[str] = None,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get next available IP address from a NetBox prefix.
    
    Args:
        task: Nornir task object
        prefix: Network prefix (e.g., "192.168.1.0/24")
        description: Description for the IP assignment
        netbox_config: NetBox configuration
        
    Returns:
        Result containing available IP address
    """
    config = netbox_config or getattr(task.host, "netbox_config", {})
    
    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()
        
        # Get the prefix object
        prefix_obj = api.ipam.prefixes.get(prefix=prefix)
        if not prefix_obj:
            return Result(
                host=task.host,
                failed=True,
                result=f"Prefix '{prefix}' not found in NetBox"
            )
        
        # Get available IP
        available_ips = prefix_obj.available_ips.list()
        if not available_ips:
            return Result(
                host=task.host,
                failed=True,
                result=f"No available IPs in prefix '{prefix}'"
            )
        
        next_ip = available_ips[0]
        
        return Result(
            host=task.host,
            result={
                "ip_address": str(next_ip),
                "prefix": prefix,
                "prefix_id": prefix_obj.id,
                "description": description or f"Auto-assigned to {task.host.name}"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get available IP from NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_assign_ip(
    task: Task,
    ip_address: str,
    device_name: Optional[str] = None,
    interface_name: Optional[str] = None,
    description: Optional[str] = None,
    is_primary: bool = False,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Assign IP address to device interface in NetBox.
    
    Args:
        task: Nornir task object
        ip_address: IP address to assign (with CIDR notation)
        device_name: Device name (defaults to task.host.name)
        interface_name: Interface name to assign IP to
        description: Description for the IP assignment
        is_primary: Whether this should be the primary IP
        netbox_config: NetBox configuration
        
    Returns:
        Result containing assignment status
    """
    device_name = device_name or task.host.name
    config = netbox_config or getattr(task.host, "netbox_config", {})
    
    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()
        
        # Get device
        device = api.dcim.devices.get(name=device_name)
        if not device:
            return Result(
                host=task.host,
                failed=True,
                result=f"Device '{device_name}' not found in NetBox"
            )
        
        # Get interface if specified
        interface = None
        if interface_name:
            interface = api.dcim.interfaces.get(
                device_id=device.id,
                name=interface_name
            )
            if not interface:
                return Result(
                    host=task.host,
                    failed=True,
                    result=f"Interface '{interface_name}' not found on device '{device_name}'"
                )
        
        # Create IP address assignment
        ip_data = {
            "address": ip_address,
            "description": description or f"Assigned to {device_name}",
            "assigned_object_type": "dcim.interface" if interface else None,
            "assigned_object_id": interface.id if interface else None
        }
        
        ip_obj = api.ipam.ip_addresses.create(ip_data)
        
        # Set as primary IP if requested
        if is_primary:
            if "/" in ip_address:
                primary_ip = ip_address.split("/")[0]
            else:
                primary_ip = ip_address
                
            device.primary_ip4 = ip_obj.id
            device.save()
        
        return Result(
            host=task.host,
            result={
                "ip_address": str(ip_obj.address),
                "ip_id": ip_obj.id,
                "device_name": device_name,
                "interface_name": interface_name,
                "is_primary": is_primary,
                "message": f"Successfully assigned IP {ip_obj.address} to {device_name}"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to assign IP in NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_get_config_context(
    task: Task,
    device_name: Optional[str] = None,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get configuration context for a device from NetBox.

    Args:
        task: Nornir task object
        device_name: Device name (defaults to task.host.name)
        netbox_config: NetBox configuration

    Returns:
        Result containing configuration context
    """
    device_name = device_name or task.host.name
    config = netbox_config or getattr(task.host, "netbox_config", {})

    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()

        device = api.dcim.devices.get(name=device_name)
        if not device:
            return Result(
                host=task.host,
                failed=True,
                result=f"Device '{device_name}' not found in NetBox"
            )

        config_context = device.config_context

        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "config_context": config_context,
                "context_keys": list(config_context.keys()) if config_context else []
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get config context from NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_sync_interfaces(
    task: Task,
    device_name: Optional[str] = None,
    interfaces_data: Optional[List[Dict[str, Any]]] = None,
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Synchronize interface information with NetBox.

    Args:
        task: Nornir task object
        device_name: Device name (defaults to task.host.name)
        interfaces_data: List of interface data dictionaries
        netbox_config: NetBox configuration

    Returns:
        Result containing sync status
    """
    device_name = device_name or task.host.name
    config = netbox_config or getattr(task.host, "netbox_config", {})
    interfaces_data = interfaces_data or []

    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()

        device = api.dcim.devices.get(name=device_name)
        if not device:
            return Result(
                host=task.host,
                failed=True,
                result=f"Device '{device_name}' not found in NetBox"
            )

        # Get existing interfaces
        existing_interfaces = {
            intf.name: intf
            for intf in api.dcim.interfaces.filter(device_id=device.id)
        }

        sync_results = {
            "created": [],
            "updated": [],
            "unchanged": [],
            "errors": []
        }

        for intf_data in interfaces_data:
            intf_name = intf_data.get("name")
            if not intf_name:
                sync_results["errors"].append("Interface missing name field")
                continue

            try:
                if intf_name in existing_interfaces:
                    # Update existing interface
                    interface = existing_interfaces[intf_name]
                    updated = False

                    for field, value in intf_data.items():
                        if field != "name" and hasattr(interface, field):
                            if getattr(interface, field) != value:
                                setattr(interface, field, value)
                                updated = True

                    if updated:
                        interface.save()
                        sync_results["updated"].append(intf_name)
                    else:
                        sync_results["unchanged"].append(intf_name)
                else:
                    # Create new interface
                    intf_data["device"] = device.id
                    interface = api.dcim.interfaces.create(intf_data)
                    sync_results["created"].append(intf_name)

            except Exception as e:
                sync_results["errors"].append(f"Error syncing {intf_name}: {str(e)}")

        return Result(
            host=task.host,
            result={
                "device_name": device_name,
                "sync_results": sync_results,
                "total_interfaces": len(interfaces_data),
                "message": f"Synced {len(interfaces_data)} interfaces for {device_name}"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to sync interfaces with NetBox: {str(e)}"
        )


@require_dependency("pynetbox", "netbox")
def netbox_get_site_devices(
    task: Task,
    site_name: str,
    device_role: Optional[str] = None,
    status: Optional[str] = "active",
    netbox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get all devices from a NetBox site.

    Args:
        task: Nornir task object
        site_name: Site name to query
        device_role: Optional device role filter
        status: Device status filter (default: "active")
        netbox_config: NetBox configuration

    Returns:
        Result containing list of devices
    """
    config = netbox_config or getattr(task.host, "netbox_config", {})

    try:
        integration = NetBoxIntegration(config)
        api = integration.get_api()

        # Get site
        site = api.dcim.sites.get(name=site_name)
        if not site:
            return Result(
                host=task.host,
                failed=True,
                result=f"Site '{site_name}' not found in NetBox"
            )

        # Build filter parameters
        filter_params = {"site_id": site.id}
        if device_role:
            filter_params["role"] = device_role
        if status:
            filter_params["status"] = status

        # Get devices
        devices = api.dcim.devices.filter(**filter_params)

        device_list = []
        for device in devices:
            device_info = {
                "id": device.id,
                "name": device.name,
                "device_type": str(device.device_type),
                "device_role": str(device.device_role),
                "platform": str(device.platform) if device.platform else None,
                "status": str(device.status),
                "primary_ip4": str(device.primary_ip4) if device.primary_ip4 else None,
                "rack": str(device.rack) if device.rack else None,
                "position": device.position
            }
            device_list.append(device_info)

        return Result(
            host=task.host,
            result={
                "site_name": site_name,
                "site_id": site.id,
                "device_count": len(device_list),
                "devices": device_list,
                "filters": filter_params
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get site devices from NetBox: {str(e)}"
        )
