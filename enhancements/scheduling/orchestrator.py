#!/usr/bin/env python3
"""
Advanced Workflow Orchestrator for NornFlow.

This module provides comprehensive workflow orchestration capabilities:
- Workflow chaining and dependencies
- Parallel execution optimization
- Resource management and allocation
- Failure handling and recovery
- Distributed execution support

Features:
- Dependency-based execution ordering
- Parallel task execution with resource limits
- Automatic retry and recovery mechanisms
- Resource allocation and conflict resolution
- Performance monitoring and optimization
"""

import asyncio
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Workflow execution mode."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_BASED = "dependency_based"
    RESOURCE_OPTIMIZED = "resource_optimized"


class ExecutionStatus(Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class WorkflowDependency:
    """Workflow dependency definition."""
    workflow_id: str
    dependency_id: str
    dependency_type: str = "success"  # success, completion, failure
    timeout_minutes: int = 60


@dataclass
class ResourceRequirement:
    """Resource requirement for workflow execution."""
    cpu_cores: float = 1.0
    memory_mb: int = 512
    network_bandwidth_mbps: float = 10.0
    storage_gb: float = 1.0
    custom_resources: Dict[str, float] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution context."""
    execution_id: str
    workflow_id: str
    workflow_file: str
    execution_mode: ExecutionMode
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[WorkflowDependency] = field(default_factory=list)
    resource_requirements: ResourceRequirement = field(default_factory=ResourceRequirement)
    retry_count: int = 0
    max_retries: int = 3
    timeout_minutes: int = 60
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    allocated_resources: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "workflow_file": self.workflow_file,
            "execution_mode": self.execution_mode.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "variables": self.variables,
            "dependencies": [
                {
                    "workflow_id": dep.workflow_id,
                    "dependency_id": dep.dependency_id,
                    "dependency_type": dep.dependency_type,
                    "timeout_minutes": dep.timeout_minutes
                }
                for dep in self.dependencies
            ],
            "resource_requirements": {
                "cpu_cores": self.resource_requirements.cpu_cores,
                "memory_mb": self.resource_requirements.memory_mb,
                "network_bandwidth_mbps": self.resource_requirements.network_bandwidth_mbps,
                "storage_gb": self.resource_requirements.storage_gb,
                "custom_resources": self.resource_requirements.custom_resources
            },
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_minutes": self.timeout_minutes,
            "result": self.result,
            "error_message": self.error_message,
            "allocated_resources": self.allocated_resources
        }


class WorkflowOrchestrator:
    """
    Advanced workflow orchestrator with comprehensive execution management.
    
    Features:
    - Multiple execution modes (sequential, parallel, dependency-based)
    - Resource management and allocation
    - Automatic retry and recovery
    - Performance monitoring and optimization
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize workflow orchestrator."""
        self.config = config or {}
        
        # Orchestrator configuration
        self.max_concurrent_workflows = self.config.get("max_concurrent_workflows", 5)
        self.max_concurrent_tasks = self.config.get("max_concurrent_tasks", 20)
        self.default_timeout_minutes = self.config.get("default_timeout_minutes", 60)
        self.enable_resource_management = self.config.get("enable_resource_management", True)
        
        # Execution state
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.pending_executions: List[WorkflowExecution] = []
        self.completed_executions: List[WorkflowExecution] = []
        self.execution_queue = asyncio.Queue()
        
        # Resource management
        self.total_resources = ResourceRequirement(
            cpu_cores=self.config.get("total_cpu_cores", 8.0),
            memory_mb=self.config.get("total_memory_mb", 16384),
            network_bandwidth_mbps=self.config.get("total_network_bandwidth_mbps", 1000.0),
            storage_gb=self.config.get("total_storage_gb", 100.0),
            custom_resources=self.config.get("custom_resources", {})
        )
        self.allocated_resources = ResourceRequirement()
        
        # Orchestrator state
        self.running = False
        self.orchestrator_task = None
        
        # Callbacks
        self.workflow_executor: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
    
    def set_workflow_executor(self, executor: Callable[[str, Dict[str, Any]], Any]):
        """Set workflow executor callback."""
        self.workflow_executor = executor
    
    def set_status_callback(self, callback: Callable[[WorkflowExecution], None]):
        """Set status update callback."""
        self.status_callback = callback
    
    async def submit_workflow(self, workflow_file: str, variables: Dict[str, Any] = None, 
                            execution_mode: ExecutionMode = ExecutionMode.DEPENDENCY_BASED,
                            dependencies: List[WorkflowDependency] = None,
                            resource_requirements: ResourceRequirement = None) -> str:
        """
        Submit workflow for execution.
        
        Args:
            workflow_file: Path to workflow file
            variables: Workflow variables
            execution_mode: Execution mode
            dependencies: Workflow dependencies
            resource_requirements: Resource requirements
            
        Returns:
            Execution ID
        """
        execution_id = str(uuid.uuid4())
        workflow_id = Path(workflow_file).stem
        
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_file=workflow_file,
            execution_mode=execution_mode,
            variables=variables or {},
            dependencies=dependencies or [],
            resource_requirements=resource_requirements or ResourceRequirement(),
            timeout_minutes=self.default_timeout_minutes
        )
        
        # Add to pending queue
        self.pending_executions.append(execution)
        await self.execution_queue.put(execution)
        
        logger.info(f"Submitted workflow for execution: {workflow_file} ({execution_id})")
        
        return execution_id
    
    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Cancel workflow execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Operation result
        """
        # Check active executions
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now()
            
            # Release resources
            self._release_resources(execution)
            
            # Move to completed
            self.completed_executions.append(execution)
            del self.active_executions[execution_id]
            
            logger.info(f"Cancelled execution: {execution_id}")
            
            return {
                "success": True,
                "message": f"Execution {execution_id} cancelled"
            }
        
        # Check pending executions
        for i, execution in enumerate(self.pending_executions):
            if execution.execution_id == execution_id:
                execution.status = ExecutionStatus.CANCELLED
                execution.completed_at = datetime.now()
                
                self.completed_executions.append(execution)
                del self.pending_executions[i]
                
                logger.info(f"Cancelled pending execution: {execution_id}")
                
                return {
                    "success": True,
                    "message": f"Pending execution {execution_id} cancelled"
                }
        
        return {
            "success": False,
            "message": f"Execution {execution_id} not found"
        }
    
    async def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution status."""
        # Check active executions
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]
        
        # Check pending executions
        for execution in self.pending_executions:
            if execution.execution_id == execution_id:
                return execution
        
        # Check completed executions
        for execution in self.completed_executions:
            if execution.execution_id == execution_id:
                return execution
        
        return None
    
    async def list_executions(self, status_filter: Optional[ExecutionStatus] = None) -> List[WorkflowExecution]:
        """List executions with optional status filter."""
        all_executions = (
            list(self.active_executions.values()) +
            self.pending_executions +
            self.completed_executions
        )
        
        if status_filter:
            return [exec for exec in all_executions if exec.status == status_filter]
        
        return all_executions
    
    async def start_orchestrator(self) -> Dict[str, Any]:
        """
        Start the orchestrator.
        
        Returns:
            Operation result
        """
        try:
            if self.running:
                return {
                    "success": False,
                    "message": "Orchestrator is already running"
                }
            
            self.running = True
            self.orchestrator_task = asyncio.create_task(self._orchestrator_loop())
            
            logger.info("Workflow orchestrator started")
            
            return {
                "success": True,
                "message": "Orchestrator started successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to start orchestrator: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to start orchestrator: {str(e)}"
            }
    
    async def stop_orchestrator(self) -> Dict[str, Any]:
        """
        Stop the orchestrator.
        
        Returns:
            Operation result
        """
        try:
            if not self.running:
                return {
                    "success": False,
                    "message": "Orchestrator is not running"
                }
            
            self.running = False
            
            if self.orchestrator_task:
                self.orchestrator_task.cancel()
                try:
                    await self.orchestrator_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Workflow orchestrator stopped")
            
            return {
                "success": True,
                "message": "Orchestrator stopped successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to stop orchestrator: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to stop orchestrator: {str(e)}"
            }
    
    async def _orchestrator_loop(self):
        """Main orchestrator loop."""
        logger.info("Orchestrator loop started")
        
        while self.running:
            try:
                # Process pending executions
                await self._process_pending_executions()
                
                # Check for completed executions
                await self._check_completed_executions()
                
                # Clean up old executions
                self._cleanup_executions()
                
                # Wait for next iteration
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Orchestrator loop error: {str(e)}")
                await asyncio.sleep(10)
        
        logger.info("Orchestrator loop stopped")
    
    async def _process_pending_executions(self):
        """Process pending executions."""
        ready_executions = []
        
        # Find executions ready to run
        for execution in self.pending_executions[:]:
            if len(self.active_executions) >= self.max_concurrent_workflows:
                break
            
            # Check dependencies
            if self._check_dependencies(execution):
                # Check resource availability
                if self._check_resource_availability(execution):
                    ready_executions.append(execution)
        
        # Start ready executions
        for execution in ready_executions:
            await self._start_execution(execution)
    
    async def _start_execution(self, execution: WorkflowExecution):
        """Start workflow execution."""
        try:
            # Remove from pending
            if execution in self.pending_executions:
                self.pending_executions.remove(execution)
            
            # Allocate resources
            if self.enable_resource_management:
                self._allocate_resources(execution)
            
            # Update status
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now()
            
            # Add to active executions
            self.active_executions[execution.execution_id] = execution
            
            # Notify status callback
            if self.status_callback:
                self.status_callback(execution)
            
            # Execute workflow asynchronously
            if self.workflow_executor:
                asyncio.create_task(self._execute_workflow(execution))
            
            logger.info(f"Started execution: {execution.workflow_file} ({execution.execution_id})")
        
        except Exception as e:
            logger.error(f"Failed to start execution {execution.execution_id}: {str(e)}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            self.completed_executions.append(execution)
    
    async def _execute_workflow(self, execution: WorkflowExecution):
        """Execute workflow asynchronously."""
        try:
            # Set timeout
            timeout_seconds = execution.timeout_minutes * 60
            
            # Execute workflow with timeout
            result = await asyncio.wait_for(
                self._run_workflow(execution),
                timeout=timeout_seconds
            )
            
            # Update execution result
            execution.result = result
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now()
            
            logger.info(f"Completed execution: {execution.execution_id}")
        
        except asyncio.TimeoutError:
            logger.error(f"Execution timeout: {execution.execution_id}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = "Execution timeout"
            execution.completed_at = datetime.now()
        
        except Exception as e:
            logger.error(f"Execution error: {execution.execution_id}: {str(e)}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            
            # Check if retry is needed
            if execution.retry_count < execution.max_retries:
                execution.retry_count += 1
                execution.status = ExecutionStatus.RETRYING
                
                # Add back to pending with delay
                await asyncio.sleep(30)  # Wait 30 seconds before retry
                execution.status = ExecutionStatus.PENDING
                self.pending_executions.append(execution)
                
                logger.info(f"Retrying execution: {execution.execution_id} (attempt {execution.retry_count})")
        
        finally:
            # Release resources
            if self.enable_resource_management:
                self._release_resources(execution)
            
            # Move to completed if not retrying
            if execution.status != ExecutionStatus.PENDING:
                if execution.execution_id in self.active_executions:
                    del self.active_executions[execution.execution_id]
                
                if execution not in self.completed_executions:
                    self.completed_executions.append(execution)
            
            # Notify status callback
            if self.status_callback:
                self.status_callback(execution)
    
    async def _run_workflow(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Run workflow using executor callback."""
        if not self.workflow_executor:
            raise Exception("No workflow executor configured")
        
        # Call executor in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.workflow_executor,
            execution.workflow_file,
            execution.variables
        )
        
        return result
    
    def _check_dependencies(self, execution: WorkflowExecution) -> bool:
        """Check if execution dependencies are satisfied."""
        for dependency in execution.dependencies:
            # Find dependency execution
            dep_execution = None
            
            # Check completed executions
            for completed in self.completed_executions:
                if completed.workflow_id == dependency.dependency_id:
                    dep_execution = completed
                    break
            
            if not dep_execution:
                return False  # Dependency not found or not completed
            
            # Check dependency type
            if dependency.dependency_type == "success":
                if dep_execution.status != ExecutionStatus.COMPLETED:
                    return False
            elif dependency.dependency_type == "completion":
                if dep_execution.status not in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                    return False
            elif dependency.dependency_type == "failure":
                if dep_execution.status != ExecutionStatus.FAILED:
                    return False
        
        return True
    
    def _check_resource_availability(self, execution: WorkflowExecution) -> bool:
        """Check if required resources are available."""
        if not self.enable_resource_management:
            return True
        
        req = execution.resource_requirements
        
        # Check CPU
        if self.allocated_resources.cpu_cores + req.cpu_cores > self.total_resources.cpu_cores:
            return False
        
        # Check memory
        if self.allocated_resources.memory_mb + req.memory_mb > self.total_resources.memory_mb:
            return False
        
        # Check network bandwidth
        if (self.allocated_resources.network_bandwidth_mbps + req.network_bandwidth_mbps > 
            self.total_resources.network_bandwidth_mbps):
            return False
        
        # Check storage
        if self.allocated_resources.storage_gb + req.storage_gb > self.total_resources.storage_gb:
            return False
        
        # Check custom resources
        for resource_name, required_amount in req.custom_resources.items():
            allocated = self.allocated_resources.custom_resources.get(resource_name, 0)
            total = self.total_resources.custom_resources.get(resource_name, 0)
            
            if allocated + required_amount > total:
                return False
        
        return True
    
    def _allocate_resources(self, execution: WorkflowExecution):
        """Allocate resources for execution."""
        req = execution.resource_requirements
        
        self.allocated_resources.cpu_cores += req.cpu_cores
        self.allocated_resources.memory_mb += req.memory_mb
        self.allocated_resources.network_bandwidth_mbps += req.network_bandwidth_mbps
        self.allocated_resources.storage_gb += req.storage_gb
        
        for resource_name, amount in req.custom_resources.items():
            if resource_name not in self.allocated_resources.custom_resources:
                self.allocated_resources.custom_resources[resource_name] = 0
            self.allocated_resources.custom_resources[resource_name] += amount
        
        # Record allocated resources in execution
        execution.allocated_resources = {
            "cpu_cores": req.cpu_cores,
            "memory_mb": req.memory_mb,
            "network_bandwidth_mbps": req.network_bandwidth_mbps,
            "storage_gb": req.storage_gb,
            **req.custom_resources
        }
        
        logger.debug(f"Allocated resources for {execution.execution_id}: {execution.allocated_resources}")
    
    def _release_resources(self, execution: WorkflowExecution):
        """Release resources from execution."""
        if not execution.allocated_resources:
            return
        
        self.allocated_resources.cpu_cores -= execution.allocated_resources.get("cpu_cores", 0)
        self.allocated_resources.memory_mb -= execution.allocated_resources.get("memory_mb", 0)
        self.allocated_resources.network_bandwidth_mbps -= execution.allocated_resources.get("network_bandwidth_mbps", 0)
        self.allocated_resources.storage_gb -= execution.allocated_resources.get("storage_gb", 0)
        
        for resource_name, amount in execution.allocated_resources.items():
            if resource_name in ["cpu_cores", "memory_mb", "network_bandwidth_mbps", "storage_gb"]:
                continue
            
            if resource_name in self.allocated_resources.custom_resources:
                self.allocated_resources.custom_resources[resource_name] -= amount
                if self.allocated_resources.custom_resources[resource_name] <= 0:
                    del self.allocated_resources.custom_resources[resource_name]
        
        logger.debug(f"Released resources for {execution.execution_id}")
    
    async def _check_completed_executions(self):
        """Check for completed executions and clean up."""
        # This method can be extended to handle post-completion tasks
        pass
    
    def _cleanup_executions(self):
        """Clean up old execution records."""
        # Keep only last 1000 completed executions
        if len(self.completed_executions) > 1000:
            self.completed_executions = self.completed_executions[-1000:]
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get orchestrator status and statistics."""
        return {
            "running": self.running,
            "active_executions": len(self.active_executions),
            "pending_executions": len(self.pending_executions),
            "completed_executions": len(self.completed_executions),
            "max_concurrent_workflows": self.max_concurrent_workflows,
            "resource_utilization": {
                "cpu_cores": f"{self.allocated_resources.cpu_cores}/{self.total_resources.cpu_cores}",
                "memory_mb": f"{self.allocated_resources.memory_mb}/{self.total_resources.memory_mb}",
                "network_bandwidth_mbps": f"{self.allocated_resources.network_bandwidth_mbps}/{self.total_resources.network_bandwidth_mbps}",
                "storage_gb": f"{self.allocated_resources.storage_gb}/{self.total_resources.storage_gb}"
            }
        }
