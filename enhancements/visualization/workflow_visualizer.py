#!/usr/bin/env python3
"""
Workflow Visualization and Monitoring System for NornFlow.

This module provides comprehensive workflow visualization capabilities:
- Interactive workflow dependency graphs
- Real-time execution monitoring
- Performance metrics and analytics
- Workflow optimization recommendations
- Visual workflow builder interface

Features:
- D3.js-based interactive graphs
- WebSocket real-time updates
- Execution timeline visualization
- Performance bottleneck identification
- Workflow complexity analysis
"""

import json
import yaml
import asyncio
import websockets
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import networkx as nx
from jinja2 import Template

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class TaskNode:
    """Represents a task node in the workflow graph."""
    id: str
    name: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    dependencies: List[str] = None
    variables: Dict[str, Any] = None
    error_message: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.variables is None:
            self.variables = {}


@dataclass
class WorkflowExecution:
    """Represents a workflow execution instance."""
    execution_id: str
    workflow_name: str
    workflow_file: str
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None
    tasks: Dict[str, TaskNode] = None
    variables: Dict[str, Any] = None
    user: Optional[str] = None
    dry_run: bool = False
    
    def __post_init__(self):
        if self.tasks is None:
            self.tasks = {}
        if self.variables is None:
            self.variables = {}


class WorkflowVisualizer:
    """
    Comprehensive workflow visualization and monitoring system.
    
    Provides:
    - Interactive workflow graphs with D3.js
    - Real-time execution monitoring
    - Performance analytics and optimization
    - Visual workflow builder interface
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize workflow visualizer."""
        self.config = config or {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        self.websocket_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # Performance tracking
        self.performance_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_duration": 0.0,
            "task_performance": {}
        }
    
    def parse_workflow_structure(self, workflow_file: Path) -> Dict[str, Any]:
        """
        Parse workflow file and extract structure for visualization.
        
        Args:
            workflow_file: Path to workflow YAML file
            
        Returns:
            Workflow structure with tasks, dependencies, and metadata
        """
        try:
            with open(workflow_file, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            # Extract basic workflow information
            workflow_info = {
                "name": workflow_data.get("name", workflow_file.stem),
                "description": workflow_data.get("description", ""),
                "variables": workflow_data.get("vars", {}),
                "tasks": [],
                "dependencies": {},
                "complexity_score": 0
            }
            
            # Parse tasks and build dependency graph
            tasks = workflow_data.get("tasks", [])
            dependency_graph = nx.DiGraph()
            
            for i, task in enumerate(tasks):
                task_id = task.get("name", f"task_{i}")
                task_info = {
                    "id": task_id,
                    "name": task.get("name", task_id),
                    "task_type": task.get("task", "unknown"),
                    "description": task.get("description", ""),
                    "variables": task.get("vars", {}),
                    "conditions": self._extract_conditions(task),
                    "loops": self._extract_loops(task),
                    "error_handling": self._extract_error_handling(task),
                    "dependencies": task.get("depends_on", []),
                    "position": {"x": 0, "y": 0}  # Will be calculated by layout algorithm
                }
                
                workflow_info["tasks"].append(task_info)
                dependency_graph.add_node(task_id, **task_info)
                
                # Add dependency edges
                for dep in task.get("depends_on", []):
                    dependency_graph.add_edge(dep, task_id)
                    if dep not in workflow_info["dependencies"]:
                        workflow_info["dependencies"][dep] = []
                    workflow_info["dependencies"][dep].append(task_id)
            
            # Calculate layout positions using networkx
            if dependency_graph.nodes():
                try:
                    pos = nx.spring_layout(dependency_graph, k=3, iterations=50)
                    for task in workflow_info["tasks"]:
                        if task["id"] in pos:
                            task["position"]["x"] = pos[task["id"]][0] * 500 + 250
                            task["position"]["y"] = pos[task["id"]][1] * 300 + 150
                except:
                    # Fallback to simple linear layout
                    for i, task in enumerate(workflow_info["tasks"]):
                        task["position"]["x"] = 100 + (i % 4) * 200
                        task["position"]["y"] = 100 + (i // 4) * 150
            
            # Calculate complexity score
            workflow_info["complexity_score"] = self._calculate_complexity_score(workflow_info)
            
            return workflow_info
        
        except Exception as e:
            logger.error(f"Failed to parse workflow structure: {str(e)}")
            return {
                "name": "Error",
                "description": f"Failed to parse workflow: {str(e)}",
                "tasks": [],
                "dependencies": {},
                "complexity_score": 0
            }
    
    def _extract_conditions(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract conditional logic from task."""
        conditions = []
        
        if "when" in task:
            conditions.append({
                "type": "when",
                "condition": task["when"],
                "description": f"Execute when: {task['when']}"
            })
        
        if "unless" in task:
            conditions.append({
                "type": "unless", 
                "condition": task["unless"],
                "description": f"Skip unless: {task['unless']}"
            })
        
        return conditions
    
    def _extract_loops(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract loop constructs from task."""
        loops = []
        
        if "loop" in task:
            loops.append({
                "type": "loop",
                "items": task["loop"],
                "description": f"Loop over: {task['loop']}"
            })
        
        if "with_items" in task:
            loops.append({
                "type": "with_items",
                "items": task["with_items"],
                "description": f"Iterate over items: {task['with_items']}"
            })
        
        if "until" in task:
            loops.append({
                "type": "until",
                "condition": task["until"],
                "description": f"Repeat until: {task['until']}"
            })
        
        return loops
    
    def _extract_error_handling(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract error handling configuration from task."""
        error_handling = {
            "ignore_errors": task.get("ignore_errors", False),
            "rescue": task.get("rescue", []),
            "always": task.get("always", []),
            "retry_count": task.get("retry_count", 0),
            "retry_delay": task.get("retry_delay", 1)
        }
        
        return error_handling
    
    def _calculate_complexity_score(self, workflow_info: Dict[str, Any]) -> int:
        """Calculate workflow complexity score."""
        score = 0
        
        # Base score for number of tasks
        score += len(workflow_info["tasks"]) * 2
        
        # Add points for dependencies
        for task in workflow_info["tasks"]:
            score += len(task["dependencies"]) * 3
            score += len(task["conditions"]) * 5
            score += len(task["loops"]) * 8
            
            if task["error_handling"]["rescue"]:
                score += len(task["error_handling"]["rescue"]) * 4
            if task["error_handling"]["always"]:
                score += len(task["error_handling"]["always"]) * 2
        
        return score
    
    def generate_d3_visualization(self, workflow_info: Dict[str, Any]) -> str:
        """
        Generate D3.js visualization HTML for workflow.
        
        Args:
            workflow_info: Parsed workflow structure
            
        Returns:
            HTML string with embedded D3.js visualization
        """
        template = Template('''
<!DOCTYPE html>
<html>
<head>
    <title>{{ workflow_info.name }} - Workflow Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .workflow-container { width: 100%; height: 600px; border: 1px solid #ccc; }
        .task-node { cursor: pointer; }
        .task-node.pending { fill: #f0f0f0; stroke: #999; }
        .task-node.running { fill: #ffd700; stroke: #ff8c00; }
        .task-node.success { fill: #90ee90; stroke: #008000; }
        .task-node.failed { fill: #ffcccb; stroke: #ff0000; }
        .task-node.skipped { fill: #d3d3d3; stroke: #696969; }
        .dependency-link { stroke: #999; stroke-width: 2; marker-end: url(#arrowhead); }
        .task-label { font-size: 12px; text-anchor: middle; }
        .tooltip { position: absolute; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px; pointer-events: none; }
        .controls { margin-bottom: 20px; }
        .controls button { margin-right: 10px; padding: 5px 15px; }
        .metrics { display: flex; gap: 20px; margin-bottom: 20px; }
        .metric-card { background: #f5f5f5; padding: 15px; border-radius: 5px; min-width: 150px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #333; }
        .metric-label { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <h1>{{ workflow_info.name }}</h1>
    <p>{{ workflow_info.description }}</p>
    
    <div class="metrics">
        <div class="metric-card">
            <div class="metric-value">{{ workflow_info.tasks|length }}</div>
            <div class="metric-label">Total Tasks</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ workflow_info.complexity_score }}</div>
            <div class="metric-label">Complexity Score</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="execution-time">--</div>
            <div class="metric-label">Execution Time</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="success-rate">--</div>
            <div class="metric-label">Success Rate</div>
        </div>
    </div>
    
    <div class="controls">
        <button onclick="resetView()">Reset View</button>
        <button onclick="toggleLayout()">Toggle Layout</button>
        <button onclick="exportSVG()">Export SVG</button>
        <button onclick="showPerformanceAnalysis()">Performance Analysis</button>
    </div>
    
    <div class="workflow-container">
        <svg id="workflow-svg" width="100%" height="100%">
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
                </marker>
            </defs>
        </svg>
    </div>
    
    <div id="tooltip" class="tooltip" style="display: none;"></div>
    
    <script>
        const workflowData = {{ workflow_info | tojson }};
        let svg, g, simulation;
        let currentLayout = 'force';
        
        function initVisualization() {
            svg = d3.select("#workflow-svg");
            g = svg.append("g");
            
            // Add zoom behavior
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on("zoom", (event) => {
                    g.attr("transform", event.transform);
                });
            
            svg.call(zoom);
            
            renderWorkflow();
            
            // Connect to WebSocket for real-time updates
            connectWebSocket();
        }
        
        function renderWorkflow() {
            // Clear existing content
            g.selectAll("*").remove();
            
            const tasks = workflowData.tasks;
            const dependencies = [];
            
            // Build dependency links
            tasks.forEach(task => {
                task.dependencies.forEach(dep => {
                    const sourceTask = tasks.find(t => t.id === dep);
                    if (sourceTask) {
                        dependencies.push({
                            source: sourceTask,
                            target: task
                        });
                    }
                });
            });
            
            // Create links
            const links = g.selectAll(".dependency-link")
                .data(dependencies)
                .enter()
                .append("line")
                .attr("class", "dependency-link");
            
            // Create task nodes
            const nodes = g.selectAll(".task-node")
                .data(tasks)
                .enter()
                .append("g")
                .attr("class", "task-node")
                .attr("transform", d => `translate(${d.position.x}, ${d.position.y})`);
            
            // Add circles for tasks
            nodes.append("circle")
                .attr("r", 30)
                .attr("class", d => `task-node ${d.status || 'pending'}`);
            
            // Add task labels
            nodes.append("text")
                .attr("class", "task-label")
                .attr("dy", "0.35em")
                .text(d => d.name.length > 10 ? d.name.substring(0, 10) + "..." : d.name);
            
            // Add tooltips
            nodes.on("mouseover", showTooltip)
                  .on("mouseout", hideTooltip)
                  .on("click", showTaskDetails);
            
            // Update link positions
            links.attr("x1", d => d.source.position.x)
                 .attr("y1", d => d.source.position.y)
                 .attr("x2", d => d.target.position.x)
                 .attr("y2", d => d.target.position.y);
        }
        
        function showTooltip(event, d) {
            const tooltip = d3.select("#tooltip");
            tooltip.style("display", "block")
                   .style("left", (event.pageX + 10) + "px")
                   .style("top", (event.pageY - 10) + "px")
                   .html(`
                       <strong>${d.name}</strong><br>
                       Type: ${d.task_type}<br>
                       Status: ${d.status || 'pending'}<br>
                       Dependencies: ${d.dependencies.length}<br>
                       Conditions: ${d.conditions.length}<br>
                       Loops: ${d.loops.length}
                   `);
        }
        
        function hideTooltip() {
            d3.select("#tooltip").style("display", "none");
        }
        
        function showTaskDetails(event, d) {
            alert(`Task: ${d.name}\nType: ${d.task_type}\nDescription: ${d.description}`);
        }
        
        function connectWebSocket() {
            // WebSocket connection for real-time updates
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}/ws/workflow-updates`);
            
            ws.onmessage = function(event) {
                const update = JSON.parse(event.data);
                updateTaskStatus(update);
            };
        }
        
        function updateTaskStatus(update) {
            // Update task status in real-time
            const task = workflowData.tasks.find(t => t.id === update.task_id);
            if (task) {
                task.status = update.status;
                task.start_time = update.start_time;
                task.end_time = update.end_time;
                task.duration = update.duration;
                
                // Update visualization
                d3.select(`[data-task-id="${update.task_id}"] circle`)
                  .attr("class", `task-node ${update.status}`);
                
                // Update metrics
                updateMetrics();
            }
        }
        
        function updateMetrics() {
            // Update execution metrics
            const completedTasks = workflowData.tasks.filter(t => t.status === 'success' || t.status === 'failed');
            const successfulTasks = workflowData.tasks.filter(t => t.status === 'success');
            
            if (completedTasks.length > 0) {
                const successRate = (successfulTasks.length / completedTasks.length * 100).toFixed(1);
                d3.select("#success-rate .metric-value").text(successRate + "%");
            }
            
            const totalDuration = workflowData.tasks
                .filter(t => t.duration)
                .reduce((sum, t) => sum + t.duration, 0);
            
            if (totalDuration > 0) {
                d3.select("#execution-time .metric-value").text(totalDuration.toFixed(1) + "s");
            }
        }
        
        function resetView() {
            svg.transition().duration(750).call(
                d3.zoom().transform,
                d3.zoomIdentity
            );
        }
        
        function toggleLayout() {
            currentLayout = currentLayout === 'force' ? 'hierarchical' : 'force';
            renderWorkflow();
        }
        
        function exportSVG() {
            const svgElement = document.getElementById("workflow-svg");
            const serializer = new XMLSerializer();
            const svgString = serializer.serializeToString(svgElement);
            
            const blob = new Blob([svgString], {type: "image/svg+xml"});
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement("a");
            a.href = url;
            a.download = `${workflowData.name}-workflow.svg`;
            a.click();
            
            URL.revokeObjectURL(url);
        }
        
        function showPerformanceAnalysis() {
            // Show performance analysis modal
            alert("Performance analysis feature coming soon!");
        }
        
        // Initialize visualization when page loads
        document.addEventListener("DOMContentLoaded", initVisualization);
    </script>
</body>
</html>
        ''')
        
        return template.render(workflow_info=workflow_info)
    
    def start_execution_monitoring(self, execution_id: str, workflow_file: Path, variables: Dict[str, Any], user: str = None, dry_run: bool = False) -> WorkflowExecution:
        """
        Start monitoring a workflow execution.
        
        Args:
            execution_id: Unique execution identifier
            workflow_file: Path to workflow file
            variables: Execution variables
            user: User executing the workflow
            dry_run: Whether this is a dry run
            
        Returns:
            WorkflowExecution instance for tracking
        """
        workflow_info = self.parse_workflow_structure(workflow_file)
        
        # Create execution instance
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_name=workflow_info["name"],
            workflow_file=str(workflow_file),
            start_time=datetime.now(),
            variables=variables,
            user=user,
            dry_run=dry_run
        )
        
        # Initialize task nodes
        for task_info in workflow_info["tasks"]:
            task_node = TaskNode(
                id=task_info["id"],
                name=task_info["name"],
                task_type=task_info["task_type"],
                dependencies=task_info["dependencies"],
                variables=task_info["variables"]
            )
            execution.tasks[task_info["id"]] = task_node
        
        self.active_executions[execution_id] = execution
        
        logger.info(f"Started monitoring execution {execution_id} for workflow {workflow_info['name']}")
        
        return execution
    
    def update_task_status(self, execution_id: str, task_id: str, status: TaskStatus, start_time: datetime = None, end_time: datetime = None, error_message: str = None, output: Dict[str, Any] = None):
        """
        Update task status during execution.
        
        Args:
            execution_id: Execution identifier
            task_id: Task identifier
            status: New task status
            start_time: Task start time
            end_time: Task end time
            error_message: Error message if failed
            output: Task output data
        """
        if execution_id not in self.active_executions:
            logger.warning(f"Execution {execution_id} not found for task update")
            return
        
        execution = self.active_executions[execution_id]
        
        if task_id not in execution.tasks:
            logger.warning(f"Task {task_id} not found in execution {execution_id}")
            return
        
        task = execution.tasks[task_id]
        task.status = status
        
        if start_time:
            task.start_time = start_time
        if end_time:
            task.end_time = end_time
            if task.start_time:
                task.duration = (end_time - task.start_time).total_seconds()
        
        if error_message:
            task.error_message = error_message
        if output:
            task.output = output
        
        # Broadcast update to WebSocket clients
        self._broadcast_task_update(execution_id, task)
        
        logger.debug(f"Updated task {task_id} status to {status.value} in execution {execution_id}")
    
    def complete_execution(self, execution_id: str, status: TaskStatus):
        """
        Complete workflow execution monitoring.
        
        Args:
            execution_id: Execution identifier
            status: Final execution status
        """
        if execution_id not in self.active_executions:
            logger.warning(f"Execution {execution_id} not found for completion")
            return
        
        execution = self.active_executions[execution_id]
        execution.status = status
        execution.end_time = datetime.now()
        
        if execution.start_time:
            execution.total_duration = (execution.end_time - execution.start_time).total_seconds()
        
        # Move to history
        self.execution_history.append(execution)
        del self.active_executions[execution_id]
        
        # Update performance metrics
        self._update_performance_metrics(execution)
        
        logger.info(f"Completed execution {execution_id} with status {status.value}")
    
    def _broadcast_task_update(self, execution_id: str, task: TaskNode):
        """Broadcast task update to WebSocket clients."""
        update_data = {
            "execution_id": execution_id,
            "task_id": task.id,
            "status": task.status.value,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "duration": task.duration,
            "error_message": task.error_message
        }
        
        # Send to all connected WebSocket clients
        message = json.dumps(update_data)
        disconnected_clients = set()
        
        for client in self.websocket_clients:
            try:
                asyncio.create_task(client.send(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        self.websocket_clients -= disconnected_clients
    
    def _update_performance_metrics(self, execution: WorkflowExecution):
        """Update performance metrics with completed execution."""
        self.performance_metrics["total_executions"] += 1
        
        if execution.status == TaskStatus.SUCCESS:
            self.performance_metrics["successful_executions"] += 1
        elif execution.status == TaskStatus.FAILED:
            self.performance_metrics["failed_executions"] += 1
        
        # Update average duration
        if execution.total_duration:
            total_duration = (self.performance_metrics["average_duration"] * 
                            (self.performance_metrics["total_executions"] - 1) + 
                            execution.total_duration)
            self.performance_metrics["average_duration"] = total_duration / self.performance_metrics["total_executions"]
        
        # Update task performance metrics
        for task in execution.tasks.values():
            if task.duration:
                task_type = task.task_type
                if task_type not in self.performance_metrics["task_performance"]:
                    self.performance_metrics["task_performance"][task_type] = {
                        "total_executions": 0,
                        "total_duration": 0.0,
                        "average_duration": 0.0,
                        "success_count": 0,
                        "failure_count": 0
                    }
                
                metrics = self.performance_metrics["task_performance"][task_type]
                metrics["total_executions"] += 1
                metrics["total_duration"] += task.duration
                metrics["average_duration"] = metrics["total_duration"] / metrics["total_executions"]
                
                if task.status == TaskStatus.SUCCESS:
                    metrics["success_count"] += 1
                elif task.status == TaskStatus.FAILED:
                    metrics["failure_count"] += 1
    
    def get_execution_summary(self, execution_id: str) -> Dict[str, Any]:
        """Get execution summary for API endpoints."""
        execution = self.active_executions.get(execution_id) or next(
            (e for e in self.execution_history if e.execution_id == execution_id), None
        )
        
        if not execution:
            return {"error": "Execution not found"}
        
        return {
            "execution_id": execution.execution_id,
            "workflow_name": execution.workflow_name,
            "status": execution.status.value,
            "start_time": execution.start_time.isoformat() if execution.start_time else None,
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "total_duration": execution.total_duration,
            "user": execution.user,
            "dry_run": execution.dry_run,
            "tasks": {
                task_id: {
                    "name": task.name,
                    "status": task.status.value,
                    "duration": task.duration,
                    "error_message": task.error_message
                }
                for task_id, task in execution.tasks.items()
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self.performance_metrics.copy()
    
    async def websocket_handler(self, websocket, path):
        """WebSocket handler for real-time updates."""
        self.websocket_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.websocket_clients.discard(websocket)
