# Advanced Workflow Control Features for NornFlow

This module extends NornFlow with sophisticated workflow control capabilities, transforming it from a simple task executor into a powerful automation orchestrator.

## 🚀 Features Overview

### 1. **Conditional Execution**
Execute tasks based on dynamic conditions using Jinja2 expressions.

### 2. **Loops and Iteration**
Iterate over lists, dictionaries, or continue until conditions are met.

### 3. **Error Handling and Recovery**
Graceful error handling with rescue blocks and always-execute tasks.

### 4. **Retry Mechanisms**
Intelligent retry strategies with exponential backoff and condition-based retries.

### 5. **Task Dependencies**
Define task execution order and parallel execution groups.

## 📋 Control Structure Reference

### Conditional Execution

#### `when` - Execute if condition is true
```yaml
- name: backup_config
  args:
    backup_dir: "backups/{{ host.name }}"
  when: "{{ backup_enabled and host.platform == 'ios' }}"
```

#### `unless` - Execute if condition is false
```yaml
- name: skip_maintenance_mode
  args:
    msg: "Skipping maintenance mode"
  unless: "{{ maintenance_window_active }}"
```

#### Complex Conditions
```yaml
- name: deploy_config
  when: >
    {{
      host.data.config_ready | default(false) and
      backup_result.success | default(false) and
      host.platform in ['ios', 'nxos', 'eos']
    }}
```

### Loop Constructs

#### `loop` - Simple list iteration
```yaml
- name: configure_interface
  args:
    interface: "{{ item }}"
    description: "Configured via automation"
  loop: ["GigE0/1", "GigE0/2", "GigE0/3"]
```

#### `with_items` - Complex item iteration
```yaml
- name: test_connectivity
  args:
    method: "tcp"
    target: "{{ item.host }}"
    port: "{{ item.port }}"
  with_items:
    - { host: "192.168.1.1", port: 22, name: "SSH" }
    - { host: "192.168.1.1", port: 443, name: "HTTPS" }
    - { host: "192.168.1.1", port: 161, name: "SNMP" }
```

#### `until` - Loop until condition is met
```yaml
- name: wait_for_convergence
  args:
    command: "show ip ospf neighbor"
  until: "{{ 'Full' in command_result.output }}"
  set_to: command_result
```

#### Loop Variables
Inside loops, these variables are available:
- `{{ item }}` - Current loop item
- `{{ loop_index }}` - Current iteration index (0-based)

### Error Handling

#### `ignore_errors` - Continue on failure
```yaml
- name: optional_command
  args:
    command: "show mpls ldp neighbor"
  ignore_errors: true
```

#### `rescue` - Error recovery blocks
```yaml
- name: primary_backup
  args:
    backup_type: "full"
  rescue:
    - name: echo
      args:
        msg: "Full backup failed, trying incremental"
    - name: backup_config
      args:
        backup_type: "incremental"
```

#### `always` - Always execute regardless of failures
```yaml
- name: cleanup_temp_files
  args:
    command: "rm -f /tmp/automation_*"
  always: true
```

### Retry Mechanisms

#### Basic Retry
```yaml
- name: unstable_command
  args:
    command: "show tech-support"
  retry:
    max_attempts: 3
    delay: 5
```

#### Advanced Retry with Backoff
```yaml
- name: api_call
  args:
    endpoint: "https://{{ host.hostname }}/api/status"
  retry:
    max_attempts: 5
    delay: 2
    backoff_factor: 2.0
    max_delay: 30
    retry_on: ["ConnectionError", "TimeoutError", "HTTPError"]
```

#### Retry Configuration Options
- `max_attempts`: Maximum number of attempts (default: 3)
- `delay`: Initial delay between retries in seconds (default: 1.0)
- `backoff_factor`: Multiplier for delay on each retry (default: 2.0)
- `max_delay`: Maximum delay between retries (default: 60.0)
- `retry_on`: List of exception types to retry on

### Task Dependencies

#### Simple Dependencies
```yaml
- name: validate_config
  args:
    validation_commands: ["show running-config"]
  depends_on: "deploy_config"
```

#### Multiple Dependencies
```yaml
- name: final_report
  args:
    template: "summary_report.j2"
  depends_on: ["backup_config", "deploy_config", "validate_config"]
```

#### Parallel Execution Groups
Tasks with no dependencies can be executed in parallel:
```yaml
# These three tasks can run in parallel
- name: discover_neighbors
  depends_on: []
  
- name: discover_interfaces
  depends_on: []
  
- name: discover_device_info
  depends_on: []

# This task waits for all three above to complete
- name: generate_topology_map
  depends_on: ["discover_neighbors", "discover_interfaces", "discover_device_info"]
```

## 🔧 Implementation Architecture

### Core Components

1. **ConditionEvaluator**: Evaluates Jinja2 conditional expressions
2. **RetryStrategy**: Manages retry logic with backoff strategies
3. **LoopController**: Handles loop iteration and variable management
4. **WorkflowControlEngine**: Orchestrates enhanced task execution
5. **EnhancedTaskModel**: Extended task model with control flow properties
6. **EnhancedWorkflowExecutor**: Main execution engine with dependency resolution

### Integration with NornFlow

The enhanced workflow control integrates seamlessly with existing NornFlow:

```python
from enhancements.workflow_control.enhanced_workflow import EnhancedWorkflowExecutor
from enhancements.workflow_control.control_structures import parse_enhanced_workflow

# Parse enhanced workflow
enhanced_tasks = parse_enhanced_workflow(workflow_dict)

# Create enhanced executor
executor = EnhancedWorkflowExecutor(workflow, vars_manager, nornir_manager)

# Execute with advanced control
results = executor.execute_enhanced_workflow(
    tasks_catalog=tasks_catalog,
    enhanced_tasks=enhanced_tasks,
    parallel_execution=True,
    max_workers=4
)
```

## 📊 Execution Statistics

The enhanced workflow executor provides detailed execution statistics:

```python
{
    "execution_mode": "sequential",  # or "parallel"
    "task_results": [...],           # Individual task results
    "stats": {
        "total_tasks": 15,
        "executed_tasks": 12,
        "skipped_tasks": 2,
        "failed_tasks": 1,
        "retried_tasks": 3,
        "loop_iterations": 25
    },
    "success": true
}
```

## 🎯 Real-World Examples

### Network Device Onboarding
```yaml
workflow:
  name: "Enhanced Device Onboarding"
  tasks:
    # Test connectivity with retry
    - name: test_connectivity
      args:
        method: "ssh"
      retry:
        max_attempts: 5
        delay: 3
        backoff_factor: 1.5
    
    # Backup only if device is reachable
    - name: backup_config
      when: "{{ connectivity_test.success }}"
      depends_on: "test_connectivity"
    
    # Configure interfaces in loop
    - name: configure_interface
      args:
        interface: "{{ item.name }}"
        description: "{{ item.description }}"
        vlan: "{{ item.vlan }}"
      loop: "{{ host.data.interfaces }}"
    
    # Validate configuration
    - name: validate_config
      depends_on: "configure_interface"
      rescue:
        - name: restore_config
          args:
            backup_file: "{{ backup_result.backup_file }}"
    
    # Always generate report
    - name: generate_report
      always: true
```

### Multi-Platform Configuration
```yaml
workflow:
  name: "Multi-Platform Configuration"
  tasks:
    # Platform-specific tasks
    - name: configure_ios
      when: "{{ host.platform == 'ios' }}"
      
    - name: configure_nxos
      when: "{{ host.platform == 'nxos' }}"
      
    - name: configure_eos
      when: "{{ host.platform == 'eos' }}"
    
    # Universal validation
    - name: validate_all
      depends_on: ["configure_ios", "configure_nxos", "configure_eos"]
```

## 🚀 Benefits

1. **Intelligent Execution**: Conditional logic reduces unnecessary operations
2. **Robust Error Handling**: Graceful failure recovery and retry mechanisms
3. **Efficient Processing**: Parallel execution and dependency optimization
4. **Flexible Iteration**: Powerful loop constructs for repetitive tasks
5. **Comprehensive Monitoring**: Detailed execution statistics and reporting

## 🔄 Backward Compatibility

The enhanced workflow control is fully backward compatible with existing NornFlow workflows. Standard workflows continue to work unchanged, while new control structures are opt-in enhancements.

## 📈 Performance Considerations

- **Parallel Execution**: Independent tasks can run concurrently
- **Dependency Optimization**: Smart dependency resolution minimizes wait times
- **Conditional Skipping**: Unnecessary tasks are skipped based on conditions
- **Retry Intelligence**: Failed tasks are retried only when appropriate

The enhanced workflow control transforms NornFlow into a production-ready automation orchestrator capable of handling complex, real-world network automation scenarios! 🎯
