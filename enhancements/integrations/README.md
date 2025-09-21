# Enhanced Integration Framework

The Enhanced Integration Framework provides comprehensive integration capabilities for NornFlow, enabling seamless connectivity with external systems and platforms commonly used in network operations.

## 🔗 Supported Integrations

### 1. **NetBox Integration** (`netbox_integration.py`)
**Purpose**: IPAM (IP Address Management) and DCIM (Data Center Infrastructure Management)

**Key Features**:
- Dynamic inventory from NetBox
- Device information retrieval and updates
- IP address management (get available IPs, assign IPs)
- Configuration context integration
- Interface synchronization

**Tasks Available**:
- `netbox_get_device` - Retrieve device information
- `netbox_update_device` - Update device properties
- `netbox_get_available_ip` - Get available IP addresses
- `netbox_assign_ip` - Assign IP address to device
- `netbox_get_config_context` - Get configuration context
- `netbox_sync_interfaces` - Synchronize interface data
- `netbox_get_site_devices` - Get all devices from a site

### 2. **Git Integration** (`git_integration.py`)
**Purpose**: Configuration version control and change tracking

**Key Features**:
- Configuration backup to Git repositories
- Commit history and change tracking
- Branch management for different environments
- Configuration drift detection
- Automated rollback capabilities

**Tasks Available**:
- `git_commit_config` - Commit configuration to repository
- `git_create_branch` - Create new Git branch
- `git_switch_branch` - Switch between branches
- `git_get_diff` - Get differences between commits
- `git_rollback_config` - Rollback to previous configuration
- `git_tag_release` - Create release tags
- `git_get_history` - Get commit history
- `git_detect_drift` - Detect configuration drift

### 3. **Monitoring Integration** (`monitoring_integration.py`)
**Purpose**: Integration with monitoring and network management platforms

#### **Grafana Integration**
- Dashboard creation and management
- Alert management and silencing
- Metrics visualization

**Tasks Available**:
- `grafana_create_dashboard` - Create Grafana dashboard
- `grafana_silence_alert` - Silence alerts during maintenance

#### **Prometheus Integration**
- Metrics collection and querying
- Push metrics to Pushgateway
- Alert rule management

**Tasks Available**:
- `prometheus_query` - Execute PromQL queries
- `prometheus_push_metrics` - Push metrics to Pushgateway

#### **Infoblox Integration**
- DNS/DHCP/IPAM management
- Host record management
- Network administration

**Tasks Available**:
- `infoblox_get_next_ip` - Get next available IP
- `infoblox_create_host_record` - Create DNS host record

### 4. **ITSM Integration** (`itsm_integration.py`)
**Purpose**: IT Service Management and change control

#### **ServiceNow Integration**
- Change request management
- Incident tracking
- CMDB integration

**Tasks Available**:
- `servicenow_create_change` - Create change request
- `servicenow_update_change` - Update change request status

#### **Jira Integration**
- Issue tracking and project management
- Workflow automation
- Change documentation

**Tasks Available**:
- `jira_create_issue` - Create Jira issue
- `jira_update_issue` - Update issue details
- `jira_transition_issue` - Transition issue status

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install optional integration dependencies
pip install pynetbox GitPython requests

# Or install specific integrations
pip install pynetbox  # For NetBox
pip install GitPython  # For Git
pip install requests   # For API-based integrations
```

### 2. Configure Integrations

Create configuration in your workflow or host data:

```yaml
# In workflow vars or host data
netbox_config:
  url: "https://netbox.company.com"
  token: "your-api-token"
  ssl_verify: true

git_config:
  repo_path: "/opt/network-configs"
  author_name: "NornFlow Automation"
  author_email: "automation@company.com"

servicenow_config:
  instance_url: "https://company.service-now.com"
  username: "automation_user"
  password: "secure_password"
```

### 3. Use in Workflows

```yaml
tasks:
  # Create change request
  - name: servicenow_create_change
    args:
      short_description: "Network maintenance for {{ host.name }}"
      description: "Automated configuration update"
      servicenow_config: "{{ servicenow_config }}"
    set_to: change_request
  
  # Backup configuration to Git
  - name: git_commit_config
    args:
      config_content: "{{ current_config }}"
      device_name: "{{ host.name }}"
      commit_message: "Backup before change {{ change_request.change_number }}"
      git_config: "{{ git_config }}"
    set_to: backup_commit
  
  # Get device info from NetBox
  - name: netbox_get_device
    args:
      device_name: "{{ host.name }}"
      netbox_config: "{{ netbox_config }}"
    set_to: device_info
```

## 🔧 Configuration Reference

### Environment Variables

Set these environment variables for secure credential management:

```bash
# NetBox
export NETBOX_TOKEN="your-netbox-api-token"

# Git (if using HTTPS with credentials)
export GIT_USERNAME="your-git-username"
export GIT_PASSWORD="your-git-password"

# ServiceNow
export SNOW_USER="your-servicenow-username"
export SNOW_PASS="your-servicenow-password"

# Jira
export JIRA_USER="your-jira-username"
export JIRA_TOKEN="your-jira-api-token"

# Grafana
export GRAFANA_API_KEY="your-grafana-api-key"

# Infoblox
export INFOBLOX_USER="your-infoblox-username"
export INFOBLOX_PASS="your-infoblox-password"
```

### Integration Configuration Examples

#### NetBox Configuration
```yaml
netbox_config:
  url: "https://netbox.company.com"
  token: "{{ env.NETBOX_TOKEN }}"
  ssl_verify: true
  timeout: 30
```

#### Git Configuration
```yaml
git_config:
  repo_path: "/opt/network-configs"
  author_name: "NornFlow Automation"
  author_email: "nornflow@company.com"
  default_branch: "main"
  config_subdir: "configs"
```

#### ServiceNow Configuration
```yaml
servicenow_config:
  instance_url: "https://company.service-now.com"
  username: "{{ env.SNOW_USER }}"
  password: "{{ env.SNOW_PASS }}"
  timeout: 30
  ssl_verify: true
```

#### Jira Configuration
```yaml
jira_config:
  server_url: "https://company.atlassian.net"
  username: "{{ env.JIRA_USER }}"
  api_token: "{{ env.JIRA_TOKEN }}"  # Use API token for cloud
  # password: "{{ env.JIRA_PASS }}"  # Use password for server
  timeout: 30
  ssl_verify: true
```

## 🛡️ Security Best Practices

1. **Use Environment Variables**: Store sensitive credentials in environment variables
2. **API Tokens**: Prefer API tokens over passwords when available
3. **SSL Verification**: Always use SSL verification in production
4. **Least Privilege**: Use service accounts with minimal required permissions
5. **Credential Rotation**: Regularly rotate API tokens and passwords

## 🔍 Error Handling

The integration framework includes comprehensive error handling:

- **Dependency Checking**: Graceful fallback when optional dependencies are missing
- **Connection Testing**: Built-in connection testing for all integrations
- **API Error Handling**: Proper handling of API errors with meaningful messages
- **Retry Logic**: Automatic retry for transient failures (when appropriate)

## 📊 Monitoring and Metrics

### Prometheus Metrics

The framework can push metrics to Prometheus for monitoring:

```yaml
- name: prometheus_push_metrics
  args:
    job_name: "nornflow_operations"
    metrics:
      nornflow_task_duration_seconds: "{{ task_duration }}"
      nornflow_task_success: "{{ 1 if success else 0 }}"
      nornflow_devices_processed: "{{ device_count }}"
```

### Grafana Dashboards

Create dashboards to visualize:
- Task execution metrics
- Success/failure rates
- Device deployment status
- Change request tracking

## 🔄 Workflow Patterns

### Change Management Pattern
```yaml
# 1. Create change request
# 2. Backup current config
# 3. Deploy new config
# 4. Validate deployment
# 5. Update change request
# 6. Create tracking issue
```

### Configuration Management Pattern
```yaml
# 1. Get device info from NetBox
# 2. Generate config from template
# 3. Backup to Git
# 4. Deploy configuration
# 5. Commit new config to Git
# 6. Update NetBox status
```

### Monitoring Integration Pattern
```yaml
# 1. Silence alerts before maintenance
# 2. Perform operations
# 3. Push metrics to monitoring
# 4. Validate monitoring data
# 5. Re-enable alerts
```

## 🧪 Testing Integrations

Test integration connectivity:

```python
from enhancements.integrations.netbox_integration import NetBoxIntegration

config = {
    "url": "https://netbox.company.com",
    "token": "your-token"
}

integration = NetBoxIntegration(config)
result = integration.test_connection()
print(result)
```

## 📚 Examples

See `sample_workflows/integration_examples.yaml` for comprehensive examples demonstrating:
- Multi-system integration workflows
- Error handling and rollback scenarios
- Change management integration
- Monitoring and alerting integration

## 🤝 Contributing

To add new integrations:

1. Create new integration module in `enhancements/integrations/`
2. Use the `@register_integration` decorator
3. Implement `BaseIntegration` class
4. Add task functions with `@require_dependency` decorator
5. Update this README with documentation
6. Add examples to sample workflows

## 📋 Requirements

- **Python 3.8+**
- **NornFlow** (base framework)
- **Optional Dependencies**:
  - `pynetbox` - For NetBox integration
  - `GitPython` - For Git integration
  - `requests` - For API-based integrations

## 🔗 Related Documentation

- [NornFlow Core Documentation](../../README.md)
- [Network Tasks Documentation](../network_tasks/README.md)
- [Workflow Control Documentation](../workflow_control/README.md)
- [Sample Workflows](../../sample_workflows/)
