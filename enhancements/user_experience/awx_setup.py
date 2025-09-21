#!/usr/bin/env python3
"""
AWX Setup Utility for NornFlow.

This utility helps set up Ansible AWX for running NornFlow workflows:
- Creates necessary AWX projects, inventories, and credentials
- Converts NornFlow workflows to AWX job templates
- Generates surveys for workflow variables
- Sets up NetBox inventory synchronization

Usage:
    python awx_setup.py --config awx_config.yaml
    python awx_setup.py --workflow workflows/network_config.yaml --awx-url https://awx.company.com
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from awx_integration import (
    AWXIntegration, 
    AWXCredential, 
    AWXJobTemplate, 
    AWXSurveyField
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AWXSetupManager:
    """Manages the complete AWX setup process for NornFlow."""
    
    def __init__(self, config_file: Path = None):
        """Initialize setup manager with configuration."""
        self.config = self._load_config(config_file)
        self.awx = AWXIntegration(self.config["awx"])
        
    def _load_config(self, config_file: Path = None) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Return default configuration
        return {
            "awx": {
                "url": "https://awx.company.com",
                "username": "admin",
                "password": "password",
                "organization": "Default",
                "verify_ssl": True
            },
            "git": {
                "repo_url": "https://github.com/company/nornflow-workflows.git",
                "branch": "main"
            },
            "netbox": {
                "enabled": False,
                "url": "https://netbox.company.com",
                "token": "your-netbox-token"
            },
            "credentials": {
                "network_devices": {
                    "username": "admin",
                    "password": "device-password",
                    "enable_password": "enable-password"
                }
            }
        }
    
    def setup_complete_environment(self) -> Dict[str, Any]:
        """Set up complete AWX environment for NornFlow."""
        logger.info("Starting complete AWX environment setup for NornFlow")
        
        results = {
            "connection_test": None,
            "project": None,
            "inventory": None,
            "credentials": None,
            "workflows": []
        }
        
        # Test AWX connection
        logger.info("Testing AWX connection...")
        results["connection_test"] = self.awx.test_connection()
        if not results["connection_test"]["success"]:
            logger.error(f"AWX connection failed: {results['connection_test']['message']}")
            return results
        
        logger.info(f"Connected to AWX: {results['connection_test']['message']}")
        
        # Create NornFlow project
        logger.info("Creating NornFlow project...")
        results["project"] = self.awx.create_nornflow_project(
            self.config["git"]["repo_url"],
            self.config["git"]["branch"]
        )
        
        if not results["project"]["success"]:
            logger.error(f"Project creation failed: {results['project']['message']}")
            return results
        
        logger.info(f"Project created: {results['project']['message']}")
        
        # Create NornFlow inventory
        logger.info("Creating NornFlow inventory...")
        netbox_config = self.config.get("netbox") if self.config.get("netbox", {}).get("enabled") else None
        results["inventory"] = self.awx.create_nornflow_inventory(netbox_config)
        
        if not results["inventory"]["success"]:
            logger.error(f"Inventory creation failed: {results['inventory']['message']}")
            return results
        
        logger.info(f"Inventory created: {results['inventory']['message']}")
        
        # Create credentials
        logger.info("Creating credentials...")
        credentials = self._generate_credentials()
        results["credentials"] = self.awx.create_credentials(credentials)
        
        if not results["credentials"]["success"]:
            logger.warning(f"Some credentials failed: {results['credentials']['message']}")
        else:
            logger.info(f"Credentials created: {results['credentials']['message']}")
        
        # Convert workflows
        workflow_dir = Path("workflows")
        if workflow_dir.exists():
            logger.info("Converting NornFlow workflows to AWX job templates...")
            for workflow_file in workflow_dir.glob("*.yaml"):
                logger.info(f"Converting workflow: {workflow_file.name}")
                workflow_result = self.awx.convert_workflow_to_awx(
                    workflow_file, 
                    self.config["git"]["repo_url"]
                )
                results["workflows"].append({
                    "file": workflow_file.name,
                    "result": workflow_result
                })
                
                if workflow_result["success"]:
                    logger.info(f"Workflow '{workflow_file.name}' converted successfully")
                else:
                    logger.error(f"Workflow '{workflow_file.name}' conversion failed: {workflow_result['message']}")
        
        logger.info("AWX environment setup completed!")
        return results
    
    def _generate_credentials(self) -> List[AWXCredential]:
        """Generate AWX credentials from configuration."""
        credentials = []
        
        # Network device credentials
        if "network_devices" in self.config.get("credentials", {}):
            net_creds = self.config["credentials"]["network_devices"]
            credentials.append(AWXCredential(
                name="NornFlow Network Devices",
                credential_type="Machine",
                description="SSH credentials for network devices",
                inputs={
                    "username": net_creds.get("username", "admin"),
                    "password": net_creds.get("password", ""),
                    "become_password": net_creds.get("enable_password", "")
                }
            ))
        
        # NetBox credentials
        if self.config.get("netbox", {}).get("enabled"):
            netbox_config = self.config["netbox"]
            credentials.append(AWXCredential(
                name="NornFlow NetBox",
                credential_type="Custom",
                description="NetBox API credentials",
                inputs={
                    "url": netbox_config.get("url", ""),
                    "token": netbox_config.get("token", "")
                }
            ))
        
        # Integration credentials
        integrations = self.config.get("integrations", {})
        
        for integration_name, integration_config in integrations.items():
            if integration_config.get("enabled", False):
                if integration_name == "grafana":
                    credentials.append(AWXCredential(
                        name="NornFlow Grafana",
                        credential_type="Custom",
                        description="Grafana API credentials",
                        inputs={
                            "url": integration_config.get("url", ""),
                            "api_key": integration_config.get("api_key", "")
                        }
                    ))
                
                elif integration_name == "servicenow":
                    credentials.append(AWXCredential(
                        name="NornFlow ServiceNow",
                        credential_type="Custom",
                        description="ServiceNow API credentials",
                        inputs={
                            "instance_url": integration_config.get("instance_url", ""),
                            "username": integration_config.get("username", ""),
                            "password": integration_config.get("password", "")
                        }
                    ))
                
                elif integration_name == "jira":
                    credentials.append(AWXCredential(
                        name="NornFlow Jira",
                        credential_type="Custom",
                        description="Jira API credentials",
                        inputs={
                            "server_url": integration_config.get("server_url", ""),
                            "username": integration_config.get("username", ""),
                            "api_token": integration_config.get("api_token", "")
                        }
                    ))
        
        return credentials
    
    def convert_single_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """Convert a single workflow to AWX job template."""
        logger.info(f"Converting workflow: {workflow_file}")
        
        result = self.awx.convert_workflow_to_awx(
            workflow_file,
            self.config["git"]["repo_url"]
        )
        
        if result["success"]:
            logger.info(f"Workflow converted successfully: {result['message']}")
        else:
            logger.error(f"Workflow conversion failed: {result['message']}")
        
        return result
    
    def generate_setup_documentation(self) -> str:
        """Generate documentation for AWX setup."""
        doc = f"""
# AWX Setup for NornFlow

## Configuration Summary
- AWX URL: {self.config['awx']['url']}
- Organization: {self.config['awx']['organization']}
- Git Repository: {self.config['git']['repo_url']}
- Git Branch: {self.config['git']['branch']}

## Required AWX Components

### 1. Project: NornFlow Project
- SCM Type: Git
- SCM URL: {self.config['git']['repo_url']}
- SCM Branch: {self.config['git']['branch']}
- Update on Launch: Yes

### 2. Inventory: NornFlow Inventory
- Type: Standard Inventory
- Variables: nornflow_managed: true
"""
        
        if self.config.get("netbox", {}).get("enabled"):
            doc += f"""
- NetBox Inventory Source:
  - URL: {self.config['netbox']['url']}
  - Token: [CONFIGURED]
  - Update on Launch: Yes
"""
        
        doc += """
### 3. Credentials
"""
        
        credentials = self._generate_credentials()
        for cred in credentials:
            doc += f"- {cred.name}: {cred.description}\n"
        
        doc += """
### 4. Job Templates
Job templates will be created for each NornFlow workflow with:
- Survey enabled for workflow variables
- Dry-run option
- Device limiting capability
- Verbosity control

## Usage
1. Run the setup utility to create all components
2. Access AWX web interface
3. Navigate to Templates
4. Launch NornFlow job templates with surveys
5. Monitor execution in AWX job output
"""
        
        return doc


def main():
    """Main entry point for AWX setup utility."""
    parser = argparse.ArgumentParser(description="Set up AWX for NornFlow workflows")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--workflow", type=Path, help="Single workflow file to convert")
    parser.add_argument("--awx-url", help="AWX URL")
    parser.add_argument("--awx-user", help="AWX username")
    parser.add_argument("--awx-pass", help="AWX password")
    parser.add_argument("--git-repo", help="Git repository URL")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--docs", action="store_true", help="Generate setup documentation")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup_manager = AWXSetupManager(args.config)
        
        # Override config with command line arguments
        if args.awx_url:
            setup_manager.config["awx"]["url"] = args.awx_url
        if args.awx_user:
            setup_manager.config["awx"]["username"] = args.awx_user
        if args.awx_pass:
            setup_manager.config["awx"]["password"] = args.awx_pass
        if args.git_repo:
            setup_manager.config["git"]["repo_url"] = args.git_repo
        
        # Generate documentation
        if args.docs:
            print(setup_manager.generate_setup_documentation())
            return
        
        # Convert single workflow
        if args.workflow:
            if not args.workflow.exists():
                logger.error(f"Workflow file not found: {args.workflow}")
                sys.exit(1)
            
            result = setup_manager.convert_single_workflow(args.workflow)
            print(json.dumps(result, indent=2))
            return
        
        # Full environment setup
        if args.dry_run:
            logger.info("DRY RUN: Would set up complete AWX environment")
            print(setup_manager.generate_setup_documentation())
        else:
            results = setup_manager.setup_complete_environment()
            print(json.dumps(results, indent=2))
    
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
