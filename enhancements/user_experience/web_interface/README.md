# NornFlow Web Interface

A modern, responsive web interface for NornFlow network automation workflows. This Flask-based application provides an intuitive GUI for network engineers to execute, monitor, and manage NornFlow workflows without command-line knowledge.

## Features

### 🎯 **Core Functionality**
- **Workflow Discovery**: Automatic discovery and display of available NornFlow workflows
- **Interactive Execution**: Web forms for workflow parameters with validation
- **Real-time Monitoring**: Live output streaming during workflow execution
- **Execution History**: Complete history with filtering and search capabilities
- **User Authentication**: Multi-user support with role-based access control

### 🚀 **User Experience**
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Real-time Updates**: WebSocket-based live updates for execution status
- **Dry-run Support**: Safe testing mode for all workflows
- **Variable Management**: Intelligent form generation from workflow variables
- **Execution Dashboard**: Overview of system status and recent activities

### 🔒 **Security & Management**
- **User Authentication**: Secure login with password hashing
- **Role-based Access**: Admin and user roles with different permissions
- **Execution Tracking**: Complete audit trail of all workflow executions
- **Session Management**: Secure session handling with configurable timeouts

## Quick Start

### 1. Installation

```bash
# Navigate to web interface directory
cd enhancements/user_experience/web_interface

# Install dependencies
pip install -r requirements.txt

# Set environment variables (optional)
export NORNFLOW_PATH="/opt/nornflow"
export WORKFLOWS_PATH="workflows"
export SECRET_KEY="your-secret-key-here"
```

### 2. Run the Application

```bash
# Development mode
python app.py

# Production mode with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 --worker-class eventlet app:app
```

### 3. Access the Interface

- Open your browser to `http://localhost:5000`
- Login with default credentials: `admin` / `admin`
- Change the default password after first login

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NORNFLOW_PATH` | `/opt/nornflow` | Path to NornFlow installation |
| `WORKFLOWS_PATH` | `workflows` | Path to workflow directory |
| `SECRET_KEY` | `auto-generated` | Flask secret key for sessions |
| `DATABASE_PATH` | `nornflow_web.db` | SQLite database file path |

### Configuration File

Create `config.yaml` for advanced configuration:

```yaml
# NornFlow Web Interface Configuration
app:
  host: "0.0.0.0"
  port: 5000
  debug: false
  secret_key: "your-secret-key"

nornflow:
  path: "/opt/nornflow"
  workflows_path: "workflows"
  config_file: "nornflow.yaml"

database:
  path: "nornflow_web.db"
  backup_interval: 3600  # seconds

security:
  session_timeout: 3600  # seconds
  max_login_attempts: 5
  password_min_length: 8

ui:
  items_per_page: 20
  auto_refresh_interval: 30  # seconds
  theme: "default"
```

## User Guide

### Dashboard
- **Overview**: System status, workflow statistics, and recent executions
- **Quick Actions**: Direct access to common tasks
- **Real-time Updates**: Live status updates for running executions

### Workflows
- **Browse Workflows**: View all available NornFlow workflows
- **Workflow Details**: Detailed information about tasks and variables
- **Execute Workflows**: Interactive forms for workflow execution

### Execution
- **Parameter Forms**: Auto-generated forms based on workflow variables
- **Dry-run Mode**: Safe testing without making actual changes
- **Live Monitoring**: Real-time output streaming during execution
- **Status Tracking**: Visual indicators for execution progress

### History
- **Execution Log**: Complete history of all workflow executions
- **Filtering**: Filter by user, workflow, status, or date range
- **Details View**: Full execution details including output and variables

## API Endpoints

### Authentication
- `POST /login` - User login
- `GET /logout` - User logout

### Workflows
- `GET /api/workflows` - List all workflows
- `GET /api/workflow/<file>` - Get workflow details
- `POST /execute` - Execute workflow

### Executions
- `GET /api/executions` - List execution history
- `GET /execution/<id>` - Get execution details

### Real-time Events (WebSocket)
- `execution_started` - Workflow execution started
- `execution_output` - Real-time output line
- `execution_completed` - Execution finished
- `execution_error` - Execution error occurred

## Development

### Project Structure
```
web_interface/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # Jinja2 templates
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── dashboard.html    # Main dashboard
│   ├── workflow_detail.html  # Workflow execution
│   └── ...
├── static/               # Static assets (CSS, JS, images)
└── config.yaml          # Configuration file
```

### Adding Features

1. **New Routes**: Add Flask routes in `app.py`
2. **Templates**: Create Jinja2 templates in `templates/`
3. **Static Assets**: Add CSS/JS files in `static/`
4. **Database**: Extend SQLite schema in `init_database()`

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test
pytest test_workflows.py
```

## Production Deployment

### Using Gunicorn + Nginx

1. **Install Gunicorn**:
```bash
pip install gunicorn eventlet
```

2. **Create Gunicorn config** (`gunicorn.conf.py`):
```python
bind = "127.0.0.1:5000"
workers = 4
worker_class = "eventlet"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
```

3. **Run with Gunicorn**:
```bash
gunicorn -c gunicorn.conf.py app:app
```

4. **Configure Nginx**:
```nginx
server {
    listen 80;
    server_name nornflow.company.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Using Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--worker-class", "eventlet", "app:app"]
```

## Security Considerations

1. **Change Default Credentials**: Update admin password immediately
2. **Use HTTPS**: Configure SSL/TLS in production
3. **Secure Secret Key**: Use a strong, random secret key
4. **Database Security**: Protect SQLite database file permissions
5. **Network Security**: Use firewall rules to restrict access
6. **Regular Updates**: Keep dependencies updated

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check if NornFlow is installed and accessible
2. **Permission Denied**: Verify file permissions for workflows directory
3. **Database Locked**: Ensure only one instance is running
4. **WebSocket Issues**: Check firewall settings for WebSocket connections

### Logs

- Application logs: Check console output or configure logging
- Execution logs: Stored in NornFlow logs directory
- Database logs: SQLite operations logged to application log

### Debug Mode

Enable debug mode for development:
```bash
export FLASK_DEBUG=1
python app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is part of the NornFlow NetOps Enhancement Suite.
