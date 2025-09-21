#!/usr/bin/env python3
"""
API Testing Setup Utility for NornFlow.

This utility helps set up comprehensive API payload testing for NornFlow workflows:
- Creates test configuration files for templates and APIs
- Generates sample test scenarios and mock responses
- Sets up performance testing configurations
- Creates integration test suites
- Provides validation and troubleshooting tools

Usage:
    python api_testing_setup.py --create-config test_config.yaml
    python api_testing_setup.py --run-tests test_config.yaml
    python api_testing_setup.py --performance-test template.j2
    python api_testing_setup.py --validate-templates templates/
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from api_testing_framework import APIPayloadTestingFramework, TestScenario

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APITestingSetupManager:
    """Manages the setup and execution of API payload testing for NornFlow."""
    
    def __init__(self, config_file: Path = None):
        """Initialize setup manager with configuration."""
        self.config = self._load_config(config_file)
        self.framework = APIPayloadTestingFramework(self.config.get("framework", {}))
        
    def _load_config(self, config_file: Path = None) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        
        # Return default configuration
        return {
            "framework": {
                "templates_dir": "templates",
                "schemas_dir": "schemas",
                "test_results_dir": "test_results"
            },
            "mock_server": {
                "port": 8888,
                "responses": {
                    "GET:/api/devices": {
                        "response": {
                            "devices": [
                                {"id": 1, "name": "router-01", "type": "router"},
                                {"id": 2, "name": "switch-01", "type": "switch"}
                            ]
                        },
                        "status_code": 200
                    },
                    "POST:/api/config": {
                        "response": {
                            "status": "success",
                            "message": "Configuration applied successfully",
                            "job_id": "12345"
                        },
                        "status_code": 201
                    }
                }
            }
        }
    
    def create_sample_test_config(self, output_file: Path) -> Dict[str, Any]:
        """Create a comprehensive sample test configuration file."""
        sample_config = {
            "framework": {
                "templates_dir": "templates",
                "schemas_dir": "schemas", 
                "test_results_dir": "test_results"
            },
            "template_tests": [
                {
                    "template": "device_config.j2",
                    "scenarios": [
                        {
                            "name": "router_config",
                            "description": "Test router configuration template",
                            "variables": {
                                "device_name": "router-01",
                                "device_type": "router",
                                "interfaces": [
                                    {"name": "GigabitEthernet0/0", "ip": "192.168.1.1", "mask": "255.255.255.0"},
                                    {"name": "GigabitEthernet0/1", "ip": "10.0.0.1", "mask": "255.255.255.0"}
                                ],
                                "routing_protocol": "ospf",
                                "ospf_area": "0.0.0.0"
                            },
                            "expected_output": {
                                "required_fields": ["hostname", "interfaces", "router"],
                                "field_types": {
                                    "hostname": "str",
                                    "interfaces": "list"
                                },
                                "contains": ["hostname router-01", "interface GigabitEthernet0/0"]
                            },
                            "expected_status": 200,
                            "timeout": 5.0,
                            "validate_schema": True
                        },
                        {
                            "name": "switch_config", 
                            "description": "Test switch configuration template",
                            "variables": {
                                "device_name": "switch-01",
                                "device_type": "switch",
                                "vlans": [
                                    {"id": 10, "name": "management"},
                                    {"id": 20, "name": "users"},
                                    {"id": 30, "name": "servers"}
                                ],
                                "trunk_ports": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"]
                            },
                            "expected_output": {
                                "required_fields": ["hostname", "vlans"],
                                "contains": ["hostname switch-01", "vlan 10"]
                            },
                            "expected_status": 200,
                            "timeout": 5.0,
                            "validate_schema": True
                        }
                    ],
                    "performance_test": {
                        "enabled": True,
                        "iterations": 100
                    }
                },
                {
                    "template": "api_payload.j2",
                    "scenarios": [
                        {
                            "name": "netbox_device_creation",
                            "description": "Test NetBox device creation payload",
                            "variables": {
                                "device_name": "test-device-01",
                                "device_type": "cisco-2960",
                                "site": "datacenter-01",
                                "rack": "rack-01",
                                "position": 1,
                                "serial": "ABC123456789"
                            },
                            "expected_output": {
                                "required_fields": ["name", "device_type", "site"],
                                "field_types": {
                                    "name": "str",
                                    "position": "int"
                                }
                            },
                            "expected_status": 201,
                            "timeout": 10.0,
                            "validate_schema": True
                        }
                    ]
                }
            ],
            "api_tests": [
                {
                    "base_url": "http://localhost:8888",
                    "endpoints": [
                        {
                            "path": "/api/devices",
                            "method": "GET",
                            "headers": {
                                "Authorization": "Token {{ api_token }}",
                                "Content-Type": "application/json"
                            },
                            "response_schema": {
                                "type": "object",
                                "properties": {
                                    "devices": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {"type": "string"},
                                                "type": {"type": "string"}
                                            },
                                            "required": ["id", "name", "type"]
                                        }
                                    }
                                },
                                "required": ["devices"]
                            }
                        },
                        {
                            "path": "/api/config",
                            "method": "POST",
                            "headers": {
                                "Authorization": "Token {{ api_token }}",
                                "Content-Type": "application/json"
                            },
                            "payload_template": "{{ config_payload | tojson }}",
                            "response_schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string"},
                                    "message": {"type": "string"},
                                    "job_id": {"type": "string"}
                                },
                                "required": ["status", "job_id"]
                            }
                        }
                    ],
                    "scenarios": [
                        {
                            "name": "device_list_test",
                            "description": "Test device listing API",
                            "variables": {
                                "api_token": "test-token-123"
                            },
                            "expected_status": 200,
                            "timeout": 5.0,
                            "validate_schema": True
                        },
                        {
                            "name": "config_push_test",
                            "description": "Test configuration push API",
                            "variables": {
                                "api_token": "test-token-123",
                                "config_payload": {
                                    "device_id": "router-01",
                                    "config_lines": [
                                        "interface GigabitEthernet0/0",
                                        "ip address 192.168.1.1 255.255.255.0",
                                        "no shutdown"
                                    ]
                                }
                            },
                            "expected_status": 201,
                            "timeout": 10.0,
                            "validate_schema": True
                        }
                    ]
                }
            ],
            "integration_tests": [
                {
                    "name": "end_to_end_config_push",
                    "description": "End-to-end test: render template and push via API",
                    "template": "device_config.j2",
                    "variables": {
                        "device_name": "test-router",
                        "device_type": "router",
                        "interfaces": [
                            {"name": "GigabitEthernet0/0", "ip": "192.168.1.1", "mask": "255.255.255.0"}
                        ]
                    },
                    "api_request": {
                        "url": "http://localhost:8888/api/config",
                        "method": "POST",
                        "headers": {
                            "Authorization": "Token test-token-123",
                            "Content-Type": "application/json"
                        }
                    },
                    "expected_status": 201,
                    "timeout": 15.0,
                    "response_validation": {
                        "required_fields": ["status", "job_id"],
                        "field_values": {
                            "status": "success"
                        }
                    }
                }
            ],
            "mock_server": {
                "port": 8888,
                "responses": {
                    "GET:/api/devices": {
                        "response": {
                            "devices": [
                                {"id": 1, "name": "router-01", "type": "router"},
                                {"id": 2, "name": "switch-01", "type": "switch"}
                            ]
                        },
                        "status_code": 200
                    },
                    "POST:/api/config": {
                        "response": {
                            "status": "success",
                            "message": "Configuration applied successfully",
                            "job_id": "test-job-12345"
                        },
                        "status_code": 201
                    }
                }
            },
            "performance_testing": {
                "enabled": True,
                "default_iterations": 100,
                "templates": [
                    {
                        "template": "device_config.j2",
                        "scenario": "router_config",
                        "iterations": 500
                    }
                ]
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                yaml.dump(sample_config, f, default_flow_style=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Sample test configuration created: {output_file}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create sample config: {str(e)}"
            }
    
    def run_comprehensive_tests(self, test_config_file: Path) -> Dict[str, Any]:
        """Run comprehensive API payload tests from configuration file."""
        logger.info(f"Running comprehensive API tests from: {test_config_file}")
        
        try:
            with open(test_config_file, 'r') as f:
                test_config = yaml.safe_load(f)
            
            # Run batch template tests
            template_results = self.framework.run_batch_template_tests(test_config_file)
            
            # Run integration tests if configured
            integration_results = None
            if "integration_tests" in test_config or "api_tests" in test_config:
                integration_config = {
                    "use_mock_server": True,
                    "mock_responses": test_config.get("mock_server", {}).get("responses", {}),
                    "mock_port": test_config.get("mock_server", {}).get("port", 8888),
                    "template_tests": test_config.get("template_tests", []),
                    "api_tests": test_config.get("api_tests", []),
                    "integration_tests": test_config.get("integration_tests", [])
                }
                
                integration_results = self.framework.run_integration_tests(integration_config)
            
            # Combine results
            combined_results = {
                "template_test_results": template_results,
                "integration_test_results": integration_results
            }
            
            # Generate comprehensive report
            report_file = Path(self.framework.test_results_dir) / f"comprehensive_test_report_{test_config_file.stem}.md"
            report_content = self.framework.generate_test_report(
                integration_results if integration_results else template_results,
                report_file
            )
            
            logger.info("Comprehensive testing completed successfully")
            
            return {
                "success": True,
                "results": combined_results,
                "report_file": str(report_file),
                "message": "Comprehensive API testing completed"
            }
        
        except Exception as e:
            logger.error(f"Comprehensive testing failed: {str(e)}")
            return {
                "success": False,
                "message": f"Testing failed: {str(e)}"
            }
    
    def validate_templates(self, templates_dir: Path) -> Dict[str, Any]:
        """Validate all Jinja2 templates in a directory."""
        logger.info(f"Validating templates in: {templates_dir}")
        
        if not templates_dir.exists():
            return {
                "success": False,
                "message": f"Templates directory not found: {templates_dir}"
            }
        
        # Find template files
        template_files = list(templates_dir.glob("*.j2")) + list(templates_dir.glob("*.jinja2"))
        
        if not template_files:
            return {
                "success": False,
                "message": f"No template files found in: {templates_dir}"
            }
        
        validation_results = []
        
        for template_file in template_files:
            logger.info(f"Validating template: {template_file.name}")
            
            try:
                # Basic syntax validation
                with open(template_file, 'r') as f:
                    template_content = f.read()
                
                from jinja2 import Template, TemplateSyntaxError
                Template(template_content)
                
                validation_results.append({
                    "template": template_file.name,
                    "valid": True,
                    "message": "Template syntax is valid"
                })
                
                logger.info(f"✅ {template_file.name} is valid")
            
            except TemplateSyntaxError as e:
                validation_results.append({
                    "template": template_file.name,
                    "valid": False,
                    "error": f"Syntax error: {str(e)}"
                })
                
                logger.error(f"❌ {template_file.name} has syntax error: {str(e)}")
            
            except Exception as e:
                validation_results.append({
                    "template": template_file.name,
                    "valid": False,
                    "error": f"Validation error: {str(e)}"
                })
                
                logger.error(f"❌ {template_file.name} validation failed: {str(e)}")
        
        valid_templates = sum(1 for r in validation_results if r["valid"])
        
        return {
            "success": valid_templates > 0,
            "total_templates": len(template_files),
            "valid_templates": valid_templates,
            "invalid_templates": len(template_files) - valid_templates,
            "validation_results": validation_results,
            "message": f"Validated {valid_templates}/{len(template_files)} templates successfully"
        }
    
    def run_performance_test(self, template_file: Path, iterations: int = 100) -> Dict[str, Any]:
        """Run performance test for a single template."""
        logger.info(f"Running performance test for: {template_file}")
        
        if not template_file.exists():
            return {
                "success": False,
                "message": f"Template file not found: {template_file}"
            }
        
        # Create a basic test scenario
        test_scenario = TestScenario(
            name="performance_test",
            description="Performance testing scenario",
            variables={
                "device_name": "test-device",
                "device_type": "router",
                "interfaces": [{"name": "GigE0/0", "ip": "192.168.1.1"}],
                "vlans": [{"id": 10, "name": "management"}],
                "test_value": "performance_test_value"
            }
        )
        
        results = self.framework.run_performance_tests(template_file, test_scenario, iterations)
        
        if results.get("success", True):  # Performance tests don't have explicit success field
            logger.info(f"Performance test completed for {template_file.name}")
        else:
            logger.error(f"Performance test failed for {template_file.name}")
        
        return results


def main():
    """Main entry point for API testing setup utility."""
    parser = argparse.ArgumentParser(description="Set up and run API payload testing for NornFlow")
    parser.add_argument("--create-config", type=Path, help="Create sample test configuration file")
    parser.add_argument("--run-tests", type=Path, help="Run comprehensive tests from configuration file")
    parser.add_argument("--validate-templates", type=Path, help="Validate all templates in directory")
    parser.add_argument("--performance-test", type=Path, help="Run performance test for single template")
    parser.add_argument("--iterations", type=int, default=100, help="Number of iterations for performance test")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup_manager = APITestingSetupManager(args.config)
        
        # Create sample configuration
        if args.create_config:
            result = setup_manager.create_sample_test_config(args.create_config)
            print(json.dumps(result, indent=2))
            return
        
        # Validate templates
        if args.validate_templates:
            if not args.validate_templates.exists():
                logger.error(f"Templates directory not found: {args.validate_templates}")
                sys.exit(1)
            
            result = setup_manager.validate_templates(args.validate_templates)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Run performance test
        if args.performance_test:
            if not args.performance_test.exists():
                logger.error(f"Template file not found: {args.performance_test}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would run performance test on {args.performance_test} with {args.iterations} iterations")
            else:
                result = setup_manager.run_performance_test(args.performance_test, args.iterations)
                print(json.dumps(result, indent=2, default=str))
            return
        
        # Run comprehensive tests
        if args.run_tests:
            if not args.run_tests.exists():
                logger.error(f"Test configuration file not found: {args.run_tests}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would run comprehensive tests from {args.run_tests}")
            else:
                result = setup_manager.run_comprehensive_tests(args.run_tests)
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
