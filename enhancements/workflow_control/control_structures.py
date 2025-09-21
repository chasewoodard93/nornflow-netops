"""
Advanced workflow control structures for NornFlow.

This module provides enhanced control flow capabilities including:
- Conditional execution (when, unless, if)
- Loops and iteration (loop, with_items, until)
- Error handling (ignore_errors, rescue, always)
- Retry mechanisms (retry, delay, backoff)
- Workflow dependencies (depends_on, parallel)
"""

from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from jinja2 import Template
import logging

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for workflow control."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    RETRY = "retry"


class ConditionEvaluator:
    """Evaluates conditional expressions in workflow control structures."""
    
    def __init__(self, vars_manager, host_name: str):
        """
        Initialize condition evaluator.
        
        Args:
            vars_manager: NornFlow variables manager
            host_name: Current host name for variable context
        """
        self.vars_manager = vars_manager
        self.host_name = host_name
    
    def evaluate(self, condition: str) -> bool:
        """
        Evaluate a conditional expression.
        
        Args:
            condition: Jinja2 template expression to evaluate
            
        Returns:
            Boolean result of the condition evaluation
        """
        try:
            # Get variable context for this host
            context = self.vars_manager.get_device_context(self.host_name)
            flat_context = context.get_flat_context()
            
            # Add host namespace
            flat_context["host"] = context.host_namespace
            
            # Create and render template
            template = Template(condition)
            result = template.render(**flat_context)
            
            # Convert result to boolean
            if isinstance(result, str):
                # Handle string boolean representations
                result = result.strip().lower()
                if result in ('true', '1', 'yes', 'on'):
                    return True
                elif result in ('false', '0', 'no', 'off', ''):
                    return False
                else:
                    # Try to evaluate as Python expression
                    try:
                        return bool(eval(result))
                    except:
                        return bool(result)
            
            return bool(result)
            
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}' for host {self.host_name}: {e}")
            return False


class RetryStrategy:
    """Defines retry behavior for task execution."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        retry_on: Optional[List[str]] = None
    ):
        """
        Initialize retry strategy.
        
        Args:
            max_attempts: Maximum number of retry attempts
            delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for delay on each retry
            max_delay: Maximum delay between retries
            retry_on: List of exception types to retry on
        """
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.retry_on = retry_on or ["ConnectionError", "TimeoutError", "TemporaryFailure"]
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if a task should be retried based on the exception and attempt count.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (1-based)
            
        Returns:
            True if the task should be retried
        """
        if attempt >= self.max_attempts:
            return False
        
        exception_name = type(exception).__name__
        return exception_name in self.retry_on
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        if attempt <= 1:
            return 0
        
        delay = self.delay * (self.backoff_factor ** (attempt - 2))
        return min(delay, self.max_delay)


class LoopController:
    """Controls loop execution in workflows."""
    
    def __init__(self, vars_manager, host_name: str):
        """
        Initialize loop controller.
        
        Args:
            vars_manager: NornFlow variables manager
            host_name: Current host name for variable context
        """
        self.vars_manager = vars_manager
        self.host_name = host_name
        self.condition_evaluator = ConditionEvaluator(vars_manager, host_name)
    
    def expand_items(self, items_spec: Union[str, List[Any]]) -> List[Any]:
        """
        Expand items specification into a list of items to iterate over.
        
        Args:
            items_spec: Items specification (variable name or list)
            
        Returns:
            List of items to iterate over
        """
        if isinstance(items_spec, list):
            return items_spec
        
        if isinstance(items_spec, str):
            # Try to resolve as variable
            try:
                context = self.vars_manager.get_device_context(self.host_name)
                flat_context = context.get_flat_context()
                
                # Render the items specification
                template = Template(items_spec)
                result = template.render(**flat_context)
                
                # Try to evaluate as Python expression
                try:
                    evaluated = eval(result)
                    if isinstance(evaluated, (list, tuple)):
                        return list(evaluated)
                    else:
                        return [evaluated]
                except:
                    # If evaluation fails, treat as literal string
                    return [result]
                    
            except Exception as e:
                logger.warning(f"Failed to expand items '{items_spec}' for host {self.host_name}: {e}")
                return [items_spec]
        
        return [items_spec]
    
    def should_continue_until(self, until_condition: str) -> bool:
        """
        Check if loop should continue based on 'until' condition.
        
        Args:
            until_condition: Condition to check
            
        Returns:
            True if loop should continue (condition is False)
        """
        return not self.condition_evaluator.evaluate(until_condition)


class WorkflowControlEngine:
    """
    Enhanced workflow execution engine with advanced control structures.
    
    This engine extends the basic NornFlow workflow execution with:
    - Conditional execution
    - Loops and iteration
    - Error handling and recovery
    - Retry mechanisms
    - Parallel execution
    """
    
    def __init__(self, vars_manager, nornir_manager):
        """
        Initialize workflow control engine.
        
        Args:
            vars_manager: NornFlow variables manager
            nornir_manager: NornFlow Nornir manager
        """
        self.vars_manager = vars_manager
        self.nornir_manager = nornir_manager
        self.execution_stats = {
            "tasks_executed": 0,
            "tasks_skipped": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "loops_executed": 0
        }
    
    def execute_task_with_control(
        self,
        task,
        tasks_catalog: Dict[str, Callable],
        control_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task with advanced control structures.
        
        Args:
            task: TaskModel instance
            tasks_catalog: Available task functions
            control_config: Control configuration (when, loop, retry, etc.)
            
        Returns:
            Dictionary with execution results and metadata
        """
        control_config = control_config or {}
        results = {
            "task_name": task.name,
            "executed": False,
            "skipped": False,
            "failed": False,
            "retried": 0,
            "loop_iterations": 0,
            "results": {},
            "error": None
        }
        
        try:
            # Check conditional execution
            if not self._should_execute_task(task, control_config):
                results["skipped"] = True
                self.execution_stats["tasks_skipped"] += 1
                return results
            
            # Handle loop execution
            if self._is_loop_task(control_config):
                return self._execute_loop_task(task, tasks_catalog, control_config)
            
            # Handle retry execution
            if self._has_retry_config(control_config):
                return self._execute_task_with_retry(task, tasks_catalog, control_config)
            
            # Standard execution
            aggregated_result = task.run(self.nornir_manager, tasks_catalog)
            results["executed"] = True
            results["results"] = aggregated_result
            self.execution_stats["tasks_executed"] += 1
            
            # Handle set_to variable assignment
            if hasattr(task, "set_to") and task.set_to:
                for host_name, host_result in aggregated_result.items():
                    self.vars_manager.set_runtime_variable(
                        name=task.set_to,
                        value=host_result,
                        host_name=host_name
                    )
            
        except Exception as e:
            results["failed"] = True
            results["error"] = str(e)
            self.execution_stats["tasks_failed"] += 1
            
            # Handle error recovery
            if not control_config.get("ignore_errors", False):
                raise
        
        return results
    
    def _should_execute_task(self, task, control_config: Dict[str, Any]) -> bool:
        """Check if task should be executed based on conditions."""
        # Check 'when' condition
        when_condition = control_config.get("when")
        if when_condition:
            # For now, evaluate against first host (could be enhanced for per-host evaluation)
            hosts = list(self.nornir_manager.nornir.inventory.hosts.keys())
            if hosts:
                evaluator = ConditionEvaluator(self.vars_manager, hosts[0])
                if not evaluator.evaluate(when_condition):
                    return False
        
        # Check 'unless' condition
        unless_condition = control_config.get("unless")
        if unless_condition:
            hosts = list(self.nornir_manager.nornir.inventory.hosts.keys())
            if hosts:
                evaluator = ConditionEvaluator(self.vars_manager, hosts[0])
                if evaluator.evaluate(unless_condition):
                    return False
        
        return True
    
    def _is_loop_task(self, control_config: Dict[str, Any]) -> bool:
        """Check if task has loop configuration."""
        return any(key in control_config for key in ["loop", "with_items", "until"])
    
    def _has_retry_config(self, control_config: Dict[str, Any]) -> bool:
        """Check if task has retry configuration."""
        return "retry" in control_config
    
    def _execute_loop_task(self, task, tasks_catalog: Dict[str, Callable], control_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task in a loop."""
        results = {
            "task_name": task.name,
            "executed": True,
            "loop_iterations": 0,
            "results": {},
            "iterations": []
        }
        
        # Get loop configuration
        loop_items = control_config.get("loop") or control_config.get("with_items")
        until_condition = control_config.get("until")
        max_iterations = control_config.get("max_iterations", 100)
        
        hosts = list(self.nornir_manager.nornir.inventory.hosts.keys())
        
        if loop_items:
            # Item-based loop
            for host_name in hosts:
                controller = LoopController(self.vars_manager, host_name)
                items = controller.expand_items(loop_items)
                
                for i, item in enumerate(items):
                    if results["loop_iterations"] >= max_iterations:
                        break
                    
                    # Set loop variables
                    self.vars_manager.set_runtime_variable("item", item, host_name)
                    self.vars_manager.set_runtime_variable("loop_index", i, host_name)
                    
                    # Execute task iteration
                    iteration_result = task.run(self.nornir_manager, tasks_catalog)
                    results["iterations"].append({
                        "index": i,
                        "item": item,
                        "result": iteration_result
                    })
                    results["loop_iterations"] += 1
        
        elif until_condition:
            # Condition-based loop
            for host_name in hosts:
                controller = LoopController(self.vars_manager, host_name)
                iteration = 0
                
                while iteration < max_iterations:
                    # Execute task iteration
                    iteration_result = task.run(self.nornir_manager, tasks_catalog)
                    results["iterations"].append({
                        "index": iteration,
                        "result": iteration_result
                    })
                    results["loop_iterations"] += 1
                    iteration += 1
                    
                    # Check until condition
                    if not controller.should_continue_until(until_condition):
                        break
        
        self.execution_stats["loops_executed"] += 1
        return results
    
    def _execute_task_with_retry(self, task, tasks_catalog: Dict[str, Callable], control_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with retry logic."""
        retry_config = control_config["retry"]
        strategy = RetryStrategy(
            max_attempts=retry_config.get("max_attempts", 3),
            delay=retry_config.get("delay", 1.0),
            backoff_factor=retry_config.get("backoff_factor", 2.0),
            max_delay=retry_config.get("max_delay", 60.0),
            retry_on=retry_config.get("retry_on")
        )
        
        results = {
            "task_name": task.name,
            "executed": False,
            "retried": 0,
            "results": None,
            "attempts": []
        }
        
        for attempt in range(1, strategy.max_attempts + 1):
            try:
                # Add delay before retry (except first attempt)
                delay = strategy.get_delay(attempt)
                if delay > 0:
                    time.sleep(delay)
                
                # Execute task
                aggregated_result = task.run(self.nornir_manager, tasks_catalog)
                
                # Check if any host failed
                has_failures = any(
                    host_result.failed for host_result in aggregated_result.values()
                )
                
                if not has_failures:
                    # Success
                    results["executed"] = True
                    results["results"] = aggregated_result
                    results["attempts"].append({
                        "attempt": attempt,
                        "success": True,
                        "delay": delay
                    })
                    break
                else:
                    # Some hosts failed, check if we should retry
                    results["attempts"].append({
                        "attempt": attempt,
                        "success": False,
                        "delay": delay,
                        "failures": [
                            host_name for host_name, host_result in aggregated_result.items()
                            if host_result.failed
                        ]
                    })
                    
                    if attempt < strategy.max_attempts:
                        results["retried"] += 1
                        self.execution_stats["tasks_retried"] += 1
                    else:
                        # Final attempt failed
                        results["results"] = aggregated_result
                        raise Exception(f"Task failed after {strategy.max_attempts} attempts")
                        
            except Exception as e:
                results["attempts"].append({
                    "attempt": attempt,
                    "success": False,
                    "delay": delay,
                    "error": str(e)
                })
                
                if attempt < strategy.max_attempts and strategy.should_retry(e, attempt):
                    results["retried"] += 1
                    self.execution_stats["tasks_retried"] += 1
                    continue
                else:
                    # Final failure
                    raise
        
        return results


class EnhancedTaskModel:
    """
    Enhanced task model with advanced control flow capabilities.

    This extends the basic TaskModel with support for:
    - Conditional execution (when, unless)
    - Loop constructs (loop, with_items, until)
    - Error handling (ignore_errors, rescue, always)
    - Retry mechanisms (retry with backoff)
    - Dependencies (depends_on)
    """

    def __init__(self, task_model, control_config: Optional[Dict[str, Any]] = None):
        """
        Initialize enhanced task model.

        Args:
            task_model: Original TaskModel instance
            control_config: Control flow configuration
        """
        self.task_model = task_model
        self.control_config = control_config or {}

        # Control flow properties
        self.when = self.control_config.get("when")
        self.unless = self.control_config.get("unless")
        self.loop = self.control_config.get("loop")
        self.with_items = self.control_config.get("with_items")
        self.until = self.control_config.get("until")
        self.retry = self.control_config.get("retry")
        self.ignore_errors = self.control_config.get("ignore_errors", False)
        self.depends_on = self.control_config.get("depends_on", [])
        self.rescue = self.control_config.get("rescue")
        self.always = self.control_config.get("always")

        # Execution metadata
        self.execution_mode = self._determine_execution_mode()
        self.dependencies_met = False

    def _determine_execution_mode(self) -> ExecutionMode:
        """Determine the execution mode based on control configuration."""
        if self.loop or self.with_items or self.until:
            return ExecutionMode.LOOP
        elif self.retry:
            return ExecutionMode.RETRY
        elif self.when or self.unless:
            return ExecutionMode.CONDITIONAL
        else:
            return ExecutionMode.SEQUENTIAL

    @property
    def name(self):
        """Get task name."""
        return self.task_model.name

    @property
    def args(self):
        """Get task arguments."""
        return self.task_model.args

    @property
    def set_to(self):
        """Get set_to variable name."""
        return getattr(self.task_model, "set_to", None)

    def run(self, nornir_manager, tasks_catalog: Dict[str, Callable]) -> Any:
        """
        Execute the enhanced task with control flow.

        Args:
            nornir_manager: NornirManager instance
            tasks_catalog: Available task functions

        Returns:
            Task execution results
        """
        # For now, delegate to original task model
        # This will be enhanced when integrated with WorkflowControlEngine
        return self.task_model.run(nornir_manager, tasks_catalog)

    def check_dependencies(self, completed_tasks: List[str]) -> bool:
        """
        Check if task dependencies are satisfied.

        Args:
            completed_tasks: List of completed task names

        Returns:
            True if all dependencies are met
        """
        if not self.depends_on:
            return True

        if isinstance(self.depends_on, str):
            dependencies = [self.depends_on]
        else:
            dependencies = self.depends_on

        return all(dep in completed_tasks for dep in dependencies)


def parse_enhanced_workflow(workflow_dict: Dict[str, Any]) -> List[EnhancedTaskModel]:
    """
    Parse a workflow dictionary into enhanced task models.

    Args:
        workflow_dict: Workflow definition dictionary

    Returns:
        List of EnhancedTaskModel instances
    """
    from nornflow.models import TaskModel

    enhanced_tasks = []
    tasks_data = workflow_dict.get("workflow", {}).get("tasks", [])

    for task_data in tasks_data:
        # Separate control config from task config
        control_keys = {
            "when", "unless", "loop", "with_items", "until", "retry",
            "ignore_errors", "depends_on", "rescue", "always"
        }

        task_config = {k: v for k, v in task_data.items() if k not in control_keys}
        control_config = {k: v for k, v in task_data.items() if k in control_keys}

        # Create original task model
        task_model = TaskModel.create(task_config)

        # Create enhanced task model
        enhanced_task = EnhancedTaskModel(task_model, control_config)
        enhanced_tasks.append(enhanced_task)

    return enhanced_tasks
