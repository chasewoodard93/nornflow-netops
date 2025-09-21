"""
API Payload Testing Framework for NornFlow.

This module provides comprehensive testing capabilities for API payloads and Jinja2 templates:
- Template validation and rendering testing
- API payload structure validation
- Mock API server for testing without real endpoints
- Variable injection and testing scenarios
- JSON schema validation for API responses
- Performance testing for template rendering

This enables developers to thoroughly test API integrations and templates
before deploying workflows to production environments.
"""

import json
import yaml
import requests
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
from jinja2 import Environment, FileSystemLoader, Template, TemplateError
from jsonschema import validate, ValidationError
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@dataclass
class TestScenario:
    """Test scenario for API payload testing."""
    name: str
    description: str
    variables: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    timeout: float = 5.0
    validate_schema: bool = True


@dataclass
class TemplateTestResult:
    """Result of template testing."""
    template_name: str
    scenario_name: str
    success: bool
    rendered_output: Optional[str] = None
    error_message: Optional[str] = None
    render_time: float = 0.0
    validation_errors: List[str] = None


@dataclass
class APITestResult:
    """Result of API testing."""
    endpoint: str
    method: str
    scenario_name: str
    success: bool
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None
    response_time: float = 0.0
    error_message: Optional[str] = None
    validation_errors: List[str] = None


class MockAPIServer:
    """Mock API server for testing API payloads without real endpoints."""
    
    def __init__(self, port: int = 8888):
        """Initialize mock API server."""
        self.port = port
        self.server = None
        self.thread = None
        self.responses = {}
        self.requests_log = []
        
    def add_mock_response(self, path: str, method: str, response: Dict[str, Any], status_code: int = 200):
        """Add a mock response for a specific endpoint."""
        key = f"{method.upper()}:{path}"
        self.responses[key] = {
            "response": response,
            "status_code": status_code
        }
    
    def start(self):
        """Start the mock API server."""
        class MockHandler(BaseHTTPRequestHandler):
            def __init__(self, mock_server, *args, **kwargs):
                self.mock_server = mock_server
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                self._handle_request("GET")
            
            def do_POST(self):
                self._handle_request("POST")
            
            def do_PUT(self):
                self._handle_request("PUT")
            
            def do_DELETE(self):
                self._handle_request("DELETE")
            
            def _handle_request(self, method):
                # Log the request
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
                
                request_log = {
                    "timestamp": datetime.now().isoformat(),
                    "method": method,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body
                }
                self.mock_server.requests_log.append(request_log)
                
                # Find matching response
                key = f"{method}:{self.path.split('?')[0]}"
                if key in self.mock_server.responses:
                    mock_response = self.mock_server.responses[key]
                    
                    self.send_response(mock_response["status_code"])
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    response_json = json.dumps(mock_response["response"])
                    self.wfile.write(response_json.encode('utf-8'))
                else:
                    # Default 404 response
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    error_response = {"error": f"Mock endpoint not found: {method} {self.path}"}
                    self.wfile.write(json.dumps(error_response).encode('utf-8'))
            
            def log_message(self, format, *args):
                # Suppress default logging
                pass
        
        # Create handler with reference to mock server
        handler = lambda *args, **kwargs: MockHandler(self, *args, **kwargs)
        
        self.server = HTTPServer(('localhost', self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Mock API server started on http://localhost:{self.port}")
    
    def stop(self):
        """Stop the mock API server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            if self.thread:
                self.thread.join()
        logger.info("Mock API server stopped")
    
    def get_requests_log(self) -> List[Dict[str, Any]]:
        """Get log of all requests received by the mock server."""
        return self.requests_log.copy()
    
    def clear_requests_log(self):
        """Clear the requests log."""
        self.requests_log.clear()


class APIPayloadTestingFramework:
    """
    Comprehensive testing framework for API payloads and Jinja2 templates.
    
    Provides methods to:
    - Test Jinja2 template rendering with various variable sets
    - Validate API payload structure and content
    - Run mock API servers for testing
    - Generate test reports and documentation
    - Performance testing for template rendering
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize API testing framework.
        
        Args:
            config: Configuration for testing framework
        """
        self.config = config or {}
        self.templates_dir = Path(self.config.get("templates_dir", "templates"))
        self.schemas_dir = Path(self.config.get("schemas_dir", "schemas"))
        self.test_results_dir = Path(self.config.get("test_results_dir", "test_results"))
        
        # Initialize Jinja2 environment
        if self.templates_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True
            )
        else:
            self.jinja_env = Environment()
        
        # Ensure directories exist
        self.test_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock server instance
        self.mock_server = None
    
    def test_template_rendering(self, template_file: Path, test_scenarios: List[TestScenario]) -> List[TemplateTestResult]:
        """
        Test Jinja2 template rendering with multiple scenarios.
        
        Args:
            template_file: Path to Jinja2 template file
            test_scenarios: List of test scenarios with different variables
            
        Returns:
            List of template test results
        """
        results = []
        
        try:
            # Load template
            if template_file.is_absolute():
                with open(template_file, 'r') as f:
                    template_content = f.read()
                template = Template(template_content)
                template_name = template_file.name
            else:
                template = self.jinja_env.get_template(str(template_file))
                template_name = str(template_file)
            
            # Test each scenario
            for scenario in test_scenarios:
                logger.info(f"Testing template '{template_name}' with scenario '{scenario.name}'")
                
                start_time = time.time()
                result = TemplateTestResult(
                    template_name=template_name,
                    scenario_name=scenario.name,
                    success=False,
                    validation_errors=[]
                )
                
                try:
                    # Render template with scenario variables
                    rendered = template.render(**scenario.variables)
                    render_time = time.time() - start_time
                    
                    result.rendered_output = rendered
                    result.render_time = render_time
                    result.success = True
                    
                    # Validate rendered output if expected output provided
                    if scenario.expected_output:
                        validation_errors = self._validate_rendered_output(
                            rendered, scenario.expected_output
                        )
                        result.validation_errors = validation_errors
                        if validation_errors:
                            result.success = False
                    
                    logger.info(f"✅ Template '{template_name}' scenario '{scenario.name}' passed")
                
                except TemplateError as e:
                    result.error_message = f"Template rendering error: {str(e)}"
                    result.render_time = time.time() - start_time
                    logger.error(f"❌ Template '{template_name}' scenario '{scenario.name}' failed: {str(e)}")
                
                except Exception as e:
                    result.error_message = f"Unexpected error: {str(e)}"
                    result.render_time = time.time() - start_time
                    logger.error(f"❌ Template '{template_name}' scenario '{scenario.name}' error: {str(e)}")
                
                results.append(result)
        
        except Exception as e:
            # Template loading error
            error_result = TemplateTestResult(
                template_name=str(template_file),
                scenario_name="template_loading",
                success=False,
                error_message=f"Template loading error: {str(e)}"
            )
            results.append(error_result)
            logger.error(f"❌ Failed to load template '{template_file}': {str(e)}")
        
        return results
    
    def test_api_endpoints(self, api_config: Dict[str, Any], test_scenarios: List[TestScenario]) -> List[APITestResult]:
        """
        Test API endpoints with various payloads.
        
        Args:
            api_config: API configuration including base URL, endpoints, etc.
            test_scenarios: List of test scenarios with different payloads
            
        Returns:
            List of API test results
        """
        results = []
        base_url = api_config.get("base_url", "http://localhost:8888")
        endpoints = api_config.get("endpoints", [])
        
        for endpoint_config in endpoints:
            endpoint_path = endpoint_config.get("path", "/")
            method = endpoint_config.get("method", "GET").upper()
            
            for scenario in test_scenarios:
                logger.info(f"Testing API {method} {endpoint_path} with scenario '{scenario.name}'")
                
                start_time = time.time()
                result = APITestResult(
                    endpoint=endpoint_path,
                    method=method,
                    scenario_name=scenario.name,
                    success=False,
                    validation_errors=[]
                )
                
                try:
                    # Prepare request
                    url = f"{base_url.rstrip('/')}{endpoint_path}"
                    headers = endpoint_config.get("headers", {})
                    
                    # Render payload template if provided
                    payload = None
                    if "payload_template" in endpoint_config:
                        template = Template(endpoint_config["payload_template"])
                        payload_str = template.render(**scenario.variables)
                        payload = json.loads(payload_str)
                    elif "payload" in scenario.variables:
                        payload = scenario.variables["payload"]
                    
                    # Make API request
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=payload,
                        timeout=scenario.timeout
                    )
                    
                    response_time = time.time() - start_time
                    
                    result.status_code = response.status_code
                    result.response_time = response_time
                    
                    # Parse response
                    try:
                        result.response_data = response.json()
                    except:
                        result.response_data = {"raw_response": response.text}
                    
                    # Validate status code
                    if response.status_code == scenario.expected_status:
                        result.success = True
                    else:
                        result.validation_errors.append(
                            f"Expected status {scenario.expected_status}, got {response.status_code}"
                        )
                    
                    # Validate response structure if schema provided
                    if scenario.validate_schema and "response_schema" in endpoint_config:
                        schema_errors = self._validate_response_schema(
                            result.response_data, endpoint_config["response_schema"]
                        )
                        result.validation_errors.extend(schema_errors)
                        if schema_errors:
                            result.success = False
                    
                    if result.success:
                        logger.info(f"✅ API {method} {endpoint_path} scenario '{scenario.name}' passed")
                    else:
                        logger.warning(f"⚠️ API {method} {endpoint_path} scenario '{scenario.name}' had validation errors")
                
                except requests.RequestException as e:
                    result.error_message = f"Request error: {str(e)}"
                    result.response_time = time.time() - start_time
                    logger.error(f"❌ API {method} {endpoint_path} scenario '{scenario.name}' failed: {str(e)}")
                
                except Exception as e:
                    result.error_message = f"Unexpected error: {str(e)}"
                    result.response_time = time.time() - start_time
                    logger.error(f"❌ API {method} {endpoint_path} scenario '{scenario.name}' error: {str(e)}")
                
                results.append(result)
        
        return results
    
    def _validate_rendered_output(self, rendered: str, expected: Dict[str, Any]) -> List[str]:
        """Validate rendered template output against expected structure."""
        errors = []
        
        try:
            # Try to parse as JSON
            rendered_data = json.loads(rendered)
            
            # Check required fields
            required_fields = expected.get("required_fields", [])
            for field in required_fields:
                if field not in rendered_data:
                    errors.append(f"Missing required field: {field}")
            
            # Check field types
            field_types = expected.get("field_types", {})
            for field, expected_type in field_types.items():
                if field in rendered_data:
                    actual_type = type(rendered_data[field]).__name__
                    if actual_type != expected_type:
                        errors.append(f"Field '{field}' expected type {expected_type}, got {actual_type}")
            
            # Check field values
            field_values = expected.get("field_values", {})
            for field, expected_value in field_values.items():
                if field in rendered_data:
                    if rendered_data[field] != expected_value:
                        errors.append(f"Field '{field}' expected value {expected_value}, got {rendered_data[field]}")
        
        except json.JSONDecodeError:
            # Not JSON, do basic string validation
            if "contains" in expected:
                for text in expected["contains"]:
                    if text not in rendered:
                        errors.append(f"Rendered output should contain: {text}")
            
            if "not_contains" in expected:
                for text in expected["not_contains"]:
                    if text in rendered:
                        errors.append(f"Rendered output should not contain: {text}")
        
        return errors
    
    def _validate_response_schema(self, response_data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate API response against JSON schema."""
        errors = []
        
        try:
            validate(instance=response_data, schema=schema)
        except ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
        except Exception as e:
            errors.append(f"Schema validation error: {str(e)}")
        
        return errors

    def start_mock_server(self, mock_responses: Dict[str, Any], port: int = 8888) -> bool:
        """
        Start mock API server for testing.

        Args:
            mock_responses: Dictionary of mock responses for different endpoints
            port: Port to run mock server on

        Returns:
            True if server started successfully
        """
        try:
            self.mock_server = MockAPIServer(port)

            # Add mock responses
            for endpoint_key, response_config in mock_responses.items():
                method, path = endpoint_key.split(":", 1)
                self.mock_server.add_mock_response(
                    path=path,
                    method=method,
                    response=response_config.get("response", {}),
                    status_code=response_config.get("status_code", 200)
                )

            self.mock_server.start()
            return True

        except Exception as e:
            logger.error(f"Failed to start mock server: {str(e)}")
            return False

    def stop_mock_server(self):
        """Stop mock API server."""
        if self.mock_server:
            self.mock_server.stop()
            self.mock_server = None

    def run_performance_tests(self, template_file: Path, scenario: TestScenario, iterations: int = 100) -> Dict[str, Any]:
        """
        Run performance tests for template rendering.

        Args:
            template_file: Path to template file
            scenario: Test scenario to use
            iterations: Number of iterations to run

        Returns:
            Performance test results
        """
        logger.info(f"Running performance test for template '{template_file}' with {iterations} iterations")

        try:
            # Load template
            if template_file.is_absolute():
                with open(template_file, 'r') as f:
                    template_content = f.read()
                template = Template(template_content)
            else:
                template = self.jinja_env.get_template(str(template_file))

            # Run performance test
            render_times = []
            errors = 0

            for i in range(iterations):
                start_time = time.time()
                try:
                    template.render(**scenario.variables)
                    render_time = time.time() - start_time
                    render_times.append(render_time)
                except Exception as e:
                    errors += 1
                    logger.debug(f"Render error in iteration {i}: {str(e)}")

            # Calculate statistics
            if render_times:
                avg_time = sum(render_times) / len(render_times)
                min_time = min(render_times)
                max_time = max(render_times)

                # Calculate percentiles
                sorted_times = sorted(render_times)
                p50 = sorted_times[len(sorted_times) // 2]
                p95 = sorted_times[int(len(sorted_times) * 0.95)]
                p99 = sorted_times[int(len(sorted_times) * 0.99)]
            else:
                avg_time = min_time = max_time = p50 = p95 = p99 = 0

            results = {
                "template_file": str(template_file),
                "scenario_name": scenario.name,
                "iterations": iterations,
                "successful_renders": len(render_times),
                "errors": errors,
                "error_rate": errors / iterations * 100,
                "performance_metrics": {
                    "average_time": avg_time,
                    "min_time": min_time,
                    "max_time": max_time,
                    "p50_time": p50,
                    "p95_time": p95,
                    "p99_time": p99
                },
                "renders_per_second": len(render_times) / sum(render_times) if render_times else 0
            }

            logger.info(f"Performance test completed: {len(render_times)} successful renders, {errors} errors")
            logger.info(f"Average render time: {avg_time:.4f}s, P95: {p95:.4f}s")

            return results

        except Exception as e:
            logger.error(f"Performance test failed: {str(e)}")
            return {
                "template_file": str(template_file),
                "scenario_name": scenario.name,
                "error": str(e),
                "success": False
            }

    def generate_test_report(self, results: Dict[str, Any], output_file: Path = None) -> str:
        """
        Generate comprehensive test report.

        Args:
            results: Test results dictionary
            output_file: Optional output file path

        Returns:
            Generated report content
        """
        report_lines = []

        # Header
        report_lines.append("# NornFlow API Payload Testing Report")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # Summary
        summary = results.get("summary", {})
        report_lines.append("## Test Summary")
        report_lines.append(f"- **Total Tests**: {summary.get('total_tests', 0)}")
        report_lines.append(f"- **Successful Tests**: {summary.get('successful_tests', 0)}")
        report_lines.append(f"- **Failed Tests**: {summary.get('failed_tests', 0)}")
        report_lines.append(f"- **Success Rate**: {summary.get('success_rate', 0):.1f}%")
        report_lines.append("")

        # Template Tests
        template_tests = results.get("template_tests", [])
        if template_tests:
            report_lines.append("## Template Tests")
            for test in template_tests:
                status = "✅ PASS" if test.get("success", False) else "❌ FAIL"
                report_lines.append(f"- **{test.get('template_name', 'Unknown')}** ({test.get('scenario_name', 'Unknown')}): {status}")
                if test.get("render_time"):
                    report_lines.append(f"  - Render Time: {test['render_time']:.4f}s")
                if test.get("error_message"):
                    report_lines.append(f"  - Error: {test['error_message']}")
                if test.get("validation_errors"):
                    for error in test["validation_errors"]:
                        report_lines.append(f"  - Validation Error: {error}")
            report_lines.append("")

        # API Tests
        api_tests = results.get("api_tests", [])
        if api_tests:
            report_lines.append("## API Tests")
            for test in api_tests:
                status = "✅ PASS" if test.get("success", False) else "❌ FAIL"
                report_lines.append(f"- **{test.get('method', 'GET')} {test.get('endpoint', '/')}** ({test.get('scenario_name', 'Unknown')}): {status}")
                if test.get("status_code"):
                    report_lines.append(f"  - Status Code: {test['status_code']}")
                if test.get("response_time"):
                    report_lines.append(f"  - Response Time: {test['response_time']:.4f}s")
                if test.get("error_message"):
                    report_lines.append(f"  - Error: {test['error_message']}")
                if test.get("validation_errors"):
                    for error in test["validation_errors"]:
                        report_lines.append(f"  - Validation Error: {error}")
            report_lines.append("")

        # Performance Results
        performance_results = results.get("performance_results", [])
        if performance_results:
            report_lines.append("## Performance Test Results")
            for perf in performance_results:
                if "error" not in perf:
                    metrics = perf.get("performance_metrics", {})
                    report_lines.append(f"- **{perf.get('template_file', 'Unknown')}**:")
                    report_lines.append(f"  - Iterations: {perf.get('iterations', 0)}")
                    report_lines.append(f"  - Success Rate: {100 - perf.get('error_rate', 0):.1f}%")
                    report_lines.append(f"  - Average Time: {metrics.get('average_time', 0):.4f}s")
                    report_lines.append(f"  - P95 Time: {metrics.get('p95_time', 0):.4f}s")
                    report_lines.append(f"  - Renders/Second: {perf.get('renders_per_second', 0):.1f}")
                else:
                    report_lines.append(f"- **{perf.get('template_file', 'Unknown')}**: ❌ Error - {perf.get('error', 'Unknown error')}")
            report_lines.append("")

        # Mock Server Log
        mock_log = results.get("mock_server_log", [])
        if mock_log:
            report_lines.append("## Mock Server Request Log")
            for request in mock_log[-10:]:  # Show last 10 requests
                report_lines.append(f"- **{request.get('method', 'GET')} {request.get('path', '/')}** at {request.get('timestamp', 'Unknown')}")
            if len(mock_log) > 10:
                report_lines.append(f"... and {len(mock_log) - 10} more requests")
            report_lines.append("")

        # Recommendations
        report_lines.append("## Recommendations")
        failed_tests = summary.get("failed_tests", 0)
        if failed_tests > 0:
            report_lines.append("- Review failed tests and fix template or API issues")
            report_lines.append("- Check variable names and data types in test scenarios")
            report_lines.append("- Validate API endpoint URLs and authentication")

        if performance_results:
            slow_templates = [p for p in performance_results if p.get("performance_metrics", {}).get("p95_time", 0) > 0.1]
            if slow_templates:
                report_lines.append("- Consider optimizing slow templates (P95 > 100ms)")

        report_lines.append("- Add more test scenarios to improve coverage")
        report_lines.append("- Consider adding schema validation for API responses")

        report_content = "\n".join(report_lines)

        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            logger.info(f"Test report saved to: {output_file}")

        return report_content
