"""
Monitoring Integration for NornFlow.

This module provides integration with monitoring and network management platforms:
- Grafana: Dashboard management and alerting
- Prometheus: Metrics collection and querying
- Infoblox: DNS/DHCP/IPAM management
- Generic monitoring platform support

These integrations enable NornFlow workflows to interact with monitoring
systems for metrics collection, alerting, and network service management.
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
    name="grafana",
    description="Grafana dashboard and alerting integration",
    dependencies=["requests"],
    tasks=[
        "grafana_create_dashboard",
        "grafana_update_dashboard",
        "grafana_get_dashboard",
        "grafana_create_alert",
        "grafana_silence_alert",
        "grafana_get_metrics"
    ]
)
class GrafanaIntegration(BaseIntegration):
    """Grafana integration class."""
    
    def validate_config(self) -> None:
        """Validate Grafana configuration."""
        self.url = validate_url(validate_required_field(self.config.get("url"), "url"))
        self.api_key = validate_required_field(self.config.get("api_key"), "api_key")
        self.timeout = self.config.get("timeout", 30)
        self.ssl_verify = self.config.get("ssl_verify", True)
    
    def get_headers(self) -> Dict[str, str]:
        """Get Grafana API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Grafana connection."""
        try:
            import requests
            
            response = requests.get(
                f"{self.url}/api/health",
                headers=self.get_headers(),
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            if response.status_code == 200:
                health_data = response.json()
                return {
                    "success": True,
                    "message": f"Connected to Grafana",
                    "version": health_data.get("version"),
                    "database": health_data.get("database")
                }
            else:
                return {
                    "success": False,
                    "message": f"Grafana API returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to Grafana: {str(e)}"
            }


@register_integration(
    name="prometheus",
    description="Prometheus metrics and alerting integration",
    dependencies=["requests"],
    tasks=[
        "prometheus_query",
        "prometheus_query_range",
        "prometheus_get_targets",
        "prometheus_get_alerts",
        "prometheus_push_metrics"
    ]
)
class PrometheusIntegration(BaseIntegration):
    """Prometheus integration class."""
    
    def validate_config(self) -> None:
        """Validate Prometheus configuration."""
        self.url = validate_url(validate_required_field(self.config.get("url"), "url"))
        self.timeout = self.config.get("timeout", 30)
        self.ssl_verify = self.config.get("ssl_verify", True)
        self.pushgateway_url = self.config.get("pushgateway_url")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Prometheus connection."""
        try:
            import requests
            
            response = requests.get(
                f"{self.url}/api/v1/status/config",
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Connected to Prometheus",
                    "status": "healthy"
                }
            else:
                return {
                    "success": False,
                    "message": f"Prometheus API returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to Prometheus: {str(e)}"
            }


@register_integration(
    name="infoblox",
    description="Infoblox DNS/DHCP/IPAM integration",
    dependencies=["requests"],
    tasks=[
        "infoblox_get_network",
        "infoblox_get_next_ip",
        "infoblox_create_host_record",
        "infoblox_update_host_record",
        "infoblox_delete_host_record",
        "infoblox_get_dhcp_lease"
    ]
)
class InfobloxIntegration(BaseIntegration):
    """Infoblox integration class."""
    
    def validate_config(self) -> None:
        """Validate Infoblox configuration."""
        self.url = validate_url(validate_required_field(self.config.get("url"), "url"))
        self.username = validate_required_field(self.config.get("username"), "username")
        self.password = validate_required_field(self.config.get("password"), "password")
        self.wapi_version = self.config.get("wapi_version", "v2.12")
        self.timeout = self.config.get("timeout", 30)
        self.ssl_verify = self.config.get("ssl_verify", True)
    
    def get_auth(self) -> tuple:
        """Get Infoblox authentication."""
        return (self.username, self.password)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Infoblox connection."""
        try:
            import requests
            
            response = requests.get(
                f"{self.url}/wapi/{self.wapi_version}/grid",
                auth=self.get_auth(),
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            
            if response.status_code == 200:
                grid_data = response.json()
                return {
                    "success": True,
                    "message": "Connected to Infoblox",
                    "grid_count": len(grid_data),
                    "wapi_version": self.wapi_version
                }
            else:
                return {
                    "success": False,
                    "message": f"Infoblox API returned status {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect to Infoblox: {str(e)}"
            }


# Grafana Task Functions

@require_dependency("requests", "grafana")
def grafana_create_dashboard(
    task: Task,
    dashboard_config: Dict[str, Any],
    folder_id: Optional[int] = None,
    overwrite: bool = False,
    grafana_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create a Grafana dashboard.
    
    Args:
        task: Nornir task object
        dashboard_config: Dashboard configuration dictionary
        folder_id: Folder ID to create dashboard in
        overwrite: Whether to overwrite existing dashboard
        grafana_config: Grafana configuration
        
    Returns:
        Result containing dashboard creation status
    """
    config = grafana_config or getattr(task.host, "grafana_config", {})
    
    try:
        integration = GrafanaIntegration(config)
        import requests
        
        payload = {
            "dashboard": dashboard_config,
            "folderId": folder_id,
            "overwrite": overwrite
        }
        
        response = requests.post(
            f"{integration.url}/api/dashboards/db",
            headers=integration.get_headers(),
            json=payload,
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )
        
        result_data = handle_api_response(response, "grafana")
        
        return Result(
            host=task.host,
            result={
                "dashboard_id": result_data.get("id"),
                "dashboard_uid": result_data.get("uid"),
                "dashboard_url": result_data.get("url"),
                "version": result_data.get("version"),
                "status": result_data.get("status"),
                "message": "Dashboard created successfully"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create Grafana dashboard: {str(e)}"
        )


@require_dependency("requests", "grafana")
def grafana_silence_alert(
    task: Task,
    alert_id: Optional[str] = None,
    alert_name: Optional[str] = None,
    duration_minutes: int = 60,
    comment: Optional[str] = None,
    grafana_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Silence a Grafana alert.
    
    Args:
        task: Nornir task object
        alert_id: Alert ID to silence
        alert_name: Alert name to silence (alternative to alert_id)
        duration_minutes: Duration to silence alert
        comment: Comment for the silence
        grafana_config: Grafana configuration
        
    Returns:
        Result containing silence status
    """
    config = grafana_config or getattr(task.host, "grafana_config", {})
    
    try:
        integration = GrafanaIntegration(config)
        import requests
        
        # Calculate end time
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        silence_data = {
            "matchers": [],
            "startsAt": datetime.now().isoformat(),
            "endsAt": end_time.isoformat(),
            "comment": comment or f"Silenced by NornFlow automation for {duration_minutes} minutes"
        }
        
        if alert_id:
            silence_data["matchers"].append({
                "name": "alertname",
                "value": alert_id,
                "isRegex": False
            })
        elif alert_name:
            silence_data["matchers"].append({
                "name": "alertname", 
                "value": alert_name,
                "isRegex": False
            })
        
        response = requests.post(
            f"{integration.url}/api/alertmanager/grafana/api/v1/silences",
            headers=integration.get_headers(),
            json=silence_data,
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )
        
        result_data = handle_api_response(response, "grafana")
        
        return Result(
            host=task.host,
            result={
                "silence_id": result_data.get("silenceID"),
                "alert_id": alert_id,
                "alert_name": alert_name,
                "duration_minutes": duration_minutes,
                "end_time": end_time.isoformat(),
                "message": f"Alert silenced for {duration_minutes} minutes"
            }
        )
        
    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to silence Grafana alert: {str(e)}"
        )


# Prometheus Task Functions

@require_dependency("requests", "prometheus")
def prometheus_query(
    task: Task,
    query: str,
    time: Optional[str] = None,
    prometheus_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Execute a Prometheus query.

    Args:
        task: Nornir task object
        query: PromQL query string
        time: Query time (RFC3339 format, defaults to now)
        prometheus_config: Prometheus configuration

    Returns:
        Result containing query results
    """
    config = prometheus_config or getattr(task.host, "prometheus_config", {})

    try:
        integration = PrometheusIntegration(config)
        import requests

        params = {"query": query}
        if time:
            params["time"] = time

        response = requests.get(
            f"{integration.url}/api/v1/query",
            params=params,
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        result_data = handle_api_response(response, "prometheus")

        return Result(
            host=task.host,
            result={
                "query": query,
                "status": result_data.get("status"),
                "data": result_data.get("data"),
                "result_type": result_data.get("data", {}).get("resultType"),
                "result_count": len(result_data.get("data", {}).get("result", [])),
                "query_time": time or "now"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to execute Prometheus query: {str(e)}"
        )


@require_dependency("requests", "prometheus")
def prometheus_push_metrics(
    task: Task,
    job_name: str,
    metrics: Dict[str, Any],
    instance: Optional[str] = None,
    pushgateway_url: Optional[str] = None,
    prometheus_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Push metrics to Prometheus Pushgateway.

    Args:
        task: Nornir task object
        job_name: Job name for metrics
        metrics: Dictionary of metric names to values
        instance: Instance label (defaults to task.host.name)
        pushgateway_url: Pushgateway URL (overrides config)
        prometheus_config: Prometheus configuration

    Returns:
        Result containing push status
    """
    config = prometheus_config or getattr(task.host, "prometheus_config", {})
    instance = instance or task.host.name

    try:
        integration = PrometheusIntegration(config)
        import requests

        gateway_url = pushgateway_url or integration.pushgateway_url
        if not gateway_url:
            return Result(
                host=task.host,
                failed=True,
                result="Pushgateway URL not configured"
            )

        # Format metrics in Prometheus exposition format
        metric_lines = []
        for metric_name, value in metrics.items():
            metric_lines.append(f"{metric_name} {value}")

        metric_data = "\n".join(metric_lines)

        # Push to gateway
        url = f"{gateway_url}/metrics/job/{job_name}/instance/{instance}"
        response = requests.post(
            url,
            data=metric_data,
            headers={"Content-Type": "text/plain"},
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        response.raise_for_status()

        return Result(
            host=task.host,
            result={
                "job_name": job_name,
                "instance": instance,
                "metrics_pushed": len(metrics),
                "metrics": list(metrics.keys()),
                "pushgateway_url": gateway_url,
                "message": f"Successfully pushed {len(metrics)} metrics"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to push metrics to Prometheus: {str(e)}"
        )


# Infoblox Task Functions

@require_dependency("requests", "infoblox")
def infoblox_get_next_ip(
    task: Task,
    network: str,
    exclude_dhcp: bool = True,
    infoblox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Get next available IP address from Infoblox network.

    Args:
        task: Nornir task object
        network: Network CIDR (e.g., "192.168.1.0/24")
        exclude_dhcp: Exclude DHCP ranges from allocation
        infoblox_config: Infoblox configuration

    Returns:
        Result containing next available IP
    """
    config = infoblox_config or getattr(task.host, "infoblox_config", {})

    try:
        integration = InfobloxIntegration(config)
        import requests

        # Get network object
        params = {"network": network}
        response = requests.get(
            f"{integration.url}/wapi/{integration.wapi_version}/network",
            params=params,
            auth=integration.get_auth(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        networks = handle_api_response(response, "infoblox")

        if not networks:
            return Result(
                host=task.host,
                failed=True,
                result=f"Network '{network}' not found in Infoblox"
            )

        network_ref = networks[0]["_ref"]

        # Get next available IP
        next_ip_params = {"num": 1}
        if exclude_dhcp:
            next_ip_params["exclude"] = "dhcp"

        response = requests.post(
            f"{integration.url}/wapi/{integration.wapi_version}/{network_ref}",
            params={"_function": "next_available_ip"},
            json=next_ip_params,
            auth=integration.get_auth(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        result_data = handle_api_response(response, "infoblox")

        if result_data and "ips" in result_data:
            next_ip = result_data["ips"][0]
            return Result(
                host=task.host,
                result={
                    "network": network,
                    "next_ip": next_ip,
                    "network_ref": network_ref,
                    "exclude_dhcp": exclude_dhcp
                }
            )
        else:
            return Result(
                host=task.host,
                failed=True,
                result=f"No available IPs in network '{network}'"
            )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to get next IP from Infoblox: {str(e)}"
        )


@require_dependency("requests", "infoblox")
def infoblox_create_host_record(
    task: Task,
    hostname: str,
    ip_address: str,
    view: str = "default",
    configure_for_dns: bool = True,
    infoblox_config: Optional[Dict[str, Any]] = None
) -> Result:
    """
    Create a host record in Infoblox.

    Args:
        task: Nornir task object
        hostname: Hostname for the record
        ip_address: IP address for the record
        view: DNS view (defaults to "default")
        configure_for_dns: Whether to configure for DNS
        infoblox_config: Infoblox configuration

    Returns:
        Result containing host record creation status
    """
    config = infoblox_config or getattr(task.host, "infoblox_config", {})

    try:
        integration = InfobloxIntegration(config)
        import requests

        host_data = {
            "name": hostname,
            "ipv4addrs": [{"ipv4addr": ip_address}],
            "view": view,
            "configure_for_dns": configure_for_dns
        }

        response = requests.post(
            f"{integration.url}/wapi/{integration.wapi_version}/record:host",
            json=host_data,
            auth=integration.get_auth(),
            timeout=integration.timeout,
            verify=integration.ssl_verify
        )

        result_data = handle_api_response(response, "infoblox")

        return Result(
            host=task.host,
            result={
                "hostname": hostname,
                "ip_address": ip_address,
                "view": view,
                "host_ref": result_data,
                "configure_for_dns": configure_for_dns,
                "message": f"Host record created for {hostname} -> {ip_address}"
            }
        )

    except Exception as e:
        return Result(
            host=task.host,
            failed=True,
            result=f"Failed to create Infoblox host record: {str(e)}"
        )
