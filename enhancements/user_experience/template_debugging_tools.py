"""
Template Debugging Tools for NornFlow.

This module provides comprehensive debugging capabilities for Jinja2 templates:
- Variable inspection and tracing
- Template rendering step-by-step debugging
- Error analysis and suggestions
- Variable dependency mapping
- Template performance profiling
- Interactive debugging interface

This enables developers to quickly identify and fix issues in Jinja2 templates
used for API payloads and device configurations.
"""

import re
import ast
import json
import yaml
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
from jinja2 import Environment, FileSystemLoader, Template, TemplateError, meta
from jinja2.exceptions import TemplateRuntimeError, TemplateSyntaxError, UndefinedError
import traceback

logger = logging.getLogger(__name__)


@dataclass
class VariableInfo:
    """Information about a template variable."""
    name: str
    type: str
    value: Any
    used_in_template: bool = False
    line_numbers: List[int] = None
    filters_applied: List[str] = None
    dependencies: List[str] = None


@dataclass
class TemplateError:
    """Template error information."""
    error_type: str
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    variable_name: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class RenderingStep:
    """Information about a template rendering step."""
    step_number: int
    operation: str
    input_value: Any
    output_value: Any
    variables_used: List[str]
    filters_applied: List[str]
    line_number: Optional[int] = None


class TemplateDebugger:
    """
    Comprehensive debugging tool for Jinja2 templates.
    
    Provides methods to:
    - Analyze template structure and dependencies
    - Debug variable usage and undefined variables
    - Trace template rendering step by step
    - Provide error analysis and suggestions
    - Profile template performance
    """
    
    def __init__(self, templates_dir: Path = None):
        """
        Initialize template debugger.
        
        Args:
            templates_dir: Directory containing Jinja2 templates
        """
        self.templates_dir = templates_dir or Path("templates")
        
        # Initialize Jinja2 environment with debugging enabled
        if self.templates_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
                undefined=DebugUndefined  # Custom undefined class for debugging
            )
        else:
            self.jinja_env = Environment(undefined=DebugUndefined)
        
        # Enable line statements for better debugging
        self.jinja_env.line_statement_prefix = '#'
        
    def analyze_template(self, template_file: Path) -> Dict[str, Any]:
        """
        Analyze template structure and extract metadata.
        
        Args:
            template_file: Path to template file
            
        Returns:
            Template analysis results
        """
        try:
            # Load template content
            if template_file.is_absolute():
                with open(template_file, 'r') as f:
                    template_content = f.read()
                template_name = template_file.name
            else:
                template_content = self.jinja_env.get_template(str(template_file)).source
                template_name = str(template_file)
            
            # Parse template AST
            ast_nodes = self.jinja_env.parse(template_content)
            
            # Extract variables
            variables = meta.find_undeclared_variables(ast_nodes)
            
            # Analyze template structure
            analysis = {
                "template_name": template_name,
                "template_size": len(template_content),
                "line_count": len(template_content.split('\n')),
                "variables": {
                    "declared": list(variables),
                    "count": len(variables)
                },
                "blocks": self._extract_blocks(template_content),
                "macros": self._extract_macros(template_content),
                "includes": self._extract_includes(template_content),
                "extends": self._extract_extends(template_content),
                "filters": self._extract_filters(template_content),
                "tests": self._extract_tests(template_content),
                "control_structures": self._analyze_control_structures(template_content),
                "complexity_score": self._calculate_complexity(template_content)
            }
            
            logger.info(f"Template analysis completed for: {template_name}")
            return analysis
        
        except Exception as e:
            logger.error(f"Template analysis failed: {str(e)}")
            return {
                "template_name": str(template_file),
                "error": str(e),
                "success": False
            }
    
    def debug_variables(self, template_file: Path, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Debug variable usage in template.
        
        Args:
            template_file: Path to template file
            variables: Variables to use for rendering
            
        Returns:
            Variable debugging results
        """
        try:
            # Load template
            if template_file.is_absolute():
                with open(template_file, 'r') as f:
                    template_content = f.read()
                template = Template(template_content)
                template_name = template_file.name
            else:
                template = self.jinja_env.get_template(str(template_file))
                template_content = template.source
                template_name = str(template_file)
            
            # Analyze variables
            ast_nodes = self.jinja_env.parse(template_content)
            declared_variables = meta.find_undeclared_variables(ast_nodes)
            
            variable_info = []
            
            # Analyze each declared variable
            for var_name in declared_variables:
                var_info = VariableInfo(
                    name=var_name,
                    type=type(variables.get(var_name, None)).__name__ if var_name in variables else "undefined",
                    value=variables.get(var_name, "UNDEFINED"),
                    used_in_template=True,
                    line_numbers=self._find_variable_usage(template_content, var_name),
                    filters_applied=self._find_variable_filters(template_content, var_name),
                    dependencies=self._find_variable_dependencies(template_content, var_name)
                )
                variable_info.append(var_info)
            
            # Check for unused provided variables
            for var_name, var_value in variables.items():
                if var_name not in declared_variables:
                    var_info = VariableInfo(
                        name=var_name,
                        type=type(var_value).__name__,
                        value=var_value,
                        used_in_template=False
                    )
                    variable_info.append(var_info)
            
            # Find undefined variables
            undefined_variables = [var for var in declared_variables if var not in variables]
            
            # Generate suggestions
            suggestions = []
            for undefined_var in undefined_variables:
                similar_vars = self._find_similar_variables(undefined_var, list(variables.keys()))
                if similar_vars:
                    suggestions.append(f"Variable '{undefined_var}' is undefined. Did you mean: {', '.join(similar_vars)}?")
                else:
                    suggestions.append(f"Variable '{undefined_var}' is undefined. Please provide a value.")
            
            results = {
                "template_name": template_name,
                "variable_analysis": [asdict(var) for var in variable_info],
                "undefined_variables": undefined_variables,
                "unused_variables": [var.name for var in variable_info if not var.used_in_template],
                "suggestions": suggestions,
                "variable_count": {
                    "declared": len(declared_variables),
                    "provided": len(variables),
                    "undefined": len(undefined_variables),
                    "unused": len([var for var in variable_info if not var.used_in_template])
                }
            }
            
            logger.info(f"Variable debugging completed for: {template_name}")
            return results
        
        except Exception as e:
            logger.error(f"Variable debugging failed: {str(e)}")
            return {
                "template_name": str(template_file),
                "error": str(e),
                "success": False
            }
    
    def debug_rendering(self, template_file: Path, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Debug template rendering with detailed error analysis.
        
        Args:
            template_file: Path to template file
            variables: Variables to use for rendering
            
        Returns:
            Rendering debugging results
        """
        try:
            # Load template
            if template_file.is_absolute():
                with open(template_file, 'r') as f:
                    template_content = f.read()
                template = Template(template_content)
                template_name = template_file.name
            else:
                template = self.jinja_env.get_template(str(template_file))
                template_content = template.source
                template_name = str(template_file)
            
            results = {
                "template_name": template_name,
                "rendering_successful": False,
                "rendered_output": None,
                "errors": [],
                "warnings": [],
                "performance_metrics": {}
            }
            
            # Attempt rendering with error capture
            import time
            start_time = time.time()
            
            try:
                rendered_output = template.render(**variables)
                render_time = time.time() - start_time
                
                results["rendering_successful"] = True
                results["rendered_output"] = rendered_output
                results["performance_metrics"] = {
                    "render_time": render_time,
                    "output_size": len(rendered_output),
                    "lines_rendered": len(rendered_output.split('\n'))
                }
                
                logger.info(f"Template rendering successful for: {template_name}")
            
            except UndefinedError as e:
                render_time = time.time() - start_time
                error_info = self._analyze_undefined_error(str(e), template_content)
                results["errors"].append(error_info)
                results["performance_metrics"]["render_time"] = render_time
                
                logger.error(f"Undefined variable error in {template_name}: {str(e)}")
            
            except TemplateSyntaxError as e:
                render_time = time.time() - start_time
                error_info = self._analyze_syntax_error(e, template_content)
                results["errors"].append(error_info)
                results["performance_metrics"]["render_time"] = render_time
                
                logger.error(f"Template syntax error in {template_name}: {str(e)}")
            
            except TemplateRuntimeError as e:
                render_time = time.time() - start_time
                error_info = self._analyze_runtime_error(e, template_content)
                results["errors"].append(error_info)
                results["performance_metrics"]["render_time"] = render_time
                
                logger.error(f"Template runtime error in {template_name}: {str(e)}")
            
            except Exception as e:
                render_time = time.time() - start_time
                error_info = {
                    "error_type": "UnknownError",
                    "message": str(e),
                    "suggestion": "Check template syntax and variable types"
                }
                results["errors"].append(error_info)
                results["performance_metrics"]["render_time"] = render_time
                
                logger.error(f"Unknown error in {template_name}: {str(e)}")
            
            # Add warnings for potential issues
            warnings = self._check_template_warnings(template_content, variables)
            results["warnings"] = warnings
            
            return results
        
        except Exception as e:
            logger.error(f"Rendering debugging failed: {str(e)}")
            return {
                "template_name": str(template_file),
                "error": str(e),
                "success": False
            }
    
    def _extract_blocks(self, template_content: str) -> List[str]:
        """Extract block names from template."""
        block_pattern = r'{%\s*block\s+(\w+)\s*%}'
        return re.findall(block_pattern, template_content)
    
    def _extract_macros(self, template_content: str) -> List[str]:
        """Extract macro names from template."""
        macro_pattern = r'{%\s*macro\s+(\w+)\s*\('
        return re.findall(macro_pattern, template_content)
    
    def _extract_includes(self, template_content: str) -> List[str]:
        """Extract included template names."""
        include_pattern = r'{%\s*include\s+["\']([^"\']+)["\']'
        return re.findall(include_pattern, template_content)
    
    def _extract_extends(self, template_content: str) -> Optional[str]:
        """Extract extended template name."""
        extends_pattern = r'{%\s*extends\s+["\']([^"\']+)["\']'
        matches = re.findall(extends_pattern, template_content)
        return matches[0] if matches else None
    
    def _extract_filters(self, template_content: str) -> List[str]:
        """Extract filter names used in template."""
        filter_pattern = r'\|\s*(\w+)'
        return list(set(re.findall(filter_pattern, template_content)))
    
    def _extract_tests(self, template_content: str) -> List[str]:
        """Extract test names used in template."""
        test_pattern = r'is\s+(\w+)'
        return list(set(re.findall(test_pattern, template_content)))
    
    def _analyze_control_structures(self, template_content: str) -> Dict[str, int]:
        """Analyze control structures in template."""
        structures = {
            "if_statements": len(re.findall(r'{%\s*if\s+', template_content)),
            "for_loops": len(re.findall(r'{%\s*for\s+', template_content)),
            "set_statements": len(re.findall(r'{%\s*set\s+', template_content)),
            "with_statements": len(re.findall(r'{%\s*with\s+', template_content))
        }
        return structures
    
    def _calculate_complexity(self, template_content: str) -> int:
        """Calculate template complexity score."""
        # Simple complexity calculation based on various factors
        complexity = 0
        complexity += len(re.findall(r'{%.*?%}', template_content))  # Control structures
        complexity += len(re.findall(r'{{.*?}}', template_content))  # Variable expressions
        complexity += len(re.findall(r'\|', template_content))  # Filters
        complexity += len(template_content.split('\n'))  # Lines
        return complexity
    
    def _find_variable_usage(self, template_content: str, var_name: str) -> List[int]:
        """Find line numbers where variable is used."""
        lines = template_content.split('\n')
        line_numbers = []
        
        for i, line in enumerate(lines, 1):
            if re.search(rf'\b{re.escape(var_name)}\b', line):
                line_numbers.append(i)
        
        return line_numbers
    
    def _find_variable_filters(self, template_content: str, var_name: str) -> List[str]:
        """Find filters applied to a variable."""
        pattern = rf'{re.escape(var_name)}\s*\|\s*(\w+)'
        return re.findall(pattern, template_content)
    
    def _find_variable_dependencies(self, template_content: str, var_name: str) -> List[str]:
        """Find variables that this variable depends on."""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated AST analysis
        dependencies = []
        
        # Look for variable assignments that reference other variables
        pattern = rf'{re.escape(var_name)}\s*=.*?(\w+)'
        matches = re.findall(pattern, template_content)
        dependencies.extend(matches)
        
        return dependencies
    
    def _find_similar_variables(self, target: str, available: List[str]) -> List[str]:
        """Find variables with similar names."""
        similar = []
        
        for var in available:
            # Simple similarity check
            if abs(len(target) - len(var)) <= 2:
                # Check for common prefixes/suffixes
                if target.lower() in var.lower() or var.lower() in target.lower():
                    similar.append(var)
                # Check for character transpositions
                elif self._levenshtein_distance(target.lower(), var.lower()) <= 2:
                    similar.append(var)
        
        return similar[:3]  # Return top 3 matches
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _analyze_undefined_error(self, error_message: str, template_content: str) -> Dict[str, Any]:
        """Analyze undefined variable error and provide suggestions."""
        # Extract variable name from error message
        var_match = re.search(r"'(\w+)' is undefined", error_message)
        var_name = var_match.group(1) if var_match else "unknown"
        
        return {
            "error_type": "UndefinedError",
            "message": error_message,
            "variable_name": var_name,
            "suggestion": f"Provide a value for variable '{var_name}' or use a default filter: {{ {var_name} | default('default_value') }}"
        }
    
    def _analyze_syntax_error(self, error: TemplateSyntaxError, template_content: str) -> Dict[str, Any]:
        """Analyze template syntax error."""
        return {
            "error_type": "TemplateSyntaxError",
            "message": str(error),
            "line_number": getattr(error, 'lineno', None),
            "suggestion": "Check template syntax, especially block tags and variable expressions"
        }
    
    def _analyze_runtime_error(self, error: TemplateRuntimeError, template_content: str) -> Dict[str, Any]:
        """Analyze template runtime error."""
        return {
            "error_type": "TemplateRuntimeError",
            "message": str(error),
            "suggestion": "Check variable types and filter compatibility"
        }
    
    def _check_template_warnings(self, template_content: str, variables: Dict[str, Any]) -> List[str]:
        """Check for potential template issues and generate warnings."""
        warnings = []
        
        # Check for potentially unsafe operations
        if 'eval(' in template_content:
            warnings.append("Template contains 'eval()' which may be unsafe")
        
        # Check for very long lines
        lines = template_content.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                warnings.append(f"Line {i} is very long ({len(line)} characters)")
        
        # Check for deeply nested structures
        max_nesting = 0
        current_nesting = 0
        for line in lines:
            if re.search(r'{%\s*(if|for|with|block)', line):
                current_nesting += 1
                max_nesting = max(max_nesting, current_nesting)
            elif re.search(r'{%\s*end', line):
                current_nesting -= 1
        
        if max_nesting > 5:
            warnings.append(f"Template has deep nesting (level {max_nesting}), consider refactoring")
        
        return warnings


class DebugUndefined:
    """Custom undefined class for better debugging."""
    
    def __init__(self, name=None):
        self.name = name
    
    def __str__(self):
        return f"UNDEFINED_VARIABLE({self.name})"
    
    def __repr__(self):
        return f"DebugUndefined('{self.name}')"
