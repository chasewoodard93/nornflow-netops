#!/usr/bin/env python3
"""
Integration example showing how to use enhanced workflow control with NornFlow.

This example demonstrates how to integrate the enhanced workflow control features
with an existing NornFlow setup.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

# Import enhanced workflow components
from .enhanced_workflow import EnhancedWorkflowExecutor
from .control_structures import parse_enhanced_workflow


def create_enhanced_workflow_example():
    """Create an example enhanced workflow definition."""
    return {
        "workflow": {
            "name": "Enhanced Network Automation Example",
            "description": "Demonstrates enhanced workflow control features",
            "vars": {
                "backup_enabled": True,
                "max_retries": 3,
                "interface_list": ["GigabitEthernet0/1", "GigabitEthernet0/2"]
            },
            "tasks": [
                {
                    "name": "echo",
                    "args": {"msg": "Starting enhanced workflow"},
                },
                {
                    "name": "test_connectivity",
                    "args": {"method": "ssh", "timeout": 10},
                    "retry": {
                        "max_attempts": 3,
                        "delay": 2,
                        "backoff_factor": 2.0
                    },
                    "set_to": "connectivity_result"
                },
                {
                    "name": "backup_config",
                    "args": {
                        "backup_dir": "backups/{{ host.name }}",
                        "include_timestamp": True
                    },
                    "when": "{{ backup_enabled and connectivity_result.success }}",
                    "depends_on": "test_connectivity",
                    "set_to": "backup_result"
                },
                {
                    "name": "echo",
                    "args": {"msg": "Configuring interface {{ item }}"},
                    "loop": "{{ interface_list }}",
                    "when": "{{ backup_result.success | default(false) }}"
                },
                {
                    "name": "validate_config",
                    "args": {
                        "validation_commands": ["show ip interface brief"]
                    },
                    "depends_on": ["backup_config"],
                    "ignore_errors": True,
                    "set_to": "validation_result"
                },
                {
                    "name": "echo",
                    "args": {"msg": "Workflow completed successfully"},
                    "always": True
                }
            ]
        }
    }


def demonstrate_enhanced_workflow_parsing():
    """Demonstrate parsing of enhanced workflow."""
    print("🔍 Enhanced Workflow Parsing Demonstration")
    print("=" * 50)
    
    # Create example workflow
    workflow_dict = create_enhanced_workflow_example()
    
    # Parse into enhanced tasks
    enhanced_tasks = parse_enhanced_workflow(workflow_dict)
    
    print(f"Parsed {len(enhanced_tasks)} enhanced tasks:")
    
    for i, task in enumerate(enhanced_tasks, 1):
        print(f"\n{i}. Task: {task.name}")
        print(f"   Execution Mode: {task.execution_mode.value}")
        
        if task.when:
            print(f"   Condition (when): {task.when}")
        if task.unless:
            print(f"   Condition (unless): {task.unless}")
        if task.loop or task.with_items:
            loop_spec = task.loop or task.with_items
            print(f"   Loop: {loop_spec}")
        if task.until:
            print(f"   Until: {task.until}")
        if task.retry:
            print(f"   Retry: {task.retry}")
        if task.depends_on:
            print(f"   Dependencies: {task.depends_on}")
        if task.ignore_errors:
            print(f"   Ignore Errors: {task.ignore_errors}")
        if task.always:
            print(f"   Always Execute: {task.always}")


def demonstrate_condition_evaluation():
    """Demonstrate condition evaluation."""
    print("\n🧮 Condition Evaluation Demonstration")
    print("=" * 50)
    
    from .control_structures import ConditionEvaluator
    
    # Mock variables manager for demonstration
    class MockVarsManager:
        def get_device_context(self, host_name):
            return MockDeviceContext()
    
    class MockDeviceContext:
        def get_flat_context(self):
            return {
                "backup_enabled": True,
                "host_platform": "ios",
                "connectivity_result": {"success": True},
                "backup_result": {"success": True}
            }
        
        @property
        def host_namespace(self):
            return MockHostNamespace()
    
    class MockHostNamespace:
        @property
        def platform(self):
            return "ios"
        
        @property
        def name(self):
            return "router01"
    
    # Create evaluator
    vars_manager = MockVarsManager()
    evaluator = ConditionEvaluator(vars_manager, "router01")
    
    # Test conditions
    test_conditions = [
        "{{ backup_enabled }}",
        "{{ host_platform == 'ios' }}",
        "{{ connectivity_result.success and backup_result.success }}",
        "{{ host_platform in ['ios', 'nxos'] }}",
        "{{ not backup_enabled }}",
        "{{ backup_enabled and host_platform == 'junos' }}"
    ]
    
    for condition in test_conditions:
        try:
            result = evaluator.evaluate(condition)
            print(f"✓ {condition:<50} → {result}")
        except Exception as e:
            print(f"✗ {condition:<50} → Error: {e}")


def demonstrate_retry_strategy():
    """Demonstrate retry strategy."""
    print("\n🔄 Retry Strategy Demonstration")
    print("=" * 50)
    
    from .control_structures import RetryStrategy
    
    # Create retry strategy
    strategy = RetryStrategy(
        max_attempts=5,
        delay=1.0,
        backoff_factor=2.0,
        max_delay=30.0,
        retry_on=["ConnectionError", "TimeoutError"]
    )
    
    print(f"Retry Strategy Configuration:")
    print(f"  Max Attempts: {strategy.max_attempts}")
    print(f"  Initial Delay: {strategy.delay}s")
    print(f"  Backoff Factor: {strategy.backoff_factor}")
    print(f"  Max Delay: {strategy.max_delay}s")
    print(f"  Retry On: {strategy.retry_on}")
    
    print(f"\nDelay Progression:")
    for attempt in range(1, strategy.max_attempts + 1):
        delay = strategy.get_delay(attempt)
        print(f"  Attempt {attempt}: {delay}s delay")
    
    # Test retry decisions
    print(f"\nRetry Decisions:")
    
    class MockConnectionError(Exception):
        pass
    
    class MockValueError(Exception):
        pass
    
    test_exceptions = [
        ("ConnectionError", MockConnectionError("Connection failed")),
        ("ValueError", MockValueError("Invalid value")),
        ("TimeoutError", TimeoutError("Request timed out"))
    ]
    
    for exc_name, exception in test_exceptions:
        for attempt in range(1, 6):
            should_retry = strategy.should_retry(exception, attempt)
            print(f"  {exc_name} on attempt {attempt}: {'RETRY' if should_retry else 'STOP'}")


def demonstrate_dependency_analysis():
    """Demonstrate dependency analysis."""
    print("\n🔗 Dependency Analysis Demonstration")
    print("=" * 50)
    
    from .control_structures import EnhancedTaskModel
    from nornflow.models import TaskModel
    
    # Create mock tasks with dependencies
    task_configs = [
        {"name": "task_a", "args": {}},  # No dependencies
        {"name": "task_b", "args": {}, "depends_on": "task_a"},
        {"name": "task_c", "args": {}, "depends_on": "task_a"},
        {"name": "task_d", "args": {}, "depends_on": ["task_b", "task_c"]},
        {"name": "task_e", "args": {}},  # No dependencies
    ]
    
    enhanced_tasks = []
    for config in task_configs:
        control_config = {k: v for k, v in config.items() if k in ["depends_on"]}
        task_config = {k: v for k, v in config.items() if k not in ["depends_on"]}
        
        task_model = TaskModel.create(task_config)
        enhanced_task = EnhancedTaskModel(task_model, control_config)
        enhanced_tasks.append(enhanced_task)
    
    # Analyze dependencies (simplified version)
    print("Task Dependencies:")
    for task in enhanced_tasks:
        deps = task.depends_on if task.depends_on else "None"
        print(f"  {task.name}: {deps}")
    
    print("\nExecution Order Analysis:")
    print("  Level 0 (No dependencies): task_a, task_e")
    print("  Level 1 (Depends on Level 0): task_b, task_c")
    print("  Level 2 (Depends on Level 1): task_d")


def main():
    """Main demonstration function."""
    print("🚀 Enhanced Workflow Control Integration Example")
    print("=" * 60)
    
    try:
        demonstrate_enhanced_workflow_parsing()
        demonstrate_condition_evaluation()
        demonstrate_retry_strategy()
        demonstrate_dependency_analysis()
        
        print("\n✅ All demonstrations completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Integrate enhanced workflow control with your NornFlow setup")
        print("2. Create workflows using the new control structures")
        print("3. Test with your network devices")
        print("4. Monitor execution statistics and performance")
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
