#!/usr/bin/env python3
"""
Template Debugging Setup Utility for NornFlow.

This utility provides comprehensive debugging capabilities for Jinja2 templates:
- Interactive template debugging sessions
- Batch template analysis and validation
- Variable dependency mapping
- Error analysis and suggestions
- Performance profiling for templates
- Template complexity analysis

Usage:
    python template_debug_setup.py --analyze templates/device_config.j2
    python template_debug_setup.py --debug templates/api_payload.j2 --variables vars.yaml
    python template_debug_setup.py --batch-analyze templates/
    python template_debug_setup.py --interactive templates/device_config.j2
"""

import argparse
import yaml
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

from template_debugging_tools import TemplateDebugger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TemplateDebugSetupManager:
    """Manages template debugging operations for NornFlow."""
    
    def __init__(self, templates_dir: Path = None):
        """Initialize debug setup manager."""
        self.templates_dir = templates_dir or Path("templates")
        self.debugger = TemplateDebugger(self.templates_dir)
        
    def analyze_single_template(self, template_file: Path) -> Dict[str, Any]:
        """Analyze a single template file."""
        logger.info(f"Analyzing template: {template_file}")
        
        if not template_file.exists():
            return {
                "success": False,
                "message": f"Template file not found: {template_file}"
            }
        
        try:
            analysis = self.debugger.analyze_template(template_file)
            
            # Add summary information
            analysis["summary"] = {
                "complexity_level": self._get_complexity_level(analysis.get("complexity_score", 0)),
                "variable_count": analysis.get("variables", {}).get("count", 0),
                "has_control_structures": any(
                    count > 0 for count in analysis.get("control_structures", {}).values()
                ),
                "uses_filters": len(analysis.get("filters", [])) > 0,
                "uses_includes": len(analysis.get("includes", [])) > 0
            }
            
            logger.info(f"Template analysis completed for: {template_file.name}")
            return {
                "success": True,
                "analysis": analysis,
                "message": f"Template analysis completed for {template_file.name}"
            }
        
        except Exception as e:
            logger.error(f"Template analysis failed: {str(e)}")
            return {
                "success": False,
                "message": f"Analysis failed: {str(e)}"
            }
    
    def debug_template_with_variables(self, template_file: Path, variables_file: Path = None, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Debug template rendering with provided variables."""
        logger.info(f"Debugging template: {template_file}")
        
        if not template_file.exists():
            return {
                "success": False,
                "message": f"Template file not found: {template_file}"
            }
        
        # Load variables
        if variables_file and variables_file.exists():
            try:
                with open(variables_file, 'r') as f:
                    if variables_file.suffix.lower() in ['.yaml', '.yml']:
                        variables = yaml.safe_load(f)
                    else:
                        variables = json.load(f)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Failed to load variables file: {str(e)}"
                }
        elif not variables:
            variables = {}
        
        try:
            # Debug variables
            variable_debug = self.debugger.debug_variables(template_file, variables)
            
            # Debug rendering
            rendering_debug = self.debugger.debug_rendering(template_file, variables)
            
            # Combine results
            debug_results = {
                "template_file": str(template_file),
                "variable_debugging": variable_debug,
                "rendering_debugging": rendering_debug,
                "summary": {
                    "rendering_successful": rendering_debug.get("rendering_successful", False),
                    "undefined_variables": len(variable_debug.get("undefined_variables", [])),
                    "unused_variables": len(variable_debug.get("unused_variables", [])),
                    "error_count": len(rendering_debug.get("errors", [])),
                    "warning_count": len(rendering_debug.get("warnings", []))
                }
            }
            
            logger.info(f"Template debugging completed for: {template_file.name}")
            return {
                "success": True,
                "debug_results": debug_results,
                "message": f"Template debugging completed for {template_file.name}"
            }
        
        except Exception as e:
            logger.error(f"Template debugging failed: {str(e)}")
            return {
                "success": False,
                "message": f"Debugging failed: {str(e)}"
            }
    
    def batch_analyze_templates(self, templates_dir: Path) -> Dict[str, Any]:
        """Analyze all templates in a directory."""
        logger.info(f"Batch analyzing templates in: {templates_dir}")
        
        if not templates_dir.exists():
            return {
                "success": False,
                "message": f"Templates directory not found: {templates_dir}"
            }
        
        # Find template files
        template_files = list(templates_dir.glob("*.j2")) + list(templates_dir.glob("*.jinja2"))
        
        if not template_files:
            return {
                "success": False,
                "message": f"No template files found in: {templates_dir}"
            }
        
        results = []
        summary_stats = {
            "total_templates": len(template_files),
            "successful_analyses": 0,
            "failed_analyses": 0,
            "complexity_distribution": {"low": 0, "medium": 0, "high": 0, "very_high": 0},
            "total_variables": 0,
            "templates_with_errors": 0
        }
        
        for template_file in template_files:
            logger.info(f"Analyzing: {template_file.name}")
            
            analysis_result = self.analyze_single_template(template_file)
            results.append(analysis_result)
            
            if analysis_result["success"]:
                summary_stats["successful_analyses"] += 1
                
                analysis = analysis_result["analysis"]
                complexity_level = analysis.get("summary", {}).get("complexity_level", "low")
                summary_stats["complexity_distribution"][complexity_level] += 1
                summary_stats["total_variables"] += analysis.get("variables", {}).get("count", 0)
            else:
                summary_stats["failed_analyses"] += 1
                summary_stats["templates_with_errors"] += 1
        
        # Generate recommendations
        recommendations = []
        
        if summary_stats["failed_analyses"] > 0:
            recommendations.append(f"Fix {summary_stats['failed_analyses']} templates with analysis errors")
        
        high_complexity_count = summary_stats["complexity_distribution"]["high"] + summary_stats["complexity_distribution"]["very_high"]
        if high_complexity_count > 0:
            recommendations.append(f"Consider refactoring {high_complexity_count} high-complexity templates")
        
        if summary_stats["total_variables"] / summary_stats["total_templates"] > 10:
            recommendations.append("Consider using template inheritance to reduce variable duplication")
        
        batch_results = {
            "templates_analyzed": results,
            "summary_statistics": summary_stats,
            "recommendations": recommendations
        }
        
        logger.info(f"Batch analysis completed: {summary_stats['successful_analyses']}/{summary_stats['total_templates']} templates analyzed successfully")
        
        return {
            "success": summary_stats["successful_analyses"] > 0,
            "batch_results": batch_results,
            "message": f"Analyzed {summary_stats['successful_analyses']}/{summary_stats['total_templates']} templates successfully"
        }
    
    def interactive_debug_session(self, template_file: Path) -> Dict[str, Any]:
        """Start an interactive debugging session for a template."""
        logger.info(f"Starting interactive debug session for: {template_file}")
        
        if not template_file.exists():
            return {
                "success": False,
                "message": f"Template file not found: {template_file}"
            }
        
        try:
            print(f"\n🔍 Interactive Template Debugging Session")
            print(f"Template: {template_file}")
            print("=" * 60)
            
            # Step 1: Analyze template structure
            print("\n📊 Step 1: Template Analysis")
            analysis = self.debugger.analyze_template(template_file)
            
            print(f"Variables declared: {analysis.get('variables', {}).get('count', 0)}")
            print(f"Complexity score: {analysis.get('complexity_score', 0)}")
            print(f"Control structures: {analysis.get('control_structures', {})}")
            print(f"Filters used: {', '.join(analysis.get('filters', []))}")
            
            # Step 2: Get variables from user
            print("\n📝 Step 2: Variable Input")
            print("Declared variables:", ', '.join(analysis.get('variables', {}).get('declared', [])))
            
            variables = {}
            for var_name in analysis.get('variables', {}).get('declared', []):
                while True:
                    try:
                        value_input = input(f"Enter value for '{var_name}' (or 'skip'): ").strip()
                        if value_input.lower() == 'skip':
                            break
                        
                        # Try to parse as JSON for complex types
                        try:
                            variables[var_name] = json.loads(value_input)
                        except json.JSONDecodeError:
                            # Treat as string
                            variables[var_name] = value_input
                        break
                    except KeyboardInterrupt:
                        print("\nDebugging session cancelled.")
                        return {"success": False, "message": "Session cancelled by user"}
            
            # Step 3: Debug variables
            print("\n🔍 Step 3: Variable Debugging")
            var_debug = self.debugger.debug_variables(template_file, variables)
            
            if var_debug.get("undefined_variables"):
                print(f"⚠️ Undefined variables: {', '.join(var_debug['undefined_variables'])}")
            
            if var_debug.get("unused_variables"):
                print(f"ℹ️ Unused variables: {', '.join(var_debug['unused_variables'])}")
            
            # Step 4: Attempt rendering
            print("\n🚀 Step 4: Template Rendering")
            render_debug = self.debugger.debug_rendering(template_file, variables)
            
            if render_debug.get("rendering_successful"):
                print("✅ Template rendered successfully!")
                print(f"Render time: {render_debug.get('performance_metrics', {}).get('render_time', 0):.4f}s")
                
                show_output = input("Show rendered output? (y/n): ").strip().lower()
                if show_output == 'y':
                    print("\n📄 Rendered Output:")
                    print("-" * 40)
                    print(render_debug.get("rendered_output", ""))
                    print("-" * 40)
            else:
                print("❌ Template rendering failed!")
                for error in render_debug.get("errors", []):
                    print(f"Error: {error.get('message', 'Unknown error')}")
                    if error.get("suggestion"):
                        print(f"Suggestion: {error['suggestion']}")
            
            # Step 5: Show warnings
            warnings = render_debug.get("warnings", [])
            if warnings:
                print("\n⚠️ Warnings:")
                for warning in warnings:
                    print(f"- {warning}")
            
            print("\n✅ Interactive debugging session completed!")
            
            return {
                "success": True,
                "session_results": {
                    "analysis": analysis,
                    "variables_used": variables,
                    "variable_debugging": var_debug,
                    "rendering_debugging": render_debug
                },
                "message": "Interactive debugging session completed"
            }
        
        except Exception as e:
            logger.error(f"Interactive debugging failed: {str(e)}")
            return {
                "success": False,
                "message": f"Interactive debugging failed: {str(e)}"
            }
    
    def generate_debug_report(self, results: Dict[str, Any], output_file: Path = None) -> str:
        """Generate a comprehensive debugging report."""
        report_lines = []
        
        # Header
        report_lines.append("# NornFlow Template Debugging Report")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Handle different result types
        if "batch_results" in results:
            # Batch analysis report
            batch_results = results["batch_results"]
            summary = batch_results["summary_statistics"]
            
            report_lines.append("## Batch Analysis Summary")
            report_lines.append(f"- **Total Templates**: {summary['total_templates']}")
            report_lines.append(f"- **Successful Analyses**: {summary['successful_analyses']}")
            report_lines.append(f"- **Failed Analyses**: {summary['failed_analyses']}")
            report_lines.append(f"- **Templates with Errors**: {summary['templates_with_errors']}")
            report_lines.append("")
            
            report_lines.append("## Complexity Distribution")
            complexity = summary["complexity_distribution"]
            for level, count in complexity.items():
                report_lines.append(f"- **{level.title()}**: {count} templates")
            report_lines.append("")
            
            # Individual template results
            report_lines.append("## Individual Template Analysis")
            for template_result in batch_results["templates_analyzed"]:
                if template_result["success"]:
                    analysis = template_result["analysis"]
                    report_lines.append(f"### {analysis['template_name']}")
                    report_lines.append(f"- Variables: {analysis.get('variables', {}).get('count', 0)}")
                    report_lines.append(f"- Complexity: {analysis.get('complexity_score', 0)}")
                    report_lines.append(f"- Lines: {analysis.get('line_count', 0)}")
                else:
                    report_lines.append(f"### {template_result.get('template_file', 'Unknown')}")
                    report_lines.append(f"- ❌ Analysis failed: {template_result.get('message', 'Unknown error')}")
                report_lines.append("")
            
            # Recommendations
            recommendations = batch_results.get("recommendations", [])
            if recommendations:
                report_lines.append("## Recommendations")
                for rec in recommendations:
                    report_lines.append(f"- {rec}")
                report_lines.append("")
        
        elif "debug_results" in results:
            # Single template debug report
            debug_results = results["debug_results"]
            
            report_lines.append(f"## Template: {debug_results['template_file']}")
            
            # Variable debugging
            var_debug = debug_results["variable_debugging"]
            report_lines.append("### Variable Analysis")
            report_lines.append(f"- **Undefined Variables**: {len(var_debug.get('undefined_variables', []))}")
            report_lines.append(f"- **Unused Variables**: {len(var_debug.get('unused_variables', []))}")
            
            if var_debug.get("undefined_variables"):
                report_lines.append("#### Undefined Variables:")
                for var in var_debug["undefined_variables"]:
                    report_lines.append(f"- `{var}`")
            
            if var_debug.get("suggestions"):
                report_lines.append("#### Suggestions:")
                for suggestion in var_debug["suggestions"]:
                    report_lines.append(f"- {suggestion}")
            
            report_lines.append("")
            
            # Rendering debugging
            render_debug = debug_results["rendering_debugging"]
            report_lines.append("### Rendering Analysis")
            
            if render_debug.get("rendering_successful"):
                report_lines.append("- ✅ **Status**: Successful")
                metrics = render_debug.get("performance_metrics", {})
                if metrics:
                    report_lines.append(f"- **Render Time**: {metrics.get('render_time', 0):.4f}s")
                    report_lines.append(f"- **Output Size**: {metrics.get('output_size', 0)} characters")
            else:
                report_lines.append("- ❌ **Status**: Failed")
                
                errors = render_debug.get("errors", [])
                if errors:
                    report_lines.append("#### Errors:")
                    for error in errors:
                        report_lines.append(f"- **{error.get('error_type', 'Error')}**: {error.get('message', 'Unknown')}")
                        if error.get("suggestion"):
                            report_lines.append(f"  - Suggestion: {error['suggestion']}")
            
            warnings = render_debug.get("warnings", [])
            if warnings:
                report_lines.append("#### Warnings:")
                for warning in warnings:
                    report_lines.append(f"- {warning}")
            
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # Save to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            logger.info(f"Debug report saved to: {output_file}")
        
        return report_content
    
    def _get_complexity_level(self, complexity_score: int) -> str:
        """Get complexity level based on score."""
        if complexity_score < 20:
            return "low"
        elif complexity_score < 50:
            return "medium"
        elif complexity_score < 100:
            return "high"
        else:
            return "very_high"


def main():
    """Main entry point for template debugging setup utility."""
    parser = argparse.ArgumentParser(description="Debug and analyze Jinja2 templates for NornFlow")
    parser.add_argument("--analyze", type=Path, help="Analyze a single template file")
    parser.add_argument("--debug", type=Path, help="Debug template rendering")
    parser.add_argument("--variables", type=Path, help="Variables file (YAML or JSON)")
    parser.add_argument("--batch-analyze", type=Path, help="Analyze all templates in directory")
    parser.add_argument("--interactive", type=Path, help="Start interactive debugging session")
    parser.add_argument("--templates-dir", type=Path, help="Templates directory")
    parser.add_argument("--output-report", type=Path, help="Output report file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    try:
        # Initialize setup manager
        setup_manager = TemplateDebugSetupManager(args.templates_dir)
        
        # Analyze single template
        if args.analyze:
            if not args.analyze.exists():
                logger.error(f"Template file not found: {args.analyze}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would analyze template {args.analyze}")
            else:
                result = setup_manager.analyze_single_template(args.analyze)
                
                if args.output_report:
                    setup_manager.generate_debug_report(result, args.output_report)
                
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Debug template with variables
        if args.debug:
            if not args.debug.exists():
                logger.error(f"Template file not found: {args.debug}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would debug template {args.debug}")
                if args.variables:
                    logger.info(f"DRY RUN: Would use variables from {args.variables}")
            else:
                result = setup_manager.debug_template_with_variables(args.debug, args.variables)
                
                if args.output_report:
                    setup_manager.generate_debug_report(result, args.output_report)
                
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Batch analyze templates
        if args.batch_analyze:
            if not args.batch_analyze.exists():
                logger.error(f"Templates directory not found: {args.batch_analyze}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would analyze all templates in {args.batch_analyze}")
                template_files = list(args.batch_analyze.glob("*.j2")) + list(args.batch_analyze.glob("*.jinja2"))
                print(f"Found {len(template_files)} template files:")
                for tf in template_files:
                    print(f"  - {tf.name}")
            else:
                result = setup_manager.batch_analyze_templates(args.batch_analyze)
                
                if args.output_report:
                    setup_manager.generate_debug_report(result, args.output_report)
                
                print(json.dumps(result, indent=2, default=str))
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Interactive debugging session
        if args.interactive:
            if not args.interactive.exists():
                logger.error(f"Template file not found: {args.interactive}")
                sys.exit(1)
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would start interactive session for {args.interactive}")
            else:
                result = setup_manager.interactive_debug_session(args.interactive)
                
                if args.output_report:
                    setup_manager.generate_debug_report(result, args.output_report)
                
                if not result["success"]:
                    sys.exit(1)
            return
        
        # Show help if no action specified
        parser.print_help()
    
    except Exception as e:
        logger.error(f"Template debugging failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
