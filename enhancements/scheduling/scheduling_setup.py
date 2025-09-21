#!/usr/bin/env python3
"""
Scheduling System Setup Utility for NornFlow.

This utility provides comprehensive setup and configuration for the scheduling system:
- Scheduler configuration and initialization
- Orchestrator setup and resource management
- Event trigger configuration
- Integration testing and validation

Features:
- Automated scheduling system setup
- Configuration validation and testing
- Sample schedule creation
- Performance optimization
- Health checks and diagnostics

Usage:
    python scheduling_setup.py --setup-scheduler
    python scheduling_setup.py --setup-orchestrator
    python scheduling_setup.py --create-sample-schedules
    python scheduling_setup.py --test-scheduling
    python scheduling_setup.py --check-health
"""

import argparse
import json
import yaml
import sys
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from .scheduler import WorkflowScheduler, ScheduleDefinition, ScheduleType
from .orchestrator import WorkflowOrchestrator, ExecutionMode, ResourceRequirement

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulingSetup:
    """Scheduling system setup and configuration manager for NornFlow."""
    
    def __init__(self, config_file: Path = None):
        """Initialize scheduling setup manager."""
        self.config_file = config_file or Path("scheduling_config.yaml")
        self.config = self._load_or_create_config()
        
        # Default configuration
        self.default_config = {
            "scheduler": {
                "schedules_file": "schedules.json",
                "max_concurrent_executions": 10,
                "check_interval_seconds": 30,
                "enable_persistence": True
            },
            "orchestrator": {
                "max_concurrent_workflows": 5,
                "max_concurrent_tasks": 20,
                "default_timeout_minutes": 60,
                "enable_resource_management": True,
                "total_cpu_cores": 8.0,
                "total_memory_mb": 16384,
                "total_network_bandwidth_mbps": 1000.0,
                "total_storage_gb": 100.0,
                "custom_resources": {}
            },
            "event_triggers": {
                "enabled": True,
                "webhook_port": 8080,
                "file_watch_enabled": True,
                "api_polling_enabled": True
            },
            "integration": {
                "workflow_executor": "nornflow.core.executor",
                "notification_webhook": "",
                "metrics_endpoint": "",
                "log_level": "INFO"
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
        Create scheduling configuration file.
        
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
            
            logger.info(f"Scheduling configuration file created: {self.config_file}")
            
            return {
                "success": True,
                "config_file": str(self.config_file),
                "message": f"Scheduling configuration file created successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to create config file: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create config file: {str(e)}"
            }
    
    def setup_scheduler(self) -> Dict[str, Any]:
        """
        Setup workflow scheduler.
        
        Returns:
            Setup result
        """
        logger.info("Setting up workflow scheduler...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            scheduler_config = config.get("scheduler", {})
            
            # Initialize scheduler
            scheduler = WorkflowScheduler(scheduler_config)
            
            # Test scheduler functionality
            test_result = self._test_scheduler(scheduler)
            
            if not test_result["success"]:
                return test_result
            
            logger.info("Workflow scheduler setup completed successfully")
            
            return {
                "success": True,
                "message": "Workflow scheduler setup completed",
                "config": scheduler_config
            }
        
        except Exception as e:
            logger.error(f"Scheduler setup failed: {str(e)}")
            return {
                "success": False,
                "message": f"Scheduler setup failed: {str(e)}"
            }
    
    def setup_orchestrator(self) -> Dict[str, Any]:
        """
        Setup workflow orchestrator.
        
        Returns:
            Setup result
        """
        logger.info("Setting up workflow orchestrator...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            orchestrator_config = config.get("orchestrator", {})
            
            # Initialize orchestrator
            orchestrator = WorkflowOrchestrator(orchestrator_config)
            
            # Test orchestrator functionality
            test_result = self._test_orchestrator(orchestrator)
            
            if not test_result["success"]:
                return test_result
            
            logger.info("Workflow orchestrator setup completed successfully")
            
            return {
                "success": True,
                "message": "Workflow orchestrator setup completed",
                "config": orchestrator_config
            }
        
        except Exception as e:
            logger.error(f"Orchestrator setup failed: {str(e)}")
            return {
                "success": False,
                "message": f"Orchestrator setup failed: {str(e)}"
            }
    
    def create_sample_schedules(self) -> Dict[str, Any]:
        """
        Create sample schedules for testing.
        
        Returns:
            Creation result
        """
        logger.info("Creating sample schedules...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            scheduler_config = config.get("scheduler", {})
            
            # Initialize scheduler
            scheduler = WorkflowScheduler(scheduler_config)
            
            # Create sample schedules
            sample_schedules = [
                ScheduleDefinition(
                    id=str(uuid.uuid4()),
                    name="Daily Network Health Check",
                    workflow_file="workflows/health_check.yaml",
                    schedule_type=ScheduleType.CRON,
                    schedule_expression="0 8 * * *",  # Daily at 8 AM
                    timezone="UTC",
                    variables={
                        "check_type": "comprehensive",
                        "notification_email": "admin@example.com"
                    },
                    tags={
                        "category": "monitoring",
                        "priority": "high"
                    }
                ),
                ScheduleDefinition(
                    id=str(uuid.uuid4()),
                    name="Hourly Interface Monitoring",
                    workflow_file="workflows/interface_monitoring.yaml",
                    schedule_type=ScheduleType.CRON,
                    schedule_expression="0 * * * *",  # Every hour
                    timezone="UTC",
                    variables={
                        "interfaces": ["GigabitEthernet0/1", "GigabitEthernet0/2"],
                        "threshold_utilization": 80
                    },
                    tags={
                        "category": "monitoring",
                        "priority": "medium"
                    }
                ),
                ScheduleDefinition(
                    id=str(uuid.uuid4()),
                    name="Weekly Configuration Backup",
                    workflow_file="workflows/config_backup.yaml",
                    schedule_type=ScheduleType.CRON,
                    schedule_expression="0 2 * * 0",  # Weekly on Sunday at 2 AM
                    timezone="UTC",
                    variables={
                        "backup_location": "/backups/weekly",
                        "retention_days": 30
                    },
                    tags={
                        "category": "backup",
                        "priority": "high"
                    }
                ),
                ScheduleDefinition(
                    id=str(uuid.uuid4()),
                    name="Monthly Security Audit",
                    workflow_file="workflows/security_audit.yaml",
                    schedule_type=ScheduleType.CRON,
                    schedule_expression="0 3 1 * *",  # Monthly on 1st at 3 AM
                    timezone="UTC",
                    variables={
                        "audit_type": "comprehensive",
                        "report_format": "pdf"
                    },
                    tags={
                        "category": "security",
                        "priority": "high"
                    }
                )
            ]
            
            # Add schedules to scheduler
            created_schedules = []
            for schedule in sample_schedules:
                result = scheduler.add_schedule(schedule)
                if result["success"]:
                    created_schedules.append(schedule.name)
                else:
                    logger.warning(f"Failed to create schedule {schedule.name}: {result['message']}")
            
            logger.info(f"Created {len(created_schedules)} sample schedules")
            
            return {
                "success": True,
                "message": f"Created {len(created_schedules)} sample schedules",
                "schedules": created_schedules
            }
        
        except Exception as e:
            logger.error(f"Failed to create sample schedules: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create sample schedules: {str(e)}"
            }
    
    async def test_scheduling_system(self) -> Dict[str, Any]:
        """
        Test the complete scheduling system.
        
        Returns:
            Test results
        """
        logger.info("Testing scheduling system...")
        
        try:
            # Load configuration
            config = {**self.default_config, **self.config}
            
            # Test scheduler
            scheduler_config = config.get("scheduler", {})
            scheduler = WorkflowScheduler(scheduler_config)
            
            scheduler_test = self._test_scheduler(scheduler)
            if not scheduler_test["success"]:
                return scheduler_test
            
            # Test orchestrator
            orchestrator_config = config.get("orchestrator", {})
            orchestrator = WorkflowOrchestrator(orchestrator_config)
            
            orchestrator_test = self._test_orchestrator(orchestrator)
            if not orchestrator_test["success"]:
                return orchestrator_test
            
            # Test integration
            integration_test = await self._test_integration(scheduler, orchestrator)
            if not integration_test["success"]:
                return integration_test
            
            logger.info("Scheduling system test completed successfully")
            
            return {
                "success": True,
                "message": "Scheduling system test completed successfully",
                "test_results": {
                    "scheduler": scheduler_test,
                    "orchestrator": orchestrator_test,
                    "integration": integration_test
                }
            }
        
        except Exception as e:
            logger.error(f"Scheduling system test failed: {str(e)}")
            return {
                "success": False,
                "message": f"Scheduling system test failed: {str(e)}"
            }
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive system health check.
        
        Returns:
            Health check results
        """
        logger.info("Performing scheduling system health check...")
        
        checks = {
            "config": self._check_config_health(),
            "dependencies": self._check_dependencies(),
            "resources": self._check_resource_availability(),
            "storage": self._check_storage_health()
        }
        
        # Overall health
        overall_healthy = all(check["healthy"] for check in checks.values())
        
        return {
            "healthy": overall_healthy,
            "checks": checks,
            "message": "Scheduling system healthy" if overall_healthy else "Scheduling system issues detected"
        }
    
    def _test_scheduler(self, scheduler: WorkflowScheduler) -> Dict[str, Any]:
        """Test scheduler functionality."""
        try:
            # Test schedule creation
            test_schedule = ScheduleDefinition(
                id="test-schedule",
                name="Test Schedule",
                workflow_file="test_workflow.yaml",
                schedule_type=ScheduleType.INTERVAL,
                schedule_expression="60"  # Every 60 minutes
            )
            
            # Create test workflow file
            test_workflow_path = Path("test_workflow.yaml")
            test_workflow_path.write_text("""
name: Test Workflow
tasks:
  - name: test_task
    action: debug
    message: "Test task executed"
""")
            
            try:
                result = scheduler.add_schedule(test_schedule)
                if not result["success"]:
                    return {
                        "success": False,
                        "message": f"Failed to add test schedule: {result['message']}"
                    }
                
                # Test schedule removal
                remove_result = scheduler.remove_schedule("test-schedule")
                if not remove_result["success"]:
                    return {
                        "success": False,
                        "message": f"Failed to remove test schedule: {remove_result['message']}"
                    }
                
                return {
                    "success": True,
                    "message": "Scheduler test passed"
                }
            
            finally:
                # Clean up test file
                if test_workflow_path.exists():
                    test_workflow_path.unlink()
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Scheduler test failed: {str(e)}"
            }
    
    def _test_orchestrator(self, orchestrator: WorkflowOrchestrator) -> Dict[str, Any]:
        """Test orchestrator functionality."""
        try:
            # Test orchestrator status
            status = orchestrator.get_orchestrator_status()
            
            if not isinstance(status, dict):
                return {
                    "success": False,
                    "message": "Invalid orchestrator status response"
                }
            
            # Test resource management
            test_requirements = ResourceRequirement(
                cpu_cores=1.0,
                memory_mb=512
            )
            
            available = orchestrator._check_resource_availability(
                type('TestExecution', (), {'resource_requirements': test_requirements})()
            )
            
            if not available:
                return {
                    "success": False,
                    "message": "Resource availability check failed"
                }
            
            return {
                "success": True,
                "message": "Orchestrator test passed"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Orchestrator test failed: {str(e)}"
            }
    
    async def _test_integration(self, scheduler: WorkflowScheduler, orchestrator: WorkflowOrchestrator) -> Dict[str, Any]:
        """Test scheduler-orchestrator integration."""
        try:
            # Start orchestrator
            start_result = await orchestrator.start_orchestrator()
            if not start_result["success"]:
                return {
                    "success": False,
                    "message": f"Failed to start orchestrator: {start_result['message']}"
                }
            
            try:
                # Test workflow submission
                execution_id = await orchestrator.submit_workflow(
                    workflow_file="test_workflow.yaml",
                    variables={"test": True},
                    execution_mode=ExecutionMode.SEQUENTIAL
                )
                
                if not execution_id:
                    return {
                        "success": False,
                        "message": "Failed to submit test workflow"
                    }
                
                # Wait a moment and check status
                await asyncio.sleep(1)
                
                execution = await orchestrator.get_execution_status(execution_id)
                if not execution:
                    return {
                        "success": False,
                        "message": "Failed to get execution status"
                    }
                
                # Cancel the test execution
                cancel_result = await orchestrator.cancel_execution(execution_id)
                if not cancel_result["success"]:
                    logger.warning(f"Failed to cancel test execution: {cancel_result['message']}")
                
                return {
                    "success": True,
                    "message": "Integration test passed"
                }
            
            finally:
                # Stop orchestrator
                stop_result = await orchestrator.stop_orchestrator()
                if not stop_result["success"]:
                    logger.warning(f"Failed to stop orchestrator: {stop_result['message']}")
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Integration test failed: {str(e)}"
            }
    
    def _check_config_health(self) -> Dict[str, Any]:
        """Check configuration health."""
        try:
            if not self.config_file.exists():
                return {
                    "healthy": False,
                    "message": "Configuration file not found"
                }
            
            # Validate configuration structure
            config = {**self.default_config, **self.config}
            
            required_sections = ["scheduler", "orchestrator"]
            for section in required_sections:
                if section not in config:
                    return {
                        "healthy": False,
                        "message": f"Missing configuration section: {section}"
                    }
            
            return {
                "healthy": True,
                "message": "Configuration health OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Configuration health check failed: {str(e)}"
            }
    
    def _check_dependencies(self) -> Dict[str, Any]:
        """Check system dependencies."""
        try:
            # Check Python version
            import sys
            if sys.version_info < (3, 7):
                return {
                    "healthy": False,
                    "message": "Python 3.7+ required"
                }
            
            # Check optional dependencies
            optional_deps = {
                "croniter": "Advanced cron parsing",
                "pytz": "Timezone support"
            }
            
            missing_deps = []
            for dep, description in optional_deps.items():
                try:
                    __import__(dep)
                except ImportError:
                    missing_deps.append(f"{dep} ({description})")
            
            if missing_deps:
                return {
                    "healthy": False,
                    "message": f"Missing optional dependencies: {', '.join(missing_deps)}"
                }
            
            return {
                "healthy": True,
                "message": "Dependencies OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Dependency check failed: {str(e)}"
            }
    
    def _check_resource_availability(self) -> Dict[str, Any]:
        """Check system resource availability."""
        try:
            import psutil
            
            # Check CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                return {
                    "healthy": False,
                    "message": f"High CPU usage: {cpu_percent}%"
                }
            
            # Check memory
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return {
                    "healthy": False,
                    "message": f"High memory usage: {memory.percent}%"
                }
            
            # Check disk space
            disk = psutil.disk_usage('.')
            if disk.percent > 90:
                return {
                    "healthy": False,
                    "message": f"High disk usage: {disk.percent}%"
                }
            
            return {
                "healthy": True,
                "message": "Resource availability OK"
            }
        
        except ImportError:
            return {
                "healthy": True,
                "message": "Resource monitoring not available (psutil not installed)"
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Resource check failed: {str(e)}"
            }
    
    def _check_storage_health(self) -> Dict[str, Any]:
        """Check storage health."""
        try:
            # Check if we can write to the current directory
            test_file = Path("test_write.tmp")
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception:
                return {
                    "healthy": False,
                    "message": "Cannot write to current directory"
                }
            
            return {
                "healthy": True,
                "message": "Storage health OK"
            }
        
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Storage health check failed: {str(e)}"
            }


def main():
    """Main entry point for scheduling setup utility."""
    parser = argparse.ArgumentParser(description="Setup NornFlow scheduling system")
    parser.add_argument("--setup-scheduler", action="store_true", help="Setup workflow scheduler")
    parser.add_argument("--setup-orchestrator", action="store_true", help="Setup workflow orchestrator")
    parser.add_argument("--create-sample-schedules", action="store_true", help="Create sample schedules")
    parser.add_argument("--test-scheduling", action="store_true", help="Test scheduling system")
    parser.add_argument("--check-health", action="store_true", help="Perform system health check")
    parser.add_argument("--create-config", action="store_true", help="Create scheduling configuration file")
    parser.add_argument("--config", type=Path, help="Scheduling configuration file path")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup = SchedulingSetup(args.config)
        
        # Create configuration file
        if args.create_config:
            result = setup.create_config_file(args.force)
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Setup scheduler
        if args.setup_scheduler:
            result = setup.setup_scheduler()
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Setup orchestrator
        if args.setup_orchestrator:
            result = setup.setup_orchestrator()
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Create sample schedules
        if args.create_sample_schedules:
            result = setup.create_sample_schedules()
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # Test scheduling system
        if args.test_scheduling:
            result = asyncio.run(setup.test_scheduling_system())
            print(json.dumps(result, indent=2))
            if not result["success"]:
                sys.exit(1)
            return
        
        # System health check
        if args.check_health:
            result = setup.check_system_health()
            print(json.dumps(result, indent=2))
            if not result["healthy"]:
                sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Scheduling setup operation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
