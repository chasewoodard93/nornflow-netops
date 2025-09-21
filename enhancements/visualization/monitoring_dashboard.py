#!/usr/bin/env python3
"""
Monitoring Dashboard for NornFlow Workflow Visualization.

This module provides a comprehensive web-based monitoring dashboard:
- Real-time workflow execution monitoring
- Performance analytics and metrics
- Workflow history and trends
- Interactive workflow visualization
- System health monitoring

Features:
- Flask-based web application
- WebSocket real-time updates
- Interactive charts and graphs
- Workflow performance analysis
- System resource monitoring
"""

import json
import asyncio
import threading
import time
import psutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory, g
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging

from .workflow_visualizer import WorkflowVisualizer, TaskStatus
from ..security.middleware import SecurityMiddleware
from ..security.rbac import Permission, ResourceType

logger = logging.getLogger(__name__)


class MonitoringDashboard:
    """
    Web-based monitoring dashboard for NornFlow workflows.
    
    Provides:
    - Real-time execution monitoring
    - Performance analytics dashboard
    - Workflow history and trends
    - Interactive visualization interface
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize monitoring dashboard."""
        self.config = config or {}
        self.visualizer = WorkflowVisualizer(config)
        
        # Flask application setup
        self.app = Flask(__name__, 
                        template_folder=str(Path(__file__).parent / "templates"),
                        static_folder=str(Path(__file__).parent / "static"))
        self.app.config['SECRET_KEY'] = self.config.get('secret_key', 'nornflow-monitoring-secret')
        
        # SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Security middleware setup
        security_config = self.config.get("security", {})
        if security_config.get("enabled", True):
            self.security = SecurityMiddleware(self.app, security_config)
        else:
            self.security = None

        # Dashboard configuration
        self.host = self.config.get("host", "0.0.0.0")
        self.port = self.config.get("port", 5000)
        self.debug = self.config.get("debug", False)

        # Data storage
        self.execution_history = []
        self.system_metrics = []
        self.active_executions = {}

        # Monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None

        # Setup routes
        self._setup_routes()
        self._setup_socketio_events()

        # Active monitoring sessions
        self.monitoring_sessions: Dict[str, Dict[str, Any]] = {}
    
    def _setup_routes(self):
        """Setup Flask routes for the dashboard."""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template('dashboard.html')
        
        @self.app.route('/workflow/<path:workflow_file>')
        def workflow_visualization(workflow_file):
            """Workflow visualization page."""
            workflow_path = Path(workflow_file)
            if not workflow_path.exists():
                return jsonify({"error": "Workflow file not found"}), 404
            
            workflow_info = self.visualizer.parse_workflow_structure(workflow_path)
            visualization_html = self.visualizer.generate_d3_visualization(workflow_info)
            
            return visualization_html
        
        @self.app.route('/api/workflows')
        @self._require_permission(Permission.WORKFLOW_READ)
        def list_workflows():
            """List available workflows."""
            workflows = []

            # Scan for workflow files
            workflow_dirs = self.config.get('workflow_dirs', ['workflows'])
            for workflow_dir in workflow_dirs:
                workflow_path = Path(workflow_dir)
                if workflow_path.exists():
                    for yaml_file in workflow_path.rglob('*.yaml'):
                        try:
                            workflow_info = self.visualizer.parse_workflow_structure(yaml_file)
                            workflows.append({
                                "file": str(yaml_file),
                                "name": workflow_info["name"],
                                "description": workflow_info["description"],
                                "tasks": len(workflow_info["tasks"]),
                                "complexity": workflow_info["complexity_score"]
                            })
                        except Exception as e:
                            logger.warning(f"Failed to parse workflow {yaml_file}: {str(e)}")
            
            return jsonify(workflows)
        
        @self.app.route('/api/executions')
        @self._require_permission(Permission.WORKFLOW_READ)
        def list_executions():
            """List workflow executions."""
            executions = []
            
            # Active executions
            for execution in self.visualizer.active_executions.values():
                executions.append(self.visualizer.get_execution_summary(execution.execution_id))
            
            # Recent history (last 50)
            for execution in self.visualizer.execution_history[-50:]:
                executions.append(self.visualizer.get_execution_summary(execution.execution_id))
            
            return jsonify(executions)
        
        @self.app.route('/api/execution/<execution_id>')
        @self._require_permission(Permission.WORKFLOW_READ)
        def get_execution(execution_id):
            """Get detailed execution information."""
            summary = self.visualizer.get_execution_summary(execution_id)
            return jsonify(summary)
        
        @self.app.route('/api/metrics')
        @self._require_permission(Permission.SYSTEM_MONITOR)
        def get_metrics():
            """Get performance metrics."""
            metrics = self.visualizer.get_performance_metrics()
            
            # Add system metrics
            system_metrics = self._get_system_metrics()
            metrics.update(system_metrics)
            
            return jsonify(metrics)
        
        @self.app.route('/api/workflow/parse', methods=['POST'])
        @self._require_permission(Permission.WORKFLOW_READ)
        def parse_workflow():
            """Parse workflow file and return structure."""
            data = request.get_json()
            workflow_file = data.get('workflow_file')
            
            if not workflow_file:
                return jsonify({"error": "workflow_file required"}), 400
            
            workflow_path = Path(workflow_file)
            if not workflow_path.exists():
                return jsonify({"error": "Workflow file not found"}), 404
            
            try:
                workflow_info = self.visualizer.parse_workflow_structure(workflow_path)
                return jsonify(workflow_info)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/execution/start', methods=['POST'])
        @self._require_permission(Permission.WORKFLOW_EXECUTE)
        def start_execution_monitoring():
            """Start monitoring a workflow execution."""
            data = request.get_json()
            
            execution_id = data.get('execution_id')
            workflow_file = data.get('workflow_file')
            variables = data.get('variables', {})
            user = data.get('user')
            dry_run = data.get('dry_run', False)
            
            if not execution_id or not workflow_file:
                return jsonify({"error": "execution_id and workflow_file required"}), 400
            
            workflow_path = Path(workflow_file)
            if not workflow_path.exists():
                return jsonify({"error": "Workflow file not found"}), 404
            
            try:
                execution = self.visualizer.start_execution_monitoring(
                    execution_id, workflow_path, variables, user, dry_run
                )
                
                # Notify connected clients
                self.socketio.emit('execution_started', {
                    'execution_id': execution_id,
                    'workflow_name': execution.workflow_name
                })
                
                return jsonify({"success": True, "execution_id": execution_id})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/execution/<execution_id>/task/<task_id>/update', methods=['POST'])
        @self._require_permission(Permission.WORKFLOW_EXECUTE)
        def update_task_status(execution_id, task_id):
            """Update task status during execution."""
            data = request.get_json()
            
            status_str = data.get('status')
            if not status_str:
                return jsonify({"error": "status required"}), 400
            
            try:
                status = TaskStatus(status_str)
            except ValueError:
                return jsonify({"error": "Invalid status"}), 400
            
            start_time = None
            end_time = None
            
            if data.get('start_time'):
                start_time = datetime.fromisoformat(data['start_time'])
            if data.get('end_time'):
                end_time = datetime.fromisoformat(data['end_time'])
            
            self.visualizer.update_task_status(
                execution_id, task_id, status, start_time, end_time,
                data.get('error_message'), data.get('output')
            )
            
            # Notify connected clients
            self.socketio.emit('task_updated', {
                'execution_id': execution_id,
                'task_id': task_id,
                'status': status_str,
                'start_time': data.get('start_time'),
                'end_time': data.get('end_time'),
                'duration': data.get('duration'),
                'error_message': data.get('error_message')
            })
            
            return jsonify({"success": True})
        
        @self.app.route('/api/execution/<execution_id>/complete', methods=['POST'])
        @self._require_permission(Permission.WORKFLOW_EXECUTE)
        def complete_execution(execution_id):
            """Complete workflow execution monitoring."""
            data = request.get_json()
            
            status_str = data.get('status', 'success')
            try:
                status = TaskStatus(status_str)
            except ValueError:
                return jsonify({"error": "Invalid status"}), 400
            
            self.visualizer.complete_execution(execution_id, status)
            
            # Notify connected clients
            self.socketio.emit('execution_completed', {
                'execution_id': execution_id,
                'status': status_str
            })
            
            return jsonify({"success": True})
    
    def _setup_socketio_events(self):
        """Setup SocketIO event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            logger.info(f"Client connected: {request.sid}")
            emit('connected', {'message': 'Connected to NornFlow monitoring'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            logger.info(f"Client disconnected: {request.sid}")
        
        @self.socketio.on('join_execution')
        def handle_join_execution(data):
            """Join execution monitoring room."""
            execution_id = data.get('execution_id')
            if execution_id:
                join_room(execution_id)
                emit('joined_execution', {'execution_id': execution_id})
        
        @self.socketio.on('leave_execution')
        def handle_leave_execution(data):
            """Leave execution monitoring room."""
            execution_id = data.get('execution_id')
            if execution_id:
                leave_room(execution_id)
                emit('left_execution', {'execution_id': execution_id})
        
        @self.socketio.on('request_metrics')
        def handle_request_metrics():
            """Send current metrics to client."""
            metrics = self.visualizer.get_performance_metrics()
            system_metrics = self._get_system_metrics()
            metrics.update(system_metrics)
            emit('metrics_update', metrics)
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        try:
            import psutil
            
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            network = psutil.net_io_counters()
            
            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3),
                    "network_bytes_sent": network.bytes_sent,
                    "network_bytes_recv": network.bytes_recv
                }
            }
        except ImportError:
            logger.warning("psutil not available, system metrics disabled")
            return {"system": {"error": "psutil not available"}}
        except Exception as e:
            logger.error(f"Failed to get system metrics: {str(e)}")
            return {"system": {"error": str(e)}}
    
    def start_monitoring_server(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        """
        Start the monitoring dashboard server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
        """
        logger.info(f"Starting NornFlow monitoring dashboard on {host}:{port}")
        
        # Start metrics collection in background
        self._start_metrics_collection()
        
        # Start the Flask-SocketIO server
        self.socketio.run(self.app, host=host, port=port, debug=debug)
    
    def _start_metrics_collection(self):
        """Start background metrics collection."""
        def collect_metrics():
            while True:
                try:
                    # Collect and broadcast metrics every 30 seconds
                    metrics = self.visualizer.get_performance_metrics()
                    system_metrics = self._get_system_metrics()
                    metrics.update(system_metrics)
                    
                    self.socketio.emit('metrics_update', metrics)
                    
                    # Sleep for 30 seconds
                    threading.Event().wait(30)
                except Exception as e:
                    logger.error(f"Metrics collection error: {str(e)}")
                    threading.Event().wait(60)  # Wait longer on error
        
        # Start metrics collection thread
        metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
        metrics_thread.start()

    def _require_permission(self, permission: Permission, resource_type: ResourceType = ResourceType.WORKFLOW):
        """Helper method to create permission decorator."""
        if self.security:
            return self.security.require_permission(permission, resource_type)
        else:
            # No security enabled, allow all access
            def decorator(f):
                return f
            return decorator

    def _require_role(self, *roles: str):
        """Helper method to create role decorator."""
        if self.security:
            return self.security.require_role(*roles)
        else:
            # No security enabled, allow all access
            def decorator(f):
                return f
            return decorator

    def get_app(self):
        """Get Flask application instance."""
        return self.app
    
    def get_socketio(self):
        """Get SocketIO instance."""
        return self.socketio
