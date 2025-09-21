#!/usr/bin/env python3
"""
Visualization Setup Utility for NornFlow.

This utility provides easy setup and configuration for the workflow
visualization and monitoring system.

Features:
- Automated setup of visualization components
- Configuration management
- Integration with existing NornFlow installations
- Development and production deployment options
- Health checks and diagnostics

Usage:
    python visualization_setup.py --setup-dashboard
    python visualization_setup.py --start-monitoring --port 5000
    python visualization_setup.py --check-health
    python visualization_setup.py --create-config
"""

import argparse
import json
import yaml
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import logging
import shutil
import os

from .monitoring_dashboard import MonitoringDashboard
from .workflow_visualizer import WorkflowVisualizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VisualizationSetup:
    """Setup and configuration manager for NornFlow visualization system."""
    
    def __init__(self, config_file: Path = None):
        """Initialize setup manager."""
        self.config_file = config_file or Path("visualization_config.yaml")
        self.config = self._load_or_create_config()
        
        # Default configuration
        self.default_config = {
            "dashboard": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "secret_key": "nornflow-visualization-secret-key"
            },
            "visualization": {
                "workflow_dirs": ["workflows", "sample_workflows"],
                "max_history": 1000,
                "update_interval": 30
            },
            "monitoring": {
                "enable_system_metrics": True,
                "enable_performance_tracking": True,
                "metrics_retention_days": 30
            },
            "security": {
                "enable_auth": False,
                "auth_provider": "local",
                "session_timeout": 3600
            }
        }
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load existing config or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config: {str(e)}, using defaults")
        
        return {}
    
    def create_config_file(self, force: bool = False) -> Dict[str, Any]:
        """
        Create configuration file with default settings.
        
        Args:
            force: Overwrite existing config file
            
        Returns:
            Configuration creation result
        """
        if self.config_file.exists() and not force:
            return {
                "success": False,
                "message": f"Config file already exists: {self.config_file}. Use --force to overwrite."
            }
        
        try:
            # Merge with existing config
            config = {**self.default_config, **self.config}
            
            with open(self.config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration file created: {self.config_file}")
            
            return {
                "success": True,
                "config_file": str(self.config_file),
                "message": f"Configuration file created successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to create config file: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create config file: {str(e)}"
            }
    
    def setup_dashboard(self, install_dependencies: bool = True) -> Dict[str, Any]:
        """
        Setup the monitoring dashboard.
        
        Args:
            install_dependencies: Install required Python packages
            
        Returns:
            Setup result
        """
        logger.info("Setting up NornFlow visualization dashboard...")
        
        results = {
            "dependencies": {"success": True, "message": "Skipped"},
            "directories": {"success": True, "message": "Created"},
            "templates": {"success": True, "message": "Verified"},
            "config": {"success": True, "message": "Loaded"}
        }
        
        try:
            # Install dependencies if requested
            if install_dependencies:
                results["dependencies"] = self._install_dependencies()
            
            # Create required directories
            results["directories"] = self._create_directories()
            
            # Verify templates exist
            results["templates"] = self._verify_templates()
            
            # Create/update config
            if not self.config_file.exists():
                results["config"] = self.create_config_file()
            
            # Overall success
            overall_success = all(result["success"] for result in results.values())
            
            if overall_success:
                logger.info("Dashboard setup completed successfully!")
                return {
                    "success": True,
                    "message": "Dashboard setup completed successfully",
                    "details": results
                }
            else:
                logger.error("Dashboard setup completed with errors")
                return {
                    "success": False,
                    "message": "Dashboard setup completed with errors",
                    "details": results
                }
        
        except Exception as e:
            logger.error(f"Dashboard setup failed: {str(e)}")
            return {
                "success": False,
                "message": f"Dashboard setup failed: {str(e)}",
                "details": results
            }
    
    def _install_dependencies(self) -> Dict[str, Any]:
        """Install required Python dependencies."""
        required_packages = [
            "flask>=2.0.0",
            "flask-socketio>=5.0.0",
            "networkx>=2.6.0",
            "psutil>=5.8.0",
            "jinja2>=3.0.0"
        ]
        
        try:
            logger.info("Installing required dependencies...")
            
            for package in required_packages:
                logger.info(f"Installing {package}...")
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", package
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"Failed to install {package}: {result.stderr}")
            
            return {
                "success": True,
                "message": f"Installed {len(required_packages)} packages"
            }
        
        except Exception as e:
            logger.error(f"Dependency installation failed: {str(e)}")
            return {
                "success": False,
                "message": f"Dependency installation failed: {str(e)}"
            }
    
    def _create_directories(self) -> Dict[str, Any]:
        """Create required directories."""
        directories = [
            "logs",
            "static",
            "templates",
            "data"
        ]
        
        try:
            base_path = Path(__file__).parent
            created = []
            
            for directory in directories:
                dir_path = base_path / directory
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    created.append(str(dir_path))
            
            return {
                "success": True,
                "message": f"Created {len(created)} directories",
                "created": created
            }
        
        except Exception as e:
            logger.error(f"Directory creation failed: {str(e)}")
            return {
                "success": False,
                "message": f"Directory creation failed: {str(e)}"
            }
    
    def _verify_templates(self) -> Dict[str, Any]:
        """Verify required templates exist."""
        template_dir = Path(__file__).parent / "templates"
        required_templates = ["dashboard.html"]
        
        missing = []
        for template in required_templates:
            template_path = template_dir / template
            if not template_path.exists():
                missing.append(template)
        
        if missing:
            return {
                "success": False,
                "message": f"Missing templates: {', '.join(missing)}"
            }
        
        return {
            "success": True,
            "message": f"All {len(required_templates)} templates verified"
        }
    
    def start_monitoring_server(self, host: str = None, port: int = None, debug: bool = None) -> Dict[str, Any]:
        """
        Start the monitoring dashboard server.
        
        Args:
            host: Host to bind to (overrides config)
            port: Port to bind to (overrides config)
            debug: Enable debug mode (overrides config)
            
        Returns:
            Server start result
        """
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            
            # Override with parameters
            dashboard_config = config.get("dashboard", {})
            host = host or dashboard_config.get("host", "0.0.0.0")
            port = port or dashboard_config.get("port", 5000)
            debug = debug if debug is not None else dashboard_config.get("debug", False)
            
            logger.info(f"Starting monitoring dashboard on {host}:{port}")
            
            # Create dashboard instance
            dashboard = MonitoringDashboard(config)
            
            # Start server (this will block)
            dashboard.start_monitoring_server(host=host, port=port, debug=debug)
            
            return {
                "success": True,
                "message": f"Server started on {host}:{port}"
            }
        
        except Exception as e:
            logger.error(f"Failed to start monitoring server: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to start monitoring server: {str(e)}"
            }
    
    def check_health(self) -> Dict[str, Any]:
        """
        Perform health check of visualization system.
        
        Returns:
            Health check results
        """
        logger.info("Performing health check...")
        
        checks = {
            "config": self._check_config(),
            "dependencies": self._check_dependencies(),
            "directories": self._check_directories(),
            "templates": self._check_templates(),
            "permissions": self._check_permissions()
        }
        
        # Overall health
        overall_healthy = all(check["healthy"] for check in checks.values())
        
        return {
            "healthy": overall_healthy,
            "checks": checks,
            "message": "System healthy" if overall_healthy else "Issues detected"
        }
    
    def _check_config(self) -> Dict[str, Any]:
        """Check configuration health."""
        try:
            if not self.config_file.exists():
                return {
                    "healthy": False,
                    "message": "Configuration file not found"
                }
            
            # Validate config structure
            required_sections = ["dashboard", "visualization", "monitoring"]
            missing_sections = []
            
            for section in required_sections:
                if section not in self.config:
                    missing_sections.append(section)
            
            if missing_sections:
                return {
                    "healthy": False,
                    "message": f"Missing config sections: {', '.join(missing_sections)}"
                }
            
            return {
                "healthy": True,
                "message": "Configuration valid"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Config check failed: {str(e)}"
            }
    
    def _check_dependencies(self) -> Dict[str, Any]:
        """Check required dependencies."""
        required_modules = [
            "flask",
            "flask_socketio", 
            "networkx",
            "psutil",
            "jinja2"
        ]
        
        missing = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        
        if missing:
            return {
                "healthy": False,
                "message": f"Missing dependencies: {', '.join(missing)}"
            }
        
        return {
            "healthy": True,
            "message": "All dependencies available"
        }
    
    def _check_directories(self) -> Dict[str, Any]:
        """Check required directories."""
        base_path = Path(__file__).parent
        required_dirs = ["templates"]
        
        missing = []
        for directory in required_dirs:
            dir_path = base_path / directory
            if not dir_path.exists():
                missing.append(directory)
        
        if missing:
            return {
                "healthy": False,
                "message": f"Missing directories: {', '.join(missing)}"
            }
        
        return {
            "healthy": True,
            "message": "All directories present"
        }
    
    def _check_templates(self) -> Dict[str, Any]:
        """Check required templates."""
        return self._verify_templates()
    
    def _check_permissions(self) -> Dict[str, Any]:
        """Check file permissions."""
        try:
            # Check if we can write to current directory
            test_file = Path("test_permissions.tmp")
            test_file.write_text("test")
            test_file.unlink()
            
            return {
                "healthy": True,
                "message": "Permissions OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Permission check failed: {str(e)}"
            }
    
    def generate_sample_workflow(self, output_file: Path) -> Dict[str, Any]:
        """Generate sample workflow for testing visualization."""
        sample_workflow = {
            "name": "Sample Network Configuration Workflow",
            "description": "Sample workflow for testing visualization features",
            "vars": {
                "devices": ["router-01", "switch-01"],
                "config_template": "base_config.j2"
            },
            "tasks": [
                {
                    "name": "backup_configurations",
                    "task": "backup_device_config",
                    "description": "Backup current device configurations",
                    "vars": {
                        "devices": "{{ devices }}",
                        "backup_location": "backups/"
                    }
                },
                {
                    "name": "validate_connectivity",
                    "task": "ping_devices",
                    "description": "Validate device connectivity",
                    "vars": {
                        "devices": "{{ devices }}"
                    },
                    "depends_on": ["backup_configurations"]
                },
                {
                    "name": "deploy_configuration",
                    "task": "deploy_config_template",
                    "description": "Deploy new configuration",
                    "vars": {
                        "template": "{{ config_template }}",
                        "devices": "{{ devices }}"
                    },
                    "depends_on": ["validate_connectivity"],
                    "when": "deployment_approved == true"
                },
                {
                    "name": "validate_deployment",
                    "task": "validate_configuration",
                    "description": "Validate deployed configuration",
                    "vars": {
                        "devices": "{{ devices }}",
                        "tests": ["connectivity", "routing", "services"]
                    },
                    "depends_on": ["deploy_configuration"],
                    "rescue": [
                        {
                            "name": "rollback_configuration",
                            "task": "restore_backup",
                            "vars": {
                                "devices": "{{ devices }}",
                                "backup_location": "backups/"
                            }
                        }
                    ]
                },
                {
                    "name": "update_documentation",
                    "task": "update_network_docs",
                    "description": "Update network documentation",
                    "vars": {
                        "devices": "{{ devices }}",
                        "changes": "{{ deployment_changes }}"
                    },
                    "depends_on": ["validate_deployment"],
                    "always": True
                }
            ]
        }
        
        try:
            with open(output_file, 'w') as f:
                yaml.dump(sample_workflow, f, default_flow_style=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Sample workflow created: {output_file}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create sample workflow: {str(e)}"
            }


def main():
    """Main entry point for visualization setup utility."""
    parser = argparse.ArgumentParser(description="Setup NornFlow visualization system")
    parser.add_argument("--setup-dashboard", action="store_true", help="Setup monitoring dashboard")
    parser.add_argument("--start-monitoring", action="store_true", help="Start monitoring server")
    parser.add_argument("--check-health", action="store_true", help="Perform health check")
    parser.add_argument("--create-config", action="store_true", help="Create configuration file")
    parser.add_argument("--create-sample", type=Path, help="Create sample workflow file")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup = VisualizationSetup(args.config)
        
        # Create configuration file
        if args.create_config:
            result = setup.create_config_file(args.force)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Create sample workflow
        if args.create_sample:
            result = setup.generate_sample_workflow(args.create_sample)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Setup dashboard
        if args.setup_dashboard:
            result = setup.setup_dashboard(args.install_deps)
            print(json.dumps(result, indent=2, default=str))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Health check
        if args.check_health:
            result = setup.check_health()
            print(json.dumps(result, indent=2))
            if not result["healthy"]:
                sys.exit(1)
            return
        
        # Start monitoring server
        if args.start_monitoring:
            result = setup.start_monitoring_server(args.host, args.port, args.debug)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Setup operation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
