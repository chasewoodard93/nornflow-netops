#!/usr/bin/env python3
"""
NornFlow Web Interface.

A lightweight Flask-based web interface for NornFlow workflows:
- Workflow discovery and management
- Interactive workflow builder
- Execution dashboard with real-time output
- Variable management and validation
- Execution history and reporting
- User authentication and RBAC

This provides a user-friendly web interface for network engineers
who prefer GUI over command-line tools.
"""

import os
import json
import yaml
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nornflow-web-interface-secret')
app.config['NORNFLOW_PATH'] = os.environ.get('NORNFLOW_PATH', '/opt/nornflow')
app.config['WORKFLOWS_PATH'] = os.environ.get('WORKFLOWS_PATH', 'workflows')
app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'nornflow_web.db')

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Global execution tracking
active_executions = {}


class NornFlowWebInterface:
    """Main class for NornFlow web interface functionality."""
    
    def __init__(self, app_config: Dict[str, Any]):
        """Initialize web interface with configuration."""
        self.nornflow_path = Path(app_config['NORNFLOW_PATH'])
        self.workflows_path = Path(app_config['WORKFLOWS_PATH'])
        self.database_path = app_config['DATABASE_PATH']
        
        # Initialize database
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for execution history and users."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Executions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_name TEXT NOT NULL,
                username TEXT NOT NULL,
                variables TEXT,
                dry_run BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'running',
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                output TEXT,
                return_code INTEGER,
                execution_id TEXT UNIQUE
            )
        ''')
        
        # Create default admin user if none exists
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            admin_hash = generate_password_hash('admin')
            cursor.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                ('admin', admin_hash, 'admin')
            )
        
        conn.commit()
        conn.close()
    
    def discover_workflows(self) -> List[Dict[str, Any]]:
        """Discover available NornFlow workflows."""
        workflows = []
        
        if not self.workflows_path.exists():
            return workflows
        
        for workflow_file in self.workflows_path.glob("*.yaml"):
            try:
                with open(workflow_file, 'r') as f:
                    workflow_data = yaml.safe_load(f)
                
                workflow = workflow_data.get("workflow", {})
                workflows.append({
                    "file": workflow_file.name,
                    "name": workflow.get("name", workflow_file.stem),
                    "description": workflow.get("description", "No description available"),
                    "variables": workflow.get("vars", {}),
                    "tasks": len(workflow.get("tasks", [])),
                    "modified": datetime.fromtimestamp(workflow_file.stat().st_mtime).isoformat()
                })
            
            except Exception as e:
                logger.error(f"Error reading workflow {workflow_file}: {str(e)}")
                workflows.append({
                    "file": workflow_file.name,
                    "name": workflow_file.stem,
                    "description": f"Error reading workflow: {str(e)}",
                    "variables": {},
                    "tasks": 0,
                    "modified": datetime.fromtimestamp(workflow_file.stat().st_mtime).isoformat(),
                    "error": True
                })
        
        return sorted(workflows, key=lambda x: x["name"])
    
    def get_workflow_details(self, workflow_file: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific workflow."""
        workflow_path = self.workflows_path / workflow_file
        
        if not workflow_path.exists():
            return None
        
        try:
            with open(workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            workflow = workflow_data.get("workflow", {})
            
            return {
                "file": workflow_file,
                "name": workflow.get("name", workflow_path.stem),
                "description": workflow.get("description", "No description available"),
                "variables": workflow.get("vars", {}),
                "tasks": workflow.get("tasks", []),
                "domains": workflow.get("domains", []),
                "filters": workflow.get("filters", {}),
                "raw_content": yaml.dump(workflow_data, default_flow_style=False)
            }
        
        except Exception as e:
            logger.error(f"Error reading workflow details {workflow_file}: {str(e)}")
            return None
    
    def execute_workflow(self, workflow_file: str, variables: Dict[str, Any], 
                        username: str, dry_run: bool = True) -> str:
        """Execute a NornFlow workflow and return execution ID."""
        execution_id = f"{username}_{workflow_file}_{int(time.time())}"
        
        # Store execution in database
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO executions (workflow_name, username, variables, dry_run, execution_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (workflow_file, username, json.dumps(variables), dry_run, execution_id))
        conn.commit()
        conn.close()
        
        # Start execution in background thread
        thread = threading.Thread(
            target=self._execute_workflow_thread,
            args=(execution_id, workflow_file, variables, username, dry_run)
        )
        thread.daemon = True
        thread.start()
        
        return execution_id
    
    def _execute_workflow_thread(self, execution_id: str, workflow_file: str, 
                                variables: Dict[str, Any], username: str, dry_run: bool):
        """Execute workflow in background thread with real-time output."""
        try:
            # Prepare NornFlow command
            cmd = [
                str(self.nornflow_path / "bin" / "nornflow"),
                "run",
                workflow_file.replace(".yaml", "").replace(".yml", ""),
                "--config", str(self.nornflow_path / "config" / "nornflow.yaml")
            ]
            
            if dry_run:
                cmd.append("--dry-run")
            
            if variables.get("verbosity"):
                cmd.extend(["--verbosity", str(variables["verbosity"])])
            
            if variables.get("limit"):
                cmd.extend(["--limit", variables["limit"]])
            
            # Set up environment with variables
            env = os.environ.copy()
            for var_name, var_value in variables.items():
                if var_name not in ["verbosity", "limit"]:
                    env[f"NORNFLOW_{var_name.upper()}"] = str(var_value)
            
            # Track active execution
            active_executions[execution_id] = {
                "process": None,
                "start_time": datetime.now(),
                "username": username,
                "workflow": workflow_file
            }
            
            # Execute workflow
            socketio.emit('execution_started', {
                'execution_id': execution_id,
                'workflow': workflow_file,
                'dry_run': dry_run
            }, room=f"execution_{execution_id}")
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.workflows_path.parent),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            active_executions[execution_id]["process"] = process
            
            # Stream output in real-time
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if line:
                    output_lines.append(line.rstrip())
                    socketio.emit('execution_output', {
                        'execution_id': execution_id,
                        'line': line.rstrip()
                    }, room=f"execution_{execution_id}")
            
            # Wait for completion
            return_code = process.wait()
            end_time = datetime.now()
            
            # Update database
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE executions 
                SET status = ?, end_time = ?, output = ?, return_code = ?
                WHERE execution_id = ?
            ''', (
                'completed' if return_code == 0 else 'failed',
                end_time.isoformat(),
                '\n'.join(output_lines),
                return_code,
                execution_id
            ))
            conn.commit()
            conn.close()
            
            # Notify completion
            socketio.emit('execution_completed', {
                'execution_id': execution_id,
                'return_code': return_code,
                'duration': str(end_time - active_executions[execution_id]["start_time"])
            }, room=f"execution_{execution_id}")
            
            # Clean up
            if execution_id in active_executions:
                del active_executions[execution_id]
        
        except Exception as e:
            logger.error(f"Execution error for {execution_id}: {str(e)}")
            
            # Update database with error
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE executions 
                SET status = ?, end_time = ?, output = ?
                WHERE execution_id = ?
            ''', ('error', datetime.now().isoformat(), str(e), execution_id))
            conn.commit()
            conn.close()
            
            # Notify error
            socketio.emit('execution_error', {
                'execution_id': execution_id,
                'error': str(e)
            }, room=f"execution_{execution_id}")
            
            # Clean up
            if execution_id in active_executions:
                del active_executions[execution_id]
    
    def get_execution_history(self, username: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        if username:
            cursor.execute('''
                SELECT * FROM executions 
                WHERE username = ? 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (username, limit))
        else:
            cursor.execute('''
                SELECT * FROM executions 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (limit,))
        
        columns = [description[0] for description in cursor.description]
        executions = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return executions
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):  # user[2] is password_hash
            return {
                "id": user[0],
                "username": user[1],
                "role": user[3],
                "created_at": user[4]
            }
        
        return None


# Initialize web interface
web_interface = NornFlowWebInterface(app.config)


# Authentication decorator
def login_required(f):
    """Decorator to require login for routes."""
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# Flask Routes
@app.route('/')
def index():
    """Main dashboard page."""
    if 'user' not in session:
        return redirect(url_for('login'))

    workflows = web_interface.discover_workflows()
    recent_executions = web_interface.get_execution_history(
        username=session['user']['username'],
        limit=10
    )

    return render_template('dashboard.html',
                         workflows=workflows,
                         recent_executions=recent_executions,
                         user=session['user'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = web_interface.authenticate_user(username, password)
        if user:
            session['user'] = user
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """User logout."""
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/workflows')
@login_required
def workflows():
    """Workflows management page."""
    workflows = web_interface.discover_workflows()
    return render_template('workflows.html', workflows=workflows, user=session['user'])


@app.route('/workflow/<workflow_file>')
@login_required
def workflow_detail(workflow_file):
    """Workflow detail and execution page."""
    workflow = web_interface.get_workflow_details(workflow_file)
    if not workflow:
        flash('Workflow not found!', 'error')
        return redirect(url_for('workflows'))

    return render_template('workflow_detail.html', workflow=workflow, user=session['user'])


@app.route('/execute', methods=['POST'])
@login_required
def execute_workflow():
    """Execute a workflow."""
    data = request.get_json()
    workflow_file = data.get('workflow_file')
    variables = data.get('variables', {})
    dry_run = data.get('dry_run', True)

    if not workflow_file:
        return jsonify({'success': False, 'message': 'Workflow file required'})

    try:
        execution_id = web_interface.execute_workflow(
            workflow_file,
            variables,
            session['user']['username'],
            dry_run
        )

        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'message': 'Workflow execution started'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/execution/<execution_id>')
@login_required
def execution_detail(execution_id):
    """Execution detail page."""
    executions = web_interface.get_execution_history()
    execution = next((e for e in executions if e['execution_id'] == execution_id), None)

    if not execution:
        flash('Execution not found!', 'error')
        return redirect(url_for('history'))

    return render_template('execution_detail.html', execution=execution, user=session['user'])


@app.route('/history')
@login_required
def history():
    """Execution history page."""
    executions = web_interface.get_execution_history(
        username=session['user']['username'] if session['user']['role'] != 'admin' else None,
        limit=100
    )
    return render_template('history.html', executions=executions, user=session['user'])


@app.route('/api/workflows')
@login_required
def api_workflows():
    """API endpoint for workflows."""
    workflows = web_interface.discover_workflows()
    return jsonify(workflows)


@app.route('/api/workflow/<workflow_file>')
@login_required
def api_workflow_detail(workflow_file):
    """API endpoint for workflow details."""
    workflow = web_interface.get_workflow_details(workflow_file)
    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404
    return jsonify(workflow)


@app.route('/api/executions')
@login_required
def api_executions():
    """API endpoint for execution history."""
    executions = web_interface.get_execution_history(
        username=session['user']['username'] if session['user']['role'] != 'admin' else None
    )
    return jsonify(executions)


# SocketIO Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    if 'user' not in session:
        return False

    emit('connected', {'message': 'Connected to NornFlow Web Interface'})


@socketio.on('join_execution')
def handle_join_execution(data):
    """Join execution room for real-time updates."""
    if 'user' not in session:
        return False

    execution_id = data.get('execution_id')
    if execution_id:
        join_room(f"execution_{execution_id}")
        emit('joined_execution', {'execution_id': execution_id})


@socketio.on('leave_execution')
def handle_leave_execution(data):
    """Leave execution room."""
    execution_id = data.get('execution_id')
    if execution_id:
        leave_room(f"execution_{execution_id}")
        emit('left_execution', {'execution_id': execution_id})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    pass


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)

    # Create static directory if it doesn't exist
    static_dir = Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)

    # Run the application
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
