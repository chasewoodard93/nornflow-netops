#!/usr/bin/env python3
"""
Postman Setup Utility for NornFlow API Testing.

This utility helps set up Postman for testing NornFlow API workflows:
- Generates Postman collections from NornFlow workflows
- Creates environment files for different network setups
- Exports collections and environments for team collaboration
- Creates template testing collections for Jinja2 validation

Usage:
    python postman_setup.py --workflows-dir workflows/
    python postman_setup.py --config postman_config.yaml
    python postman_setup.py --workflow workflows/api_workflow.yaml
    python postman_setup.py --templates-dir templates/
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from postman_integration import PostmanIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PostmanSetupManager:
    """Manages the complete Postman setup process for NornFlow API testing."""
    
    def __init__(self, config_file: Path = None):
        """Initialize setup manager with configuration."""
        self.config = self._load_config(config_file)
        self.postman = PostmanIntegration(self.config.get("postman", {}))
        
    def _load_config(self, config_file: Path = None) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Return default configuration
        return {
            "postman": {
                "collections_dir": "postman_collections",
                "environments_dir": "postman_environments"
            },
            "environments": {
                "development": {
                    "netbox_url": "https://netbox-dev.company.com",
                    "netbox_token": "dev-netbox-token",
                    "grafana_url": "https://grafana-dev.company.com",
                    "grafana_api_key": "dev-grafana-key",
                    "servicenow_url": "https://dev.service-now.com",
                    "servicenow_user": "dev-user",
                    "servicenow_pass": "dev-password",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "dev-user",
                    "jira_token": "dev-token"
                },
                "staging": {
                    "netbox_url": "https://netbox-staging.company.com",
                    "netbox_token": "staging-netbox-token",
                    "grafana_url": "https://grafana-staging.company.com",
                    "grafana_api_key": "staging-grafana-key",
                    "servicenow_url": "https://staging.service-now.com",
                    "servicenow_user": "staging-user",
                    "servicenow_pass": "staging-password",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "staging-user",
                    "jira_token": "staging-token"
                },
                "production": {
                    "netbox_url": "https://netbox.company.com",
                    "netbox_token": "prod-netbox-token",
                    "grafana_url": "https://grafana.company.com",
                    "grafana_api_key": "prod-grafana-key",
                    "servicenow_url": "https://company.service-now.com",
                    "servicenow_user": "prod-user",
                    "servicenow_pass": "prod-password",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "prod-user",
                    "jira_token": "prod-token"
                }
            }
        }
    
    def setup_complete_environment(self, workflows_dir: Path, templates_dir: Path = None) -> Dict[str, Any]:
        """Set up complete Postman environment for NornFlow API testing."""
        logger.info("Starting complete Postman environment setup for NornFlow API testing")
        
        results = {
            "collections": None,
            "environments": None,
            "template_collection": None
        }
        
        # Generate collections from workflows
        logger.info(f"Generating collections from workflows in: {workflows_dir}")
        results["collections"] = self.postman.generate_collections_from_workflows(workflows_dir)
        
        if not results["collections"]["success"]:
            logger.error(f"Collection generation failed: {results['collections']['message']}")
        else:
            logger.info(f"Collections generated: {results['collections']['message']}")
        
        # Generate environments
        logger.info("Creating Postman environments...")
        env_results = []
        for env_name, env_vars in self.config["environments"].items():
            result = self.postman.generate_environment(env_name, env_vars)
            env_results.append({
                "environment": env_name,
                "result": result
            })
            
            if result["success"]:
                logger.info(f"Environment '{env_name}' created successfully")
            else:
                logger.error(f"Environment '{env_name}' creation failed: {result['message']}")
        
        successful_envs = sum(1 for r in env_results if r["result"]["success"])
        results["environments"] = {
            "success": successful_envs > 0,
            "total_environments": len(self.config["environments"]),
            "successful_generations": successful_envs,
            "results": env_results,
            "message": f"Generated {successful_envs}/{len(self.config['environments'])} environments successfully"
        }
        
        # Generate template testing collection if templates directory provided
        if templates_dir and templates_dir.exists():
            logger.info(f"Creating template testing collection from: {templates_dir}")
            results["template_collection"] = self.postman.create_template_testing_collection(templates_dir)
            
            if results["template_collection"]["success"]:
                logger.info(f"Template collection created: {results['template_collection']['message']}")
            else:
                logger.error(f"Template collection failed: {results['template_collection']['message']}")
        
        logger.info("Postman environment setup completed!")
        return results
    
    def generate_single_collection(self, workflow_file: Path) -> Dict[str, Any]:
        """Generate a single Postman collection from a workflow."""
        logger.info(f"Generating collection from workflow: {workflow_file}")
        
        result = self.postman.generate_collection_from_workflow(workflow_file)
        
        if result["success"]:
            logger.info(f"Collection generated successfully: {result['message']}")
        else:
            logger.error(f"Collection generation failed: {result['message']}")
        
        return result
    
    def create_sample_config(self, output_file: Path) -> Dict[str, Any]:
        """Create a sample configuration file."""
        sample_config = {
            "postman": {
                "collections_dir": "postman_collections",
                "environments_dir": "postman_environments"
            },
            "environments": {
                "development": {
                    "description": "Development environment for API testing",
                    "netbox_url": "https://netbox-dev.company.com",
                    "netbox_token": "${NETBOX_DEV_TOKEN}",
                    "netbox_host": "netbox-dev.company.com",
                    "grafana_url": "https://grafana-dev.company.com",
                    "grafana_api_key": "${GRAFANA_DEV_KEY}",
                    "grafana_host": "grafana-dev.company.com",
                    "servicenow_url": "https://dev.service-now.com",
                    "servicenow_user": "${SERVICENOW_DEV_USER}",
                    "servicenow_pass": "${SERVICENOW_DEV_PASS}",
                    "servicenow_host": "dev.service-now.com",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "${JIRA_DEV_USER}",
                    "jira_token": "${JIRA_DEV_TOKEN}",
                    "jira_host": "company.atlassian.net",
                    "template_test_endpoint": "https://api-dev.company.com/template/validate",
                    "template_test_host": "api-dev.company.com"
                },
                "staging": {
                    "description": "Staging environment for API testing",
                    "netbox_url": "https://netbox-staging.company.com",
                    "netbox_token": "${NETBOX_STAGING_TOKEN}",
                    "netbox_host": "netbox-staging.company.com",
                    "grafana_url": "https://grafana-staging.company.com",
                    "grafana_api_key": "${GRAFANA_STAGING_KEY}",
                    "grafana_host": "grafana-staging.company.com",
                    "servicenow_url": "https://staging.service-now.com",
                    "servicenow_user": "${SERVICENOW_STAGING_USER}",
                    "servicenow_pass": "${SERVICENOW_STAGING_PASS}",
                    "servicenow_host": "staging.service-now.com",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "${JIRA_STAGING_USER}",
                    "jira_token": "${JIRA_STAGING_TOKEN}",
                    "jira_host": "company.atlassian.net",
                    "template_test_endpoint": "https://api-staging.company.com/template/validate",
                    "template_test_host": "api-staging.company.com"
                },
                "production": {
                    "description": "Production environment for API testing",
                    "netbox_url": "https://netbox.company.com",
                    "netbox_token": "${NETBOX_PROD_TOKEN}",
                    "netbox_host": "netbox.company.com",
                    "grafana_url": "https://grafana.company.com",
                    "grafana_api_key": "${GRAFANA_PROD_KEY}",
                    "grafana_host": "grafana.company.com",
                    "servicenow_url": "https://company.service-now.com",
                    "servicenow_user": "${SERVICENOW_PROD_USER}",
                    "servicenow_pass": "${SERVICENOW_PROD_PASS}",
                    "servicenow_host": "company.service-now.com",
                    "jira_url": "https://company.atlassian.net",
                    "jira_user": "${JIRA_PROD_USER}",
                    "jira_token": "${JIRA_PROD_TOKEN}",
                    "jira_host": "company.atlassian.net",
                    "template_test_endpoint": "https://api.company.com/template/validate",
                    "template_test_host": "api.company.com"
                }
            },
            "collection_settings": {
                "include_test_scripts": True,
                "include_variable_extraction": True,
                "include_authentication": True,
                "timeout_ms": 5000
            },
            "template_testing": {
                "enabled": True,
                "validation_endpoint": "/template/validate",
                "include_variable_inspection": True
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
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate Postman setup and configuration."""
        issues = []
        
        # Check directories
        collections_dir = Path(self.postman.collections_dir)
        environments_dir = Path(self.postman.environments_dir)
        
        if not collections_dir.exists():
            issues.append(f"Collections directory does not exist: {collections_dir}")
        
        if not environments_dir.exists():
            issues.append(f"Environments directory does not exist: {environments_dir}")
        
        # Check environment configuration
        environments = self.config.get("environments", {})
        if not environments:
            issues.append("No environments configured")
        
        for env_name, env_vars in environments.items():
            required_vars = ["netbox_url", "grafana_url", "servicenow_url", "jira_url"]
            missing_vars = [var for var in required_vars if var not in env_vars]
            if missing_vars:
                issues.append(f"Environment '{env_name}' missing variables: {missing_vars}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "message": "Setup is valid" if len(issues) == 0 else f"Found {len(issues)} issues"
        }
    
    def generate_documentation(self) -> str:
        """Generate documentation for Postman setup."""
        doc = f"""
# Postman Setup for NornFlow API Testing

## Overview
This setup provides Postman collections and environments for testing NornFlow API workflows.

## Generated Collections
- **Workflow Collections**: One collection per NornFlow workflow containing API tasks
- **Template Testing Collection**: Specialized collection for testing Jinja2 templates

## Generated Environments
"""
        
        for env_name in self.config.get("environments", {}):
            doc += f"- **{env_name.title()}**: {env_name} environment variables\n"
        
        doc += f"""
## Directory Structure
- Collections: {self.postman.collections_dir}
- Environments: {self.postman.environments_dir}

## Usage Instructions

### 1. Import Collections
1. Open Postman
2. Click "Import" button
3. Select collection files from `{self.postman.collections_dir}`
4. Import all generated collections

### 2. Import Environments
1. In Postman, click the gear icon (Manage Environments)
2. Click "Import"
3. Select environment files from `{self.postman.environments_dir}`
4. Import all environments

### 3. Configure Variables
1. Select an environment (development/staging/production)
2. Update variable values with actual credentials and URLs
3. Save the environment

### 4. Run Tests
1. Select a collection
2. Choose the appropriate environment
3. Run individual requests or entire collections
4. Review test results and response data

## Security Notes
- Never commit actual credentials to version control
- Use environment variables for sensitive data
- Regularly rotate API tokens and passwords
- Use different credentials for each environment

## Troubleshooting
- Verify environment variables are set correctly
- Check API endpoint URLs and authentication
- Review Postman console for detailed error messages
- Validate JSON payloads and template syntax
"""
        
        return doc


def main():
    """Main entry point for Postman setup utility."""
    parser = argparse.ArgumentParser(description="Set up Postman for NornFlow API testing")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--workflows-dir", type=Path, help="Directory containing NornFlow workflows")
    parser.add_argument("--workflow", type=Path, help="Single workflow file to process")
    parser.add_argument("--templates-dir", type=Path, help="Directory containing Jinja2 templates")
    parser.add_argument("--create-config", type=Path, help="Create sample configuration file")
    parser.add_argument("--validate", action="store_true", help="Validate setup configuration")
    parser.add_argument("--docs", action="store_true", help="Generate setup documentation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    try:
        # Create sample configuration
        if args.create_config:
            setup_manager = PostmanSetupManager()
            result = setup_manager.create_sample_config(args.create_config)
            print(json.dumps(result, indent=2))
            return
        
        # Initialize setup manager
        setup_manager = PostmanSetupManager(args.config)
        
        # Validate setup
        if args.validate:
            result = setup_manager.validate_setup()
            print(json.dumps(result, indent=2))
            if not result["valid"]:
                sys.exit(1)
            return
        
        # Generate documentation
        if args.docs:
            print(setup_manager.generate_documentation())
            return
        
        # Process single workflow
        if args.workflow:
            if not args.workflow.exists():
                logger.error(f"Workflow file not found: {args.workflow}")
                sys.exit(1)
            
            result = setup_manager.generate_single_collection(args.workflow)
            print(json.dumps(result, indent=2))
            return
        
        # Full environment setup
        if args.workflows_dir:
            if not args.workflows_dir.exists():
                logger.error(f"Workflows directory not found: {args.workflows_dir}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would process workflows from {args.workflows_dir}")
                if args.templates_dir:
                    logger.info(f"DRY RUN: Would process templates from {args.templates_dir}")
                workflow_files = list(args.workflows_dir.glob("*.yaml")) + list(args.workflows_dir.glob("*.yml"))
                print(f"Found {len(workflow_files)} workflow files:")
                for wf in workflow_files:
                    print(f"  - {wf.name}")
            else:
                results = setup_manager.setup_complete_environment(args.workflows_dir, args.templates_dir)
                print(json.dumps(results, indent=2))
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
