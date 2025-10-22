"""
Integration test runner and orchestrator.

Provides utilities for running integration tests in different configurations
and generating comprehensive test reports.
"""

import pytest
import sys
import os
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import subprocess


class IntegrationTestRunner:
    """Orchestrates integration test execution."""
    
    def __init__(self, test_directory: str = "tests/integration"):
        self.test_directory = test_directory
        self.results = {}
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    def run_workflow_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run all workflow integration tests."""
        
        workflow_tests = [
            "test_loan_origination_workflow.py",
            "test_customer_mastery_lifecycle.py",
            "test_compliance_rule_enforcement.py",
            "test_cross_domain_integration.py"
        ]
        
        return self._run_test_files(workflow_tests, verbose)
    
    def run_all_tests(self, verbose: bool = True, markers: Optional[str] = None, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Run all integration tests with optional filtering."""
        
        cmd = ["python", "-m", "pytest", self.test_directory]
        
        if verbose:
            cmd.append("-v")
        
        if markers:
            cmd.extend(["-m", markers])
        
        if output_file:
            cmd.extend(["--junitxml", output_file])
        
        cmd.extend(["--tb=short", "--strict-markers"])
        
        print(f"Running all integration tests...")
        print(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_dir)
            return {
                "all_tests": {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": result.returncode == 0
                }
            }
        except Exception as e:
            return {
                "all_tests": {
                    "returncode": -1,
                    "error": str(e),
                    "success": False
                }
            }
    
    def _run_test_files(self, test_files: List[str], verbose: bool = True) -> Dict[str, Any]:
        """Run specific test files and collect results."""
        
        results = {}
        
        for test_file in test_files:
            test_path = os.path.join(self.test_directory, test_file)
            full_path = os.path.join(self.base_dir, test_path)
            
            if os.path.exists(full_path):
                print(f"Running {test_file}...")
                
                cmd = ["python", "-m", "pytest", test_path]
                if verbose:
                    cmd.append("-v")
                cmd.extend(["--tb=short", "--strict-markers"])
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_dir)
                    results[test_file] = {
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "success": result.returncode == 0
                    }
                except Exception as e:
                    results[test_file] = {
                        "returncode": -1,
                        "error": str(e),
                        "success": False
                    }
            else:
                results[test_file] = {
                    "error": f"Test file not found: {full_path}",
                    "success": False
                }
        
        return results
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive test report."""
        
        report_lines = [
            "# Integration Test Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Test Results Summary",
            ""
        ]
        
        total_tests = len(results)
        successful_tests = sum(1 for r in results.values() if r.get("success", False))
        
        report_lines.extend([
            f"- Total test files: {total_tests}",
            f"- Successful: {successful_tests}",
            f"- Failed: {total_tests - successful_tests}",
            f"- Success rate: {(successful_tests/total_tests*100):.1f}%",
            ""
        ])
        
        # Detailed results
        report_lines.append("## Detailed Results")
        report_lines.append("")
        
        for test_file, result in results.items():
            status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
            report_lines.append(f"### {test_file} - {status}")
            report_lines.append("")
            
            if result.get("success", False):
                report_lines.append("Test completed successfully.")
            else:
                if "error" in result:
                    report_lines.append(f"Error: {result['error']}")
                if "stderr" in result and result["stderr"]:
                    report_lines.append("```")
                    report_lines.append(result["stderr"])
                    report_lines.append("```")
            
            report_lines.append("")
        
        return "\n".join(report_lines)


if __name__ == "__main__":
    runner = IntegrationTestRunner()
    results = runner.run_workflow_tests()
    report = runner.generate_test_report(results)
    
    print(report)
    
    # Save report to file
    with open("integration_test_report.md", "w") as f:
        f.write(report)
    
    # Exit with error code if any tests failed
    if not all(r.get("success", False) for r in results.values()):
        sys.exit(1)