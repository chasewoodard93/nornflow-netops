"""
Enhanced Integration Framework for NornFlow.

This package provides comprehensive integration capabilities with external systems
including NetBox, Git, monitoring platforms, and ITSM systems.

The integration framework is designed with the following principles:
- Optional dependencies: Integrations gracefully handle missing dependencies
- Consistent API: All integrations follow similar patterns and interfaces
- Error handling: Robust error handling with meaningful error messages
- Configuration: Flexible configuration through NornFlow settings and task arguments
- Extensibility: Easy to add new integrations following established patterns

Available Integrations:
- NetBox: IPAM, device management, and configuration context
- Git: Configuration version control and change tracking
- Monitoring: Grafana, Prometheus, and network management platforms
- ITSM: ServiceNow and Jira integration for change management
- Network Management: Infoblox, Cisco DNA Center, SolarWinds, and others
"""

from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# Integration registry for tracking available integrations
INTEGRATION_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_integration(
    name: str,
    description: str,
    dependencies: list[str],
    tasks: list[str],
    config_schema: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    Decorator to register an integration with the framework.

    Args:
        name: Integration name (e.g., "netbox", "git")
        description: Human-readable description
        dependencies: List of required Python packages
        tasks: List of task names provided by this integration
        config_schema: Optional configuration schema

    Returns:
        Decorator function
    """
    def decorator(integration_class):
        INTEGRATION_REGISTRY[name] = {
            "class": integration_class,
            "description": description,
            "dependencies": dependencies,
            "tasks": tasks,
            "config_schema": config_schema or {},
            "available": check_dependencies(dependencies)
        }
        return integration_class
    return decorator


def check_dependencies(dependencies: list[str]) -> bool:
    """
    Check if all required dependencies are available.

    Args:
        dependencies: List of package names to check

    Returns:
        True if all dependencies are available
    """
    for dep in dependencies:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            return False
    return True


def get_available_integrations() -> Dict[str, Dict[str, Any]]:
    """
    Get all available integrations with their status.

    Returns:
        Dictionary of integration name to integration info
    """
    return {
        name: {
            "description": info["description"],
            "tasks": info["tasks"],
            "available": info["available"],
            "dependencies": info["dependencies"]
        }
        for name, info in INTEGRATION_REGISTRY.items()
    }


def get_integration_status() -> Dict[str, Any]:
    """
    Get comprehensive status of all integrations.

    Returns:
        Status summary including available/unavailable counts
    """
    available = sum(1 for info in INTEGRATION_REGISTRY.values() if info["available"])
    total = len(INTEGRATION_REGISTRY)

    return {
        "total_integrations": total,
        "available_integrations": available,
        "unavailable_integrations": total - available,
        "integrations": get_available_integrations()
    }


class IntegrationError(Exception):
    """Base exception for integration-related errors."""

    def __init__(self, message: str, integration: str, dependency: Optional[str] = None):
        self.integration = integration
        self.dependency = dependency
        super().__init__(message)


class DependencyError(IntegrationError):
    """Exception raised when required dependencies are missing."""

    def __init__(self, integration: str, dependency: str):
        message = (
            f"Integration '{integration}' requires '{dependency}' but it's not installed. "
            f"Install it with: pip install {dependency}"
        )
        super().__init__(message, integration, dependency)


class ConfigurationError(IntegrationError):
    """Exception raised when integration configuration is invalid."""

    def __init__(self, integration: str, message: str):
        super().__init__(f"Configuration error in '{integration}': {message}", integration)


def require_dependency(dependency: str, integration: str):
    """
    Decorator to ensure a dependency is available before executing a function.

    Args:
        dependency: Package name to check
        integration: Integration name for error messages

    Raises:
        DependencyError: If dependency is not available
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not check_dependencies([dependency]):
                raise DependencyError(integration, dependency)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def safe_import(module_name: str, integration: str):
    """
    Safely import a module with helpful error messages.

    Args:
        module_name: Module to import
        integration: Integration name for error messages

    Returns:
        Imported module

    Raises:
        DependencyError: If module cannot be imported
    """
    try:
        return __import__(module_name)
    except ImportError:
        raise DependencyError(integration, module_name)


# Common configuration validation functions
def validate_url(url: str, field_name: str = "url") -> str:
    """Validate URL format."""
    if not url or not isinstance(url, str):
        raise ValueError(f"{field_name} must be a non-empty string")

    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"{field_name} must start with http:// or https://")

    return url.rstrip("/")


def validate_required_field(value: Any, field_name: str) -> Any:
    """Validate that a required field is present and not empty."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{field_name} is required and cannot be empty")
    return value


def validate_optional_field(value: Any, default: Any = None) -> Any:
    """Validate optional field with default value."""
    return value if value is not None else default


# Integration base class
class BaseIntegration:
    """
    Base class for all integrations.

    Provides common functionality and interface for integrations.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize integration with configuration.

        Args:
            config: Integration configuration dictionary
        """
        self.config = config
        self.validate_config()

    def validate_config(self) -> None:
        """
        Validate integration configuration.

        Should be overridden by subclasses to implement specific validation.
        """
        pass

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the external system.

        Returns:
            Dictionary with connection test results
        """
        return {
            "success": True,
            "message": "Connection test not implemented for this integration"
        }

    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the integration.

        Returns:
            Dictionary with integration information
        """
        return {
            "name": self.__class__.__name__,
            "config": {k: "***" if "password" in k.lower() or "token" in k.lower() else v
                      for k, v in self.config.items()}
        }


# Utility functions for common integration patterns
def build_headers(auth_token: Optional[str] = None, content_type: str = "application/json") -> Dict[str, str]:
    """Build common HTTP headers for API requests."""
    headers = {"Content-Type": content_type}
    if auth_token:
        headers["Authorization"] = f"Token {auth_token}"
    return headers


def handle_api_response(response, integration_name: str) -> Dict[str, Any]:
    """
    Handle API response with common error checking.

    Args:
        response: HTTP response object
        integration_name: Name of integration for error messages

    Returns:
        Parsed response data

    Raises:
        IntegrationError: If API request failed
    """
    try:
        response.raise_for_status()
        return response.json() if response.content else {}
    except Exception as e:
        raise IntegrationError(
            f"API request failed: {str(e)}",
            integration_name
        )


def format_timestamp(dt) -> str:
    """Format datetime for API requests."""
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


# Export main components
__all__ = [
    "register_integration",
    "check_dependencies",
    "get_available_integrations",
    "get_integration_status",
    "IntegrationError",
    "DependencyError",
    "ConfigurationError",
    "require_dependency",
    "safe_import",
    "BaseIntegration",
    "validate_url",
    "validate_required_field",
    "validate_optional_field",
    "build_headers",
    "handle_api_response",
    "format_timestamp"
]