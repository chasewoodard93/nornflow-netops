"""
Enhanced workflow execution engine that extends NornFlow with advanced control structures.

This module provides a drop-in replacement for the standard NornFlow workflow execution
with support for conditional execution, loops, error handling, and retry mechanisms.
"""

from typing import Any, Dict, List, Optional, Callable
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .control_structures import (
    WorkflowControlEngine, 
    EnhancedTaskModel, 
    parse_enhanced_workflow,
    ExecutionMode
)

logger = logging.getLogger(__name__)


class EnhancedWorkflowExecutor:
    """
    Enhanced workflow executor with advanced control flow capabilities.
    
    This class extends the standard NornFlow workflow execution with:
    - Conditional task execution (when, unless)
    - Loop constructs (loop, with_items, until)
    - Error handling and recovery (ignore_errors, rescue, always)
    - Retry mechanisms with backoff strategies
    - Task dependencies and parallel execution
    """
    
    def __init__(self, workflow, vars_manager, nornir_manager):
        """
        Initialize enhanced workflow executor.
        
        Args:
            workflow: Original NornFlow workflow instance
            vars_manager: NornFlow variables manager
            nornir_manager: NornFlow Nornir manager
        """
        self.workflow = workflow
        self.vars_manager = vars_manager
        self.nornir_manager = nornir_manager
        self.control_engine = WorkflowControlEngine(vars_manager, nornir_manager)
        
        # Execution state
        self.completed_tasks = []
        self.failed_tasks = []
        self.execution_stats = {
            "total_tasks": 0,
            "executed_tasks": 0,
            "skipped_tasks": 0,
            "failed_tasks": 0,
            "retried_tasks": 0,
            "loop_iterations": 0
        }
    
    def execute_enhanced_workflow(
        self,
        tasks_catalog: Dict[str, Callable],
        enhanced_tasks: Optional[List[EnhancedTaskModel]] = None,
        parallel_execution: bool = False,
        max_workers: int = 4
    ) -> Dict[str, Any]:
        """
        Execute workflow with enhanced control structures.
        
        Args:
            tasks_catalog: Available task functions
            enhanced_tasks: Pre-parsed enhanced tasks (optional)
            parallel_execution: Whether to execute independent tasks in parallel
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary with execution results and statistics
        """
        if enhanced_tasks is None:
            # Parse workflow into enhanced tasks
            workflow_dict = self._get_workflow_dict()
            enhanced_tasks = parse_enhanced_workflow(workflow_dict)
        
        self.execution_stats["total_tasks"] = len(enhanced_tasks)
        
        logger.info(f"Starting enhanced workflow execution with {len(enhanced_tasks)} tasks")
        
        if parallel_execution:
            return self._execute_parallel(enhanced_tasks, tasks_catalog, max_workers)
        else:
            return self._execute_sequential(enhanced_tasks, tasks_catalog)
    
    def _execute_sequential(
        self, 
        enhanced_tasks: List[EnhancedTaskModel], 
        tasks_catalog: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """Execute tasks sequentially with dependency checking."""
        results = {
            "execution_mode": "sequential",
            "task_results": [],
            "stats": self.execution_stats,
            "success": True
        }
        
        remaining_tasks = enhanced_tasks.copy()
        
        while remaining_tasks:
            # Find tasks whose dependencies are satisfied
            ready_tasks = [
                task for task in remaining_tasks 
                if task.check_dependencies(self.completed_tasks)
            ]
            
            if not ready_tasks:
                # Circular dependency or missing dependency
                unmet_deps = []
                for task in remaining_tasks:
                    deps = task.depends_on if isinstance(task.depends_on, list) else [task.depends_on] if task.depends_on else []
                    unmet = [dep for dep in deps if dep not in self.completed_tasks]
                    if unmet:
                        unmet_deps.append(f"{task.name}: {unmet}")
                
                error_msg = f"Circular or unmet dependencies detected: {unmet_deps}"
                logger.error(error_msg)
                results["success"] = False
                results["error"] = error_msg
                break
            
            # Execute ready tasks
            for task in ready_tasks:
                try:
                    task_result = self._execute_single_task(task, tasks_catalog)
                    results["task_results"].append(task_result)
                    
                    if task_result["executed"] and not task_result["failed"]:
                        self.completed_tasks.append(task.name)
                        self.execution_stats["executed_tasks"] += 1
                    elif task_result["skipped"]:
                        self.execution_stats["skipped_tasks"] += 1
                    elif task_result["failed"]:
                        self.failed_tasks.append(task.name)
                        self.execution_stats["failed_tasks"] += 1
                        
                        # Stop execution if task failed and ignore_errors is False
                        if not task.ignore_errors:
                            results["success"] = False
                            results["error"] = f"Task {task.name} failed: {task_result.get('error')}"
                            return results
                    
                    # Update retry statistics
                    if task_result.get("retried", 0) > 0:
                        self.execution_stats["retried_tasks"] += 1
                    
                    # Update loop statistics
                    if task_result.get("loop_iterations", 0) > 0:
                        self.execution_stats["loop_iterations"] += task_result["loop_iterations"]
                    
                except Exception as e:
                    logger.error(f"Unexpected error executing task {task.name}: {e}")
                    self.failed_tasks.append(task.name)
                    self.execution_stats["failed_tasks"] += 1
                    
                    if not task.ignore_errors:
                        results["success"] = False
                        results["error"] = f"Unexpected error in task {task.name}: {str(e)}"
                        return results
                
                # Remove completed task from remaining tasks
                remaining_tasks.remove(task)
        
        logger.info(f"Enhanced workflow execution completed. Stats: {self.execution_stats}")
        return results
    
    def _execute_parallel(
        self, 
        enhanced_tasks: List[EnhancedTaskModel], 
        tasks_catalog: Dict[str, Callable],
        max_workers: int
    ) -> Dict[str, Any]:
        """Execute independent tasks in parallel."""
        results = {
            "execution_mode": "parallel",
            "task_results": [],
            "stats": self.execution_stats,
            "success": True
        }
        
        # Group tasks by dependency levels
        dependency_levels = self._analyze_dependencies(enhanced_tasks)
        
        for level, tasks_in_level in dependency_levels.items():
            logger.info(f"Executing dependency level {level} with {len(tasks_in_level)} tasks")
            
            if len(tasks_in_level) == 1:
                # Single task, execute sequentially
                task = tasks_in_level[0]
                task_result = self._execute_single_task(task, tasks_catalog)
                results["task_results"].append(task_result)
                self._update_task_completion(task, task_result)
            else:
                # Multiple independent tasks, execute in parallel
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_task = {
                        executor.submit(self._execute_single_task, task, tasks_catalog): task
                        for task in tasks_in_level
                    }
                    
                    for future in as_completed(future_to_task):
                        task = future_to_task[future]
                        try:
                            task_result = future.result()
                            results["task_results"].append(task_result)
                            self._update_task_completion(task, task_result)
                        except Exception as e:
                            logger.error(f"Parallel task {task.name} failed: {e}")
                            self.failed_tasks.append(task.name)
                            self.execution_stats["failed_tasks"] += 1
                            
                            if not task.ignore_errors:
                                results["success"] = False
                                results["error"] = f"Parallel task {task.name} failed: {str(e)}"
                                return results
        
        logger.info(f"Enhanced parallel workflow execution completed. Stats: {self.execution_stats}")
        return results
    
    def _execute_single_task(
        self, 
        task: EnhancedTaskModel, 
        tasks_catalog: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """Execute a single enhanced task."""
        logger.debug(f"Executing task: {task.name} (mode: {task.execution_mode.value})")
        
        # Use the control engine to execute the task
        return self.control_engine.execute_task_with_control(
            task.task_model, 
            tasks_catalog, 
            task.control_config
        )
    
    def _update_task_completion(self, task: EnhancedTaskModel, task_result: Dict[str, Any]):
        """Update task completion statistics."""
        if task_result["executed"] and not task_result["failed"]:
            self.completed_tasks.append(task.name)
            self.execution_stats["executed_tasks"] += 1
        elif task_result["skipped"]:
            self.execution_stats["skipped_tasks"] += 1
        elif task_result["failed"]:
            self.failed_tasks.append(task.name)
            self.execution_stats["failed_tasks"] += 1
        
        # Update retry and loop statistics
        if task_result.get("retried", 0) > 0:
            self.execution_stats["retried_tasks"] += 1
        if task_result.get("loop_iterations", 0) > 0:
            self.execution_stats["loop_iterations"] += task_result["loop_iterations"]
    
    def _analyze_dependencies(self, tasks: List[EnhancedTaskModel]) -> Dict[int, List[EnhancedTaskModel]]:
        """Analyze task dependencies and group tasks by execution level."""
        dependency_levels = {}
        task_levels = {}
        
        def calculate_level(task: EnhancedTaskModel, visited: set) -> int:
            if task.name in visited:
                raise ValueError(f"Circular dependency detected involving task: {task.name}")
            
            if task.name in task_levels:
                return task_levels[task.name]
            
            if not task.depends_on:
                level = 0
            else:
                visited.add(task.name)
                dependencies = task.depends_on if isinstance(task.depends_on, list) else [task.depends_on]
                
                max_dep_level = -1
                for dep_name in dependencies:
                    dep_task = next((t for t in tasks if t.name == dep_name), None)
                    if dep_task:
                        dep_level = calculate_level(dep_task, visited.copy())
                        max_dep_level = max(max_dep_level, dep_level)
                
                level = max_dep_level + 1
                visited.remove(task.name)
            
            task_levels[task.name] = level
            return level
        
        # Calculate levels for all tasks
        for task in tasks:
            level = calculate_level(task, set())
            if level not in dependency_levels:
                dependency_levels[level] = []
            dependency_levels[level].append(task)
        
        return dependency_levels
    
    def _get_workflow_dict(self) -> Dict[str, Any]:
        """Extract workflow dictionary from NornFlow workflow object."""
        # This is a simplified extraction - in practice, you'd need to access
        # the workflow's internal structure or modify NornFlow to expose this
        workflow_model = self.workflow.records["WorkflowModel"][0]
        
        return {
            "workflow": {
                "name": workflow_model.name,
                "description": workflow_model.description,
                "tasks": [
                    {
                        "name": task.name,
                        "args": dict(task.args) if task.args else {},
                        "set_to": getattr(task, "set_to", None)
                    }
                    for task in self.workflow.tasks
                ]
            }
        }
