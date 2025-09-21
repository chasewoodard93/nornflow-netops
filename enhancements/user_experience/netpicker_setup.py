#!/usr/bin/env python3
"""
NetPicker Setup Utility for NornFlow.

This utility helps set up NetPicker for running NornFlow workflows:
- Registers NornFlow workflows as NetPicker scripts
- Creates variable forms for workflow parameters
- Sets up secrets configuration
- Generates documentation

Usage:
    python netpicker_setup.py --workflows-dir workflows/
    python netpicker_setup.py --config netpicker_config.yaml
    python netpicker_setup.py --workflow workflows/network_config.yaml
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from netpicker_integration import NetPickerIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NetPickerSetupManager:
    """Manages the complete NetPicker setup process for NornFlow."""
    
    def __init__(self, config_file: Path = None):
        """Initialize setup manager with configuration."""
        self.config = self._load_config(config_file)
        self.netpicker = NetPickerIntegration(self.config["netpicker"])
        
    def _load_config(self, config_file: Path = None) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Return default configuration
        return {
            "netpicker": {
                "scripts_dir": "/opt/netpicker/scripts",
                "config_dir": "/opt/netpicker/config",
                "secrets_dir": "/opt/netpicker/secrets",
                "nornflow_path": "/opt/nornflow",
                "workflows_path": "workflows",
                "category": "Network Automation"
            },
            "secrets": {
                "network_devices": {
                    "username": "admin",
                    "password": "device-password",
                    "enable_password": "enable-password"
                },
                "netbox": {
                    "url": "https://netbox.company.com",
                    "token": "netbox-api-token"
                },
                "grafana": {
                    "url": "https://grafana.company.com",
                    "api_key": "grafana-api-key"
                },
                "servicenow": {
                    "url": "https://company.service-now.com",
                    "username": "servicenow-user",
                    "password": "servicenow-password"
                },
                "jira": {
                    "url": "https://company.atlassian.net",
                    "username": "jira-user",
                    "token": "jira-api-token"
                }
            }
        }
    
    def setup_complete_environment(self, workflows_dir: Path) -> Dict[str, Any]:
        """Set up complete NetPicker environment for NornFlow."""
        logger.info("Starting complete NetPicker environment setup for NornFlow")
        
        results = {
            "workflows": None,
            "secrets": None,
            "documentation": None
        }
        
        # Register all workflows
        logger.info(f"Registering workflows from: {workflows_dir}")
        results["workflows"] = self.netpicker.register_all_workflows(workflows_dir)
        
        if not results["workflows"]["success"]:
            logger.error(f"Workflow registration failed: {results['workflows']['message']}")
            return results
        
        logger.info(f"Workflows registered: {results['workflows']['message']}")
        
        # Create secrets configuration
        logger.info("Creating secrets configuration...")
        results["secrets"] = self.netpicker.create_secrets_config(self.config["secrets"])
        
        if not results["secrets"]["success"]:
            logger.error(f"Secrets configuration failed: {results['secrets']['message']}")
        else:
            logger.info(f"Secrets configured: {results['secrets']['message']}")
        
        # Generate documentation
        logger.info("Generating setup documentation...")
        try:
            doc_content = self.netpicker.generate_setup_documentation()
            doc_file = Path("netpicker_setup_guide.md")
            with open(doc_file, 'w') as f:
                f.write(doc_content)
            
            results["documentation"] = {
                "success": True,
                "file": str(doc_file),
                "message": "Setup documentation generated successfully"
            }
            logger.info(f"Documentation created: {doc_file}")
        
        except Exception as e:
            results["documentation"] = {
                "success": False,
                "message": f"Documentation generation failed: {str(e)}"
            }
        
        logger.info("NetPicker environment setup completed!")
        return results
    
    def register_single_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """Register a single workflow with NetPicker."""
        logger.info(f"Registering workflow: {workflow_file}")
        
        result = self.netpicker.register_workflow(workflow_file)
        
        if result["success"]:
            logger.info(f"Workflow registered successfully: {result['message']}")
        else:
            logger.error(f"Workflow registration failed: {result['message']}")
        
        return result
    
    def create_sample_config(self, output_file: Path) -> Dict[str, Any]:
        """Create a sample configuration file."""
        sample_config = {
            "netpicker": {
                "scripts_dir": "/opt/netpicker/scripts",
                "config_dir": "/opt/netpicker/config", 
                "secrets_dir": "/opt/netpicker/secrets",
                "nornflow_path": "/opt/nornflow",
                "workflows_path": "workflows",
                "category": "Network Automation"
            },
            "secrets": {
                "network_devices": {
                    "description": "SSH credentials for network devices",
                    "username": "admin",
                    "password": "${DEVICE_PASSWORD}",
                    "enable_password": "${ENABLE_PASSWORD}"
                },
                "netbox": {
                    "description": "NetBox IPAM/DCIM integration",
                    "url": "https://netbox.company.com",
                    "token": "${NETBOX_TOKEN}"
                },
                "grafana": {
                    "description": "Grafana monitoring integration",
                    "url": "https://grafana.company.com",
                    "api_key": "${GRAFANA_API_KEY}"
                },
                "prometheus": {
                    "description": "Prometheus monitoring integration",
                    "url": "https://prometheus.company.com",
                    "pushgateway_url": "https://pushgateway.company.com"
                },
                "servicenow": {
                    "description": "ServiceNow ITSM integration",
                    "url": "https://company.service-now.com",
                    "username": "${SERVICENOW_USER}",
                    "password": "${SERVICENOW_PASS}"
                },
                "jira": {
                    "description": "Jira issue tracking integration",
                    "url": "https://company.atlassian.net",
                    "username": "${JIRA_USER}",
                    "token": "${JIRA_TOKEN}"
                },
                "infoblox": {
                    "description": "Infoblox DNS/DHCP integration",
                    "url": "https://infoblox.company.com",
                    "username": "${INFOBLOX_USER}",
                    "password": "${INFOBLOX_PASS}",
                    "wapi_version": "v2.12"
                }
            },
            "execution": {
                "default_timeout": 3600,
                "require_approval_for_production": True,
                "enable_dry_run": True,
                "log_level": "INFO"
            },
            "ui_customization": {
                "category_name": "Network Automation",
                "script_prefix": "nornflow_",
                "form_theme": "bootstrap",
                "show_advanced_options": False
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                yaml.dump(sample_config, f, default_flow_style=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Sample configuration created: {output_file}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create sample config: {str(e)}"
            }
    
    def validate_environment(self) -> Dict[str, Any]:
        """Validate NetPicker environment setup."""
        issues = []
        
        # Check directories
        required_dirs = [
            self.netpicker.scripts_dir,
            self.netpicker.config_dir,
            self.netpicker.secrets_dir
        ]
        
        for directory in required_dirs:
            if not directory.exists():
                issues.append(f"Directory does not exist: {directory}")
            elif not os.access(directory, os.W_OK):
                issues.append(f"Directory is not writable: {directory}")
        
        # Check NornFlow installation
        nornflow_path = Path(self.netpicker.nornflow_path)
        if not nornflow_path.exists():
            issues.append(f"NornFlow path does not exist: {nornflow_path}")
        
        nornflow_bin = nornflow_path / "bin" / "nornflow"
        if not nornflow_bin.exists():
            issues.append(f"NornFlow binary not found: {nornflow_bin}")
        
        # Check workflows directory
        workflows_path = Path(self.netpicker.workflows_path)
        if not workflows_path.exists():
            issues.append(f"Workflows directory does not exist: {workflows_path}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message": "Environment is valid" if len(issues) == 0 else f"Found {len(issues)} issues"
        }


def main():
    """Main entry point for NetPicker setup utility."""
    parser = argparse.ArgumentParser(description="Set up NetPicker for NornFlow workflows")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--workflows-dir", type=Path, help="Directory containing NornFlow workflows")
    parser.add_argument("--workflow", type=Path, help="Single workflow file to register")
    parser.add_argument("--create-config", type=Path, help="Create sample configuration file")
    parser.add_argument("--validate", action="store_true", help="Validate environment setup")
    parser.add_argument("--docs", action="store_true", help="Generate setup documentation only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    try:
        # Create sample configuration
        if args.create_config:
            setup_manager = NetPickerSetupManager()
            result = setup_manager.create_sample_config(args.create_config)
            print(json.dumps(result, indent=2))
            return
        
        # Initialize setup manager
        setup_manager = NetPickerSetupManager(args.config)
        
        # Validate environment
        if args.validate:
            result = setup_manager.validate_environment()
            print(json.dumps(result, indent=2))
            if not result["valid"]:
                sys.exit(1)
            return
        
        # Generate documentation only
        if args.docs:
            print(setup_manager.netpicker.generate_setup_documentation())
            return
        
        # Register single workflow
        if args.workflow:
            if not args.workflow.exists():
                logger.error(f"Workflow file not found: {args.workflow}")
                sys.exit(1)
            
            result = setup_manager.register_single_workflow(args.workflow)
            print(json.dumps(result, indent=2))
            return
        
        # Register all workflows
        if args.workflows_dir:
            if not args.workflows_dir.exists():
                logger.error(f"Workflows directory not found: {args.workflows_dir}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would register workflows from {args.workflows_dir}")
                workflow_files = list(args.workflows_dir.glob("*.yaml")) + list(args.workflows_dir.glob("*.yml"))
                print(f"Found {len(workflow_files)} workflow files:")
                for wf in workflow_files:
                    print(f"  - {wf.name}")
            else:
                results = setup_manager.setup_complete_environment(args.workflows_dir)
                print(json.dumps(results, indent=2))
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
