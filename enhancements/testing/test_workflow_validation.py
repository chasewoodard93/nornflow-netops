"""
Workflow validation testing framework.

Tests enhanced workflow control structures including:
- Conditional execution (when/unless statements)
- Loop constructs (loop/with_items/until)
- Error handling (ignore_errors/rescue/always)
- Task dependencies and orchestration
- Variable resolution and templating
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import yaml
from datetime import datetime

from enhancements.workflow_control.enhanced_workflow import EnhancedWorkflowExecutor
from enhancements.workflow_control.control_structures import (
    ConditionEvaluator,
    LoopController,
    RetryStrategy,
    WorkflowControlEngine
)
from enhancements.testing.test_framework import WorkflowTestBase


class TestConditionalExecution(WorkflowTestBase):
    """Test conditional execution logic."""
    
    def test_condition_evaluator_simple_when(self):
        """Test simple when condition evaluation."""
        evaluator = ConditionEvaluator()
        
        # Test true condition
        context = {"deploy_config": True, "environment": "production"}
        assert evaluator.evaluate("{{ deploy_config }}", context) is True
        assert evaluator.evaluate("{{ environment == 'production' }}", context) is True
        
        # Test false condition
        context = {"deploy_config": False, "environment": "test"}
        assert evaluator.evaluate("{{ deploy_config }}", context) is False
        assert evaluator.evaluate("{{ environment == 'production' }}", context) is False
    
    def test_condition_evaluator_complex_expressions(self):
        """Test complex conditional expressions."""
        evaluator = ConditionEvaluator()
        
        context = {
            "device_count": 10,
            "environment": "production",
            "maintenance_window": True,
            "critical_devices": ["router-01", "router-02"]
        }
        
        # Test complex conditions
        assert evaluator.evaluate("{{ device_count > 5 and environment == 'production' }}", context) is True
        assert evaluator.evaluate("{{ maintenance_window and device_count < 20 }}", context) is True
        assert evaluator.evaluate("{{ 'router-01' in critical_devices }}", context) is True
        assert evaluator.evaluate("{{ device_count > 20 or environment == 'test' }}", context) is False
    
    def test_condition_evaluator_unless_logic(self):
        """Test unless condition logic (inverse of when)."""
        evaluator = ConditionEvaluator()
        
        context = {"skip_backup": True, "dry_run": False}
        
        # Unless should be inverse of when
        assert evaluator.evaluate("{{ skip_backup }}", context, unless=True) is False
        assert evaluator.evaluate("{{ dry_run }}", context, unless=True) is True
    
    def test_conditional_workflow_execution(self, conditional_workflow, temp_workflow_dir):
        """Test workflow execution with conditional tasks."""
        # Create workflow file
        workflow_file = self.create_workflow_file(temp_workflow_dir, conditional_workflow)
        
        # Mock task execution
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.return_value = Mock(failed=False, result={"success": True})
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow with conditions that should run deploy_config
            context = {"deploy_config": True, "environment": "test"}
            result = executor.execute_workflow(workflow_file, context=context)
            
            # Verify execution
            assert result.success is True
            
            # Should execute backup_config and deploy_config, but not validate_config
            executed_tasks = [call[0][0] for call in mock_execute.call_args_list]
            assert "backup_config" in executed_tasks
            assert "deploy_config" in executed_tasks
            assert "validate_config" not in executed_tasks  # environment != 'production'
    
    def test_conditional_workflow_skipped_tasks(self, conditional_workflow, temp_workflow_dir):
        """Test workflow execution with skipped conditional tasks."""
        # Create workflow file
        workflow_file = self.create_workflow_file(temp_workflow_dir, conditional_workflow)
        
        # Mock task execution
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.return_value = Mock(failed=False, result={"success": True})
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow with conditions that should skip deploy_config
            context = {"deploy_config": False, "environment": "test"}
            result = executor.execute_workflow(workflow_file, context=context)
            
            # Verify execution
            assert result.success is True
            
            # Should only execute backup_config
            executed_tasks = [call[0][0] for call in mock_execute.call_args_list]
            assert "backup_config" in executed_tasks
            assert "deploy_config" not in executed_tasks  # deploy_config is False
            assert "validate_config" not in executed_tasks


class TestLoopExecution(WorkflowTestBase):
    """Test loop execution logic."""
    
    def test_loop_controller_simple_loop(self):
        """Test simple loop iteration."""
        controller = LoopController()
        
        items = ["item1", "item2", "item3"]
        iterations = list(controller.iterate_loop(items))
        
        assert len(iterations) == 3
        assert iterations[0]["item"] == "item1"
        assert iterations[0]["loop_index"] == 0
        assert iterations[1]["item"] == "item2"
        assert iterations[2]["item"] == "item3"
    
    def test_loop_controller_with_items(self):
        """Test with_items loop iteration."""
        controller = LoopController()
        
        items = [
            {"name": "interface1", "vlan": 100},
            {"name": "interface2", "vlan": 200}
        ]
        iterations = list(controller.iterate_with_items(items))
        
        assert len(iterations) == 2
        assert iterations[0]["item"]["name"] == "interface1"
        assert iterations[0]["item"]["vlan"] == 100
        assert iterations[1]["item"]["name"] == "interface2"
    
    def test_loop_controller_until_condition(self):
        """Test until loop with condition."""
        controller = LoopController()
        
        # Mock condition that becomes true after 3 iterations
        condition_calls = 0
        def mock_condition(context):
            nonlocal condition_calls
            condition_calls += 1
            return condition_calls >= 3
        
        iterations = list(controller.iterate_until(mock_condition, max_iterations=5))
        
        assert len(iterations) == 3  # Should stop when condition becomes true
        assert condition_calls == 3
    
    def test_loop_workflow_execution(self, loop_workflow, temp_workflow_dir):
        """Test workflow execution with loop constructs."""
        # Create workflow file
        workflow_file = self.create_workflow_file(temp_workflow_dir, loop_workflow)
        
        # Mock task execution
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.return_value = Mock(failed=False, result={"success": True})
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Verify execution
            assert result.success is True
            
            # Should execute configure_interface 3 times and create_vlan 3 times
            executed_tasks = [call[0][0] for call in mock_execute.call_args_list]
            configure_calls = executed_tasks.count("configure_interface")
            vlan_calls = executed_tasks.count("create_vlan")
            
            assert configure_calls == 3  # 3 interfaces
            assert vlan_calls == 3  # 3 VLANs
    
    def test_loop_variable_substitution(self):
        """Test variable substitution in loop contexts."""
        controller = LoopController()
        
        items = ["GigE0/1", "GigE0/2", "GigE0/3"]
        template = "interface {{ item }}"
        
        for iteration in controller.iterate_loop(items):
            # Simulate template rendering with loop variables
            context = {"item": iteration["item"]}
            rendered = template.replace("{{ item }}", context["item"])
            
            if iteration["loop_index"] == 0:
                assert rendered == "interface GigE0/1"
            elif iteration["loop_index"] == 1:
                assert rendered == "interface GigE0/2"
            elif iteration["loop_index"] == 2:
                assert rendered == "interface GigE0/3"


class TestErrorHandling(WorkflowTestBase):
    """Test error handling and recovery mechanisms."""
    
    def test_retry_strategy_exponential_backoff(self):
        """Test exponential backoff retry strategy."""
        strategy = RetryStrategy(
            max_attempts=3,
            delay=1,
            backoff_factor=2.0,
            max_delay=10
        )
        
        delays = []
        for attempt in range(3):
            delay = strategy.get_delay(attempt)
            delays.append(delay)
        
        assert delays[0] == 1  # First retry: 1 second
        assert delays[1] == 2  # Second retry: 2 seconds
        assert delays[2] == 4  # Third retry: 4 seconds
    
    def test_retry_strategy_max_delay_limit(self):
        """Test retry strategy respects max delay limit."""
        strategy = RetryStrategy(
            max_attempts=5,
            delay=1,
            backoff_factor=3.0,
            max_delay=5
        )
        
        # With backoff factor 3, delays would be: 1, 3, 9, 27, 81
        # But max_delay=5 should cap them
        delays = [strategy.get_delay(i) for i in range(5)]
        
        assert delays[0] == 1
        assert delays[1] == 3
        assert delays[2] == 5  # Capped at max_delay
        assert delays[3] == 5  # Capped at max_delay
        assert delays[4] == 5  # Capped at max_delay
    
    def test_workflow_ignore_errors(self, temp_workflow_dir):
        """Test workflow execution with ignore_errors."""
        workflow_data = {
            "workflow": {
                "name": "Error Handling Test",
                "tasks": [
                    {
                        "name": "failing_task",
                        "args": {"will_fail": True},
                        "ignore_errors": True
                    },
                    {
                        "name": "success_task",
                        "args": {"message": "This should run"},
                        "depends_on": "failing_task"
                    }
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution - first task fails, second succeeds
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.side_effect = [
                Mock(failed=True, result={"error": "Task failed"}),  # failing_task
                Mock(failed=False, result={"success": True})  # success_task
            ]
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Workflow should succeed despite first task failure
            assert result.success is True
            assert len(mock_execute.call_args_list) == 2
    
    def test_workflow_rescue_block(self, temp_workflow_dir):
        """Test workflow execution with rescue blocks."""
        workflow_data = {
            "workflow": {
                "name": "Rescue Block Test",
                "tasks": [
                    {
                        "name": "risky_task",
                        "args": {"might_fail": True},
                        "rescue": [
                            {
                                "name": "recovery_task",
                                "args": {"recover": True}
                            }
                        ]
                    }
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution - main task fails, rescue task succeeds
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.side_effect = [
                Mock(failed=True, result={"error": "Main task failed"}),  # risky_task
                Mock(failed=False, result={"recovered": True})  # recovery_task
            ]
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Workflow should succeed due to rescue block
            assert result.success is True
            assert len(mock_execute.call_args_list) == 2
    
    def test_workflow_always_block(self, temp_workflow_dir):
        """Test workflow execution with always blocks."""
        workflow_data = {
            "workflow": {
                "name": "Always Block Test",
                "tasks": [
                    {
                        "name": "main_task",
                        "args": {"operation": "main"},
                        "always": [
                            {
                                "name": "cleanup_task",
                                "args": {"cleanup": True}
                            }
                        ]
                    }
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution - main task fails, always task runs
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task') as mock_execute:
            mock_execute.side_effect = [
                Mock(failed=True, result={"error": "Main task failed"}),  # main_task
                Mock(failed=False, result={"cleaned_up": True})  # cleanup_task
            ]
            
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Always block should run regardless of main task failure
            assert len(mock_execute.call_args_list) == 2
            
            # Verify cleanup task was called
            cleanup_call = mock_execute.call_args_list[1]
            assert "cleanup_task" in cleanup_call[0]


class TestTaskDependencies(WorkflowTestBase):
    """Test task dependency resolution and execution order."""
    
    def test_dependency_resolution_linear(self, temp_workflow_dir):
        """Test linear dependency resolution."""
        workflow_data = {
            "workflow": {
                "name": "Linear Dependencies",
                "tasks": [
                    {"name": "task_c", "args": {}, "depends_on": "task_b"},
                    {"name": "task_a", "args": {}},
                    {"name": "task_b", "args": {}, "depends_on": "task_a"}
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution
        executed_tasks = []
        def mock_execute(task_name, *args, **kwargs):
            executed_tasks.append(task_name)
            return Mock(failed=False, result={"success": True})
        
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task', side_effect=mock_execute):
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Verify execution order
            assert result.success is True
            assert executed_tasks == ["task_a", "task_b", "task_c"]
    
    def test_dependency_resolution_parallel(self, temp_workflow_dir):
        """Test parallel dependency resolution."""
        workflow_data = {
            "workflow": {
                "name": "Parallel Dependencies",
                "tasks": [
                    {"name": "task_a", "args": {}},
                    {"name": "task_b", "args": {}},
                    {"name": "task_c", "args": {}, "depends_on": ["task_a", "task_b"]},
                    {"name": "task_d", "args": {}, "depends_on": ["task_a", "task_b"]}
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution
        executed_tasks = []
        def mock_execute(task_name, *args, **kwargs):
            executed_tasks.append(task_name)
            return Mock(failed=False, result={"success": True})
        
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task', side_effect=mock_execute):
            # Create executor
            executor = EnhancedWorkflowExecutor()
            
            # Execute workflow
            result = executor.execute_workflow(workflow_file)
            
            # Verify execution
            assert result.success is True
            assert len(executed_tasks) == 4
            
            # task_a and task_b should execute first (in any order)
            first_two = executed_tasks[:2]
            assert "task_a" in first_two
            assert "task_b" in first_two
            
            # task_c and task_d should execute after dependencies (in any order)
            last_two = executed_tasks[2:]
            assert "task_c" in last_two
            assert "task_d" in last_two
    
    def test_circular_dependency_detection(self, temp_workflow_dir):
        """Test detection of circular dependencies."""
        workflow_data = {
            "workflow": {
                "name": "Circular Dependencies",
                "tasks": [
                    {"name": "task_a", "args": {}, "depends_on": "task_c"},
                    {"name": "task_b", "args": {}, "depends_on": "task_a"},
                    {"name": "task_c", "args": {}, "depends_on": "task_b"}
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Create executor
        executor = EnhancedWorkflowExecutor()
        
        # Should detect circular dependency and fail
        with pytest.raises(Exception, match="circular.*dependency"):
            executor.execute_workflow(workflow_file)


class TestWorkflowControlEngine(WorkflowTestBase):
    """Test the overall workflow control engine."""
    
    def test_control_engine_integration(self, temp_workflow_dir):
        """Test integration of all control structures."""
        workflow_data = {
            "workflow": {
                "name": "Complete Control Test",
                "vars": {
                    "interfaces": ["GigE0/1", "GigE0/2"],
                    "deploy_config": True,
                    "environment": "production"
                },
                "tasks": [
                    {
                        "name": "backup_config",
                        "args": {"backup_dir": "/tmp"}
                    },
                    {
                        "name": "configure_interface",
                        "args": {"interface": "{{ item }}"},
                        "loop": "{{ interfaces }}",
                        "when": "{{ deploy_config }}",
                        "depends_on": "backup_config",
                        "retry": {"max_attempts": 2, "delay": 1}
                    },
                    {
                        "name": "validate_deployment",
                        "args": {"check": "interfaces"},
                        "when": "{{ environment == 'production' }}",
                        "depends_on": "configure_interface",
                        "rescue": [
                            {
                                "name": "rollback_config",
                                "args": {"restore": True}
                            }
                        ]
                    },
                    {
                        "name": "cleanup",
                        "args": {"temp_files": True},
                        "always": True
                    }
                ]
            }
        }
        
        workflow_file = self.create_workflow_file(temp_workflow_dir, workflow_data)
        
        # Mock task execution
        executed_tasks = []
        def mock_execute(task_name, *args, **kwargs):
            executed_tasks.append(task_name)
            # Simulate validation failure to trigger rescue
            if task_name == "validate_deployment":
                return Mock(failed=True, result={"error": "Validation failed"})
            return Mock(failed=False, result={"success": True})
        
        with patch('enhancements.workflow_control.enhanced_workflow.execute_task', side_effect=mock_execute):
            # Create control engine
            engine = WorkflowControlEngine()
            
            # Execute workflow
            result = engine.execute_workflow(workflow_file)
            
            # Verify complex execution flow
            assert "backup_config" in executed_tasks
            assert executed_tasks.count("configure_interface") == 2  # Loop over 2 interfaces
            assert "validate_deployment" in executed_tasks
            assert "rollback_config" in executed_tasks  # Rescue block executed
            assert "cleanup" in executed_tasks  # Always block executed
