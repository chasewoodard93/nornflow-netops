#!/usr/bin/env python3
"""
ITSM Workflow Setup Utility for NornFlow.

This utility provides comprehensive ITSM workflow management:
- Advanced ServiceNow change management workflows
- Jira project management and automation
- Approval process automation
- Change Advisory Board (CAB) integration
- Risk assessment and compliance workflows
- Automated rollback procedures

Usage:
    python itsm_workflow_setup.py --create-change-request change_data.yaml
    python itsm_workflow_setup.py --create-automation-project project_data.yaml
    python itsm_workflow_setup.py --assess-risk change_data.yaml
    python itsm_workflow_setup.py --generate-report project_key
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from advanced_itsm_workflows import (
    AdvancedServiceNowIntegration, 
    AdvancedJiraIntegration,
    ChangeRisk,
    ChangeState,
    ApprovalState
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ITSMWorkflowManager:
    """Manages advanced ITSM workflows for NornFlow network automation."""
    
    def __init__(self, config_file: Path = None):
        """Initialize ITSM workflow manager."""
        self.config = self._load_config(config_file)
        
        # Initialize integrations
        servicenow_config = self.config.get("servicenow", {})
        jira_config = self.config.get("jira", {})
        
        self.servicenow = AdvancedServiceNowIntegration(servicenow_config) if servicenow_config else None
        self.jira = AdvancedJiraIntegration(jira_config) if jira_config else None
        
    def _load_config(self, config_file: Path = None) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Return default configuration
        return {
            "servicenow": {
                "url": "https://company.service-now.com",
                "username": "api-user",
                "password": "api-password",
                "emergency_approvers": [
                    {"name": "Network Manager", "sys_id": "manager-sys-id"},
                    {"name": "IT Director", "sys_id": "director-sys-id"}
                ]
            },
            "jira": {
                "url": "https://company.atlassian.net",
                "username": "api-user",
                "token": "api-token"
            },
            "workflows": {
                "standard_change_template": "network_config_change",
                "emergency_approval_timeout": 2,  # hours
                "cab_meeting_day": "tuesday",
                "cab_meeting_time": "14:00"
            }
        }
    
    def create_network_change_request(self, change_data_file: Path, change_type: str = "standard") -> Dict[str, Any]:
        """Create a network change request in ServiceNow."""
        logger.info(f"Creating {change_type} change request from: {change_data_file}")
        
        if not self.servicenow:
            return {
                "success": False,
                "message": "ServiceNow integration not configured"
            }
        
        if not change_data_file.exists():
            return {
                "success": False,
                "message": f"Change data file not found: {change_data_file}"
            }
        
        try:
            # Load change data
            with open(change_data_file, 'r') as f:
                change_data = yaml.safe_load(f)
            
            # Perform risk assessment first
            risk_assessment = self.servicenow.assess_change_risk(change_data)
            
            if not risk_assessment["success"]:
                return {
                    "success": False,
                    "message": f"Risk assessment failed: {risk_assessment['message']}"
                }
            
            risk_level = risk_assessment["assessment"]["risk_level"]
            logger.info(f"Risk assessment completed: {risk_level} risk")
            
            # Create appropriate change type based on risk and request
            if change_type == "emergency":
                justification = change_data.get("emergency_justification", "Network outage requiring immediate attention")
                result = self.servicenow.create_emergency_change(change_data, justification)
            elif change_type == "standard" and risk_level in ["low", "medium"]:
                template_name = self.config.get("workflows", {}).get("standard_change_template")
                result = self.servicenow.create_standard_change(change_data, template_name)
            else:
                # Normal change for high/critical risk
                result = self.servicenow.create_standard_change(change_data)
                
                # Submit to CAB if high risk
                if risk_level in ["high", "critical"] and result["success"]:
                    cab_result = self.servicenow.submit_to_cab(result["sys_id"])
                    result["cab_submission"] = cab_result
            
            # Add risk assessment to result
            result["risk_assessment"] = risk_assessment["assessment"]
            
            return result
        
        except Exception as e:
            logger.error(f"Change request creation failed: {str(e)}")
            return {
                "success": False,
                "message": f"Change request creation failed: {str(e)}"
            }
    
    def create_automation_project(self, project_data_file: Path) -> Dict[str, Any]:
        """Create a complete automation project in Jira."""
        logger.info(f"Creating automation project from: {project_data_file}")
        
        if not self.jira:
            return {
                "success": False,
                "message": "Jira integration not configured"
            }
        
        if not project_data_file.exists():
            return {
                "success": False,
                "message": f"Project data file not found: {project_data_file}"
            }
        
        try:
            # Load project data
            with open(project_data_file, 'r') as f:
                project_data = yaml.safe_load(f)
            
            results = {}
            
            # Step 1: Create Epic
            epic_data = project_data.get("epic", {})
            epic_result = self.jira.create_network_automation_epic(epic_data)
            results["epic_creation"] = epic_result
            
            if not epic_result["success"]:
                return {
                    "success": False,
                    "message": f"Epic creation failed: {epic_result['message']}",
                    "results": results
                }
            
            epic_key = epic_result["epic_key"]
            
            # Step 2: Create Stories
            stories_data = project_data.get("stories", [])
            if stories_data:
                stories_result = self.jira.create_automation_stories(epic_key, stories_data)
                results["stories_creation"] = stories_result
                
                # Step 3: Create Sprint if configured
                sprint_data = project_data.get("sprint")
                if sprint_data and stories_result["success"]:
                    board_id = project_data.get("board_id", "")
                    sprint_result = self.jira.create_sprint_for_automation(board_id, sprint_data)
                    results["sprint_creation"] = sprint_result
                    
                    # Add stories to sprint
                    if sprint_result["success"]:
                        story_keys = [story["story_key"] for story in stories_result["created_stories"]]
                        add_result = self.jira.add_issues_to_sprint(sprint_result["sprint_id"], story_keys)
                        results["sprint_population"] = add_result
            
            # Step 4: Create Workflow if configured
            workflow_data = project_data.get("workflow")
            if workflow_data:
                workflow_result = self.jira.create_automation_workflow(
                    project_data.get("project_key", ""), 
                    workflow_data
                )
                results["workflow_creation"] = workflow_result
            
            # Calculate overall success
            success = epic_result["success"]
            if stories_data:
                success = success and results.get("stories_creation", {}).get("success", False)
            
            return {
                "success": success,
                "epic_key": epic_key,
                "results": results,
                "message": f"Automation project created with epic {epic_key}"
            }
        
        except Exception as e:
            logger.error(f"Project creation failed: {str(e)}")
            return {
                "success": False,
                "message": f"Project creation failed: {str(e)}"
            }
    
    def assess_change_risk(self, change_data_file: Path) -> Dict[str, Any]:
        """Assess risk for a network change."""
        logger.info(f"Assessing change risk from: {change_data_file}")
        
        if not self.servicenow:
            return {
                "success": False,
                "message": "ServiceNow integration not configured"
            }
        
        if not change_data_file.exists():
            return {
                "success": False,
                "message": f"Change data file not found: {change_data_file}"
            }
        
        try:
            # Load change data
            with open(change_data_file, 'r') as f:
                change_data = yaml.safe_load(f)
            
            # Perform risk assessment
            result = self.servicenow.assess_change_risk(change_data)
            
            if result["success"]:
                assessment = result["assessment"]
                logger.info(f"Risk assessment: {assessment['risk_level']} (score: {assessment['risk_score']})")
                
                # Add recommendations
                if assessment["recommendations"]:
                    logger.info("Recommendations:")
                    for rec in assessment["recommendations"]:
                        logger.info(f"  - {rec}")
            
            return result
        
        except Exception as e:
            logger.error(f"Risk assessment failed: {str(e)}")
            return {
                "success": False,
                "message": f"Risk assessment failed: {str(e)}"
            }
    
    def generate_project_report(self, project_key: str, sprint_id: str = None) -> Dict[str, Any]:
        """Generate automation project report."""
        logger.info(f"Generating report for project: {project_key}")
        
        if not self.jira:
            return {
                "success": False,
                "message": "Jira integration not configured"
            }
        
        try:
            result = self.jira.generate_automation_report(project_key, sprint_id)
            
            if result["success"]:
                report = result["report"]
                logger.info(f"Report generated: {report['total_issues']} issues, {report['completion_rate']:.1f}% complete")
            
            return result
        
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            return {
                "success": False,
                "message": f"Report generation failed: {str(e)}"
            }
    
    def create_sample_change_data(self, output_file: Path) -> Dict[str, Any]:
        """Create sample change request data file."""
        sample_data = {
            "short_description": "Update network device configurations",
            "description": "Update OSPF configuration on core routers to optimize routing paths",
            "category": "Network",
            "subcategory": "Configuration",
            "requested_by": "network-engineer",
            "assigned_to": "network-team",
            "impact": "3",  # Low impact
            "urgency": "3",  # Low urgency
            "risk": "low",
            "affected_systems": ["production", "core_network"],
            "implementation_plan": """
1. Backup current configurations
2. Apply new OSPF configuration to Router-01
3. Verify routing table updates
4. Apply configuration to Router-02
5. Verify end-to-end connectivity
6. Monitor for 30 minutes
            """.strip(),
            "rollback_plan": """
1. Restore backup configurations if issues detected
2. Verify routing table restoration
3. Confirm connectivity restoration
4. Document any issues encountered
            """.strip(),
            "test_plan": """
1. Ping tests between all network segments
2. Traceroute verification for optimal paths
3. Performance monitoring for 30 minutes
4. Application connectivity verification
            """.strip(),
            "start_date": (datetime.now() + timedelta(days=7)).isoformat(),
            "end_date": (datetime.now() + timedelta(days=7, hours=2)).isoformat(),
            "custom_fields": {
                "u_automation_tool": "NornFlow",
                "u_change_type": "automated",
                "u_validation_required": "true"
            },
            "emergency_justification": "Critical network outage affecting all users"
        }
        
        try:
            with open(output_file, 'w') as f:
                yaml.dump(sample_data, f, default_flow_style=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Sample change data created: {output_file}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create sample data: {str(e)}"
            }
    
    def create_sample_project_data(self, output_file: Path) -> Dict[str, Any]:
        """Create sample project data file."""
        sample_data = {
            "project_key": "NETAUTO",
            "board_id": "123",
            "epic": {
                "project_key": "NETAUTO",
                "summary": "Network Automation Infrastructure",
                "description": "Implement comprehensive network automation using NornFlow",
                "epic_name": "Network Automation",
                "priority": "High",
                "assignee": "project-manager",
                "labels": ["network-automation", "infrastructure"],
                "components": ["Network", "Automation", "Infrastructure"]
            },
            "stories": [
                {
                    "project_key": "NETAUTO",
                    "summary": "Set up NornFlow automation framework",
                    "description": "Install and configure NornFlow for network device automation",
                    "priority": "High",
                    "assignee": "automation-engineer",
                    "story_points": 8,
                    "labels": ["setup", "framework"],
                    "acceptance_criteria": [
                        "NornFlow is installed and configured",
                        "Basic device connectivity is established",
                        "Sample workflows are tested"
                    ]
                },
                {
                    "project_key": "NETAUTO",
                    "summary": "Create device configuration templates",
                    "description": "Develop Jinja2 templates for common device configurations",
                    "priority": "Medium",
                    "assignee": "network-engineer",
                    "story_points": 5,
                    "labels": ["templates", "configuration"],
                    "acceptance_criteria": [
                        "Templates created for router configurations",
                        "Templates created for switch configurations",
                        "Templates are tested and validated"
                    ]
                },
                {
                    "project_key": "NETAUTO",
                    "summary": "Implement change management integration",
                    "description": "Integrate NornFlow with ServiceNow for change management",
                    "priority": "Medium",
                    "assignee": "integration-specialist",
                    "story_points": 13,
                    "labels": ["integration", "change-management"],
                    "acceptance_criteria": [
                        "ServiceNow integration is configured",
                        "Change requests are automatically created",
                        "Approval workflows are functional"
                    ]
                }
            ],
            "sprint": {
                "name": "Network Automation Sprint 1",
                "goal": "Establish basic automation framework and templates",
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now() + timedelta(weeks=2)).isoformat()
            },
            "workflow": {
                "name": "Network Automation Workflow",
                "statuses": [
                    "To Do", "In Analysis", "In Development", "Testing",
                    "Deployment Ready", "In Deployment", "Done"
                ],
                "transitions": [
                    {"from": "To Do", "to": "In Analysis", "name": "Start Analysis"},
                    {"from": "In Analysis", "to": "In Development", "name": "Start Development"},
                    {"from": "In Development", "to": "Testing", "name": "Ready for Testing"},
                    {"from": "Testing", "to": "Deployment Ready", "name": "Testing Complete"},
                    {"from": "Deployment Ready", "to": "In Deployment", "name": "Start Deployment"},
                    {"from": "In Deployment", "to": "Done", "name": "Deployment Complete"}
                ]
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                yaml.dump(sample_data, f, default_flow_style=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Sample project data created: {output_file}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create sample data: {str(e)}"
            }


def main():
    """Main entry point for ITSM workflow setup utility."""
    parser = argparse.ArgumentParser(description="Manage advanced ITSM workflows for NornFlow")
    parser.add_argument("--create-change", type=Path, help="Create change request from data file")
    parser.add_argument("--change-type", choices=["standard", "emergency"], default="standard", help="Type of change request")
    parser.add_argument("--create-project", type=Path, help="Create automation project from data file")
    parser.add_argument("--assess-risk", type=Path, help="Assess risk for change request")
    parser.add_argument("--generate-report", type=str, help="Generate project report (project key)")
    parser.add_argument("--sprint-id", type=str, help="Sprint ID for sprint-specific report")
    parser.add_argument("--create-sample-change", type=Path, help="Create sample change data file")
    parser.add_argument("--create-sample-project", type=Path, help="Create sample project data file")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    try:
        # Initialize workflow manager
        workflow_manager = ITSMWorkflowManager(args.config)
        
        # Create sample change data
        if args.create_sample_change:
            result = workflow_manager.create_sample_change_data(args.create_sample_change)
            print(json.dumps(result, indent=2))
            return
        
        # Create sample project data
        if args.create_sample_project:
            result = workflow_manager.create_sample_project_data(args.create_sample_project)
            print(json.dumps(result, indent=2))
            return
        
        # Create change request
        if args.create_change:
            if not args.create_change.exists():
                logger.error(f"Change data file not found: {args.create_change}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would create {args.change_type} change from {args.create_change}")
            else:
                result = workflow_manager.create_network_change_request(args.create_change, args.change_type)
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Create automation project
        if args.create_project:
            if not args.create_project.exists():
                logger.error(f"Project data file not found: {args.create_project}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would create automation project from {args.create_project}")
            else:
                result = workflow_manager.create_automation_project(args.create_project)
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Assess change risk
        if args.assess_risk:
            if not args.assess_risk.exists():
                logger.error(f"Change data file not found: {args.assess_risk}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would assess risk for {args.assess_risk}")
            else:
                result = workflow_manager.assess_change_risk(args.assess_risk)
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Generate project report
        if args.generate_report:
            if args.dry_run:
                logger.info(f"DRY RUN: Would generate report for project {args.generate_report}")
                if args.sprint_id:
                    logger.info(f"DRY RUN: Would include sprint {args.sprint_id}")
            else:
                result = workflow_manager.generate_project_report(args.generate_report, args.sprint_id)
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"ITSM workflow operation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
