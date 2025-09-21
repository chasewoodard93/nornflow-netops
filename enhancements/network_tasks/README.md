# Network Automation Tasks for NornFlow

This directory contains comprehensive network automation tasks that extend NornFlow's capabilities for network device management and operations.

## Task Categories

### 1. Device Interaction (`device_interaction/`)

**Connection Tasks** (`connection_tasks.py`):
- `test_connectivity()` - Test network connectivity using ping, TCP, SSH, or API
- `execute_command()` - Execute commands on network devices with TextFSM support
- `test_api_payload()` - Test API payloads with Jinja2 template support (NEW)

### 2. Configuration Management (`configuration/`)

**Configuration Tasks** (`config_tasks.py`):
- `deploy_config()` - Deploy configuration via CLI with backup, validation, and rollback
- `deploy_config_api()` - Deploy configuration via REST API with safety features (NEW)
- `backup_config()` - Backup device configurations with timestamps
- `validate_config()` - Validate configuration with custom checks
- `restore_config()` - Restore configuration from backup files

### 3. Network Discovery (`discovery/`)

**Discovery Tasks** (`discovery_tasks.py`):
- `discover_neighbors()` - Discover network neighbors using LLDP/CDP
- `discover_interfaces()` - Discover device interfaces and their properties
- `discover_device_info()` - Comprehensive device information discovery

## Installation and Setup

### Prerequisites

1. **Install required dependencies**:
```bash
# Core dependencies (already included in NornFlow)
pip install nornir nornir-utils

# Network automation plugins (recommended)
pip install nornir-netmiko nornir-napalm

# Optional: TextFSM for structured output parsing
pip install textfsm ntc-templates
```

2. **Add tasks to your NornFlow project**:
```bash
# Copy the network_tasks directory to your NornFlow project
cp -r enhancements/network_tasks /path/to/your/nornflow/project/tasks/
```

3. **Update your nornflow.yaml**:
```yaml
local_tasks_dirs:
  - "tasks"
  - "tasks/network_tasks"  # Add this line
```

## Usage Examples

### Basic Device Connectivity Test

```yaml
workflow:
  name: "Test Network Connectivity"
  tasks:
    - name: test_connectivity
      args:
        method: "ssh"
        timeout: 10
```

### Configuration Backup and Deploy

```yaml
workflow:
  name: "Safe Configuration Deployment"
  tasks:
    # Backup current configuration
    - name: backup_config
      args:
        backup_dir: "backups/{{ '%Y-%m-%d' | strftime }}"
        include_timestamp: true
      set_to: backup_result
    
    # Deploy new configuration with validation
    - name: deploy_config
      args:
        template_file: "templates/{{ host.platform }}/base_config.j2"
        template_vars:
          management_vlan: 100
          snmp_community: "{{ snmp_ro_community }}"
        backup_before: false  # Already backed up above
        validate_after: true
        rollback_on_error: true
```

### Network Discovery and Documentation

```yaml
workflow:
  name: "Network Discovery and Documentation"
  tasks:
    # Discover device information
    - name: discover_device_info
      args:
        include_hardware: true
        include_software: true
        include_inventory: true
      set_to: device_info
    
    # Discover network neighbors
    - name: discover_neighbors
      args:
        protocol: "both"  # LLDP and CDP
        include_details: true
      set_to: neighbors
    
    # Discover interfaces
    - name: discover_interfaces
      args:
        interface_type: "all"
        include_status: true
        include_config: true
      set_to: interfaces
    
    # Generate documentation
    - name: write_file
      args:
        filename: "documentation/{{ host.name }}_discovery.json"
        content: |
          {
            "device_info": {{ device_info | to_json }},
            "neighbors": {{ neighbors | to_json }},
            "interfaces": {{ interfaces | to_json }}
          }
```

### Advanced Configuration Management

```yaml
workflow:
  name: "Advanced Configuration Management"
  vars:
    config_templates:
      ios: "templates/ios/interface_config.j2"
      nxos: "templates/nxos/interface_config.j2"
      eos: "templates/eos/interface_config.j2"
  
  tasks:
    # Test connectivity first
    - name: test_connectivity
      args:
        method: "ssh"
        timeout: 5
    
    # Deploy configuration based on platform
    - name: deploy_config
      args:
        template_file: "{{ config_templates[host.platform] }}"
        template_vars:
          interfaces: "{{ host.data.interfaces }}"
          vlans: "{{ host.data.vlans }}"
        backup_before: true
        validate_after: true
        commit: true
        rollback_on_error: true
```

## Task Reference

### Device Interaction Tasks

#### `test_connectivity`
Tests network connectivity to devices using various methods.

**Parameters:**
- `timeout` (int): Connection timeout in seconds (default: 5)
- `count` (int): Number of ping attempts (default: 3)
- `method` (str): Test method - 'ping', 'tcp', or 'ssh' (default: 'ping')

**Returns:**
- `success` (bool): Whether connectivity test passed
- `response_time_ms` (float): Response time in milliseconds
- `output` (str): Test output

#### `execute_command`
Executes commands on network devices with optional TextFSM parsing.

**Parameters:**
- `command` (str): Command to execute
- `use_textfsm` (bool): Use TextFSM for structured output (default: False)
- `textfsm_template` (str): Specific TextFSM template
- `expect_string` (str): Expected string in output
- `delay_factor` (float): Command execution delay factor (default: 1.0)

**Returns:**
- `output` (str/list): Command output (parsed if TextFSM used)
- `parsed` (bool): Whether output was parsed

### Configuration Management Tasks

#### `deploy_config`
Deploys configuration with comprehensive safety features.

**Parameters:**
- `config` (str): Configuration string
- `config_file` (str): Path to configuration file
- `template_file` (str): Path to Jinja2 template
- `template_vars` (dict): Variables for template rendering
- `backup_before` (bool): Backup before deployment (default: True)
- `validate_after` (bool): Validate after deployment (default: True)
- `commit` (bool): Commit configuration (default: True)
- `rollback_on_error` (bool): Rollback on validation failure (default: True)

**Returns:**
- `config_deployed` (bool): Whether configuration was deployed
- `validation_passed` (bool): Whether validation passed
- `committed` (bool): Whether configuration was committed
- `backup_file` (str): Path to backup file (if created)

#### `backup_config`
Creates timestamped backups of device configurations.

**Parameters:**
- `backup_dir` (str): Directory for backups (default: "backups")
- `filename_template` (str): Template for filename (default: "{host}_{timestamp}.cfg")
- `include_timestamp` (bool): Include timestamp in filename (default: True)
- `config_type` (str): Configuration type - 'running' or 'startup' (default: "running")

**Returns:**
- `backup_file` (str): Path to created backup file
- `size_bytes` (int): Size of backup file in bytes

### Discovery Tasks

#### `discover_neighbors`
Discovers network neighbors using LLDP, CDP, or both protocols.

**Parameters:**
- `protocol` (str): Protocol to use - 'lldp', 'cdp', or 'both' (default: "lldp")
- `parse_output` (bool): Parse output into structured data (default: True)
- `include_details` (bool): Include detailed neighbor information (default: True)

**Returns:**
- `neighbors` (list): List of discovered neighbors
- `total_neighbors` (int): Total number of neighbors found
- `protocols_used` (list): Protocols successfully used

#### `discover_interfaces`
Discovers device interfaces and their properties.

**Parameters:**
- `interface_type` (str): Type of interfaces - 'all', 'physical', or 'logical' (default: "all")
- `include_status` (bool): Include interface status (default: True)
- `include_config` (bool): Include interface configuration (default: False)

**Returns:**
- `interfaces` (list): List of discovered interfaces
- `total_interfaces` (int): Total number of interfaces
- `up_interfaces` (int): Number of up interfaces

#### `discover_device_info`
Discovers comprehensive device information including hardware and software details.

**Parameters:**
- `include_hardware` (bool): Include hardware information (default: True)
- `include_software` (bool): Include software information (default: True)
- `include_inventory` (bool): Include detailed inventory (default: False)

**Returns:**
- `hardware` (dict): Hardware information
- `software` (dict): Software information
- `inventory` (list): Detailed inventory (if requested)

## Platform Support

These tasks are designed to work with multiple network platforms:

- **Cisco IOS/IOS-XE**: Full support
- **Cisco NX-OS**: Full support
- **Arista EOS**: Full support
- **Juniper Junos**: Basic support
- **Other platforms**: Basic support with fallback commands

## Error Handling

All tasks include comprehensive error handling:

- **Connection failures**: Graceful handling with detailed error messages
- **Command failures**: Proper exception handling and reporting
- **Validation failures**: Automatic rollback when configured
- **Platform differences**: Automatic command adaptation

## Best Practices

1. **Always test connectivity** before running configuration tasks
2. **Use backup_before=True** for configuration changes
3. **Enable validation** for critical configuration deployments
4. **Use dry_run mode** to test workflows before execution
5. **Implement proper error handling** in your workflows
6. **Use TextFSM parsing** for structured data when available

## Extending the Tasks

To add new network automation tasks:

1. Create a new Python file in the appropriate subdirectory
2. Follow the NornFlow task signature pattern
3. Include comprehensive error handling
4. Add proper type annotations and docstrings
5. Test with multiple platforms
6. Update this README with usage examples

## Troubleshooting

### Common Issues

**ImportError: netmiko not available**
```bash
pip install nornir-netmiko
```

**TextFSM parsing fails**
```bash
pip install textfsm ntc-templates
```

**Platform not supported**
- Check platform string in your inventory
- Add platform-specific command mappings
- Use fallback commands for unknown platforms

**Connection timeouts**
- Increase timeout values
- Check network connectivity
- Verify credentials and platform settings
