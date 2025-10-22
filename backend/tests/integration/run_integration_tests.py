#!/usr/bin/env python3
"""
Integration test execution script.

Provides different test execution modes and comprehensive reporting.
Uses the IntegrationTestRunner for better code reuse and enhanced functionality.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, List

# Import the IntegrationTestRunner for programmatic test execution
try:
    from tests.integration.test_runner import IntegrationTestRunner
except ImportError:
    # Fallback if the module is not available
    IntegrationTestRunner = None


class CLITestRunner:
    """CLI wrapper around IntegrationTestRunner with enhanced functionality."""
    
    def __init__(self):
        self.runner = IntegrationTestRunner() if IntegrationTestRunner else None
    
    def run_tests(self, test_type="all", verbose=True, markers=None, output_file=None, generate_report=False):
        """Run integration tests with specified parameters."""
        
        if self.runner and test_type in ["workflow", "all"]:
            # Use the programmatic runner for workflow tests
            return self._run_with_test_runner(test_type, verbose, markers, output_file, generate_report)
        else:
            # Fallback to direct pytest execution
            return self._run_with_pytest(test_type, verbose, markers, output_file)
    
    def _run_with_test_runner(self, test_type, verbose, markers, output_file, generate_report):
        """Run tests using the IntegrationTestRunner class."""
        import subprocess
        
        print(f"Running {test_type} tests using IntegrationTestRunner...")
        print("-" * 50)
        
        try:
            if test_type == "workflow":
                results = self.runner.run_workflow_tests(verbose=verbose)
            else:  # test_type == "all"
                # Run all integration tests using pytest but collect results
                results = self.runner.run_all_tests(verbose=verbose, markers=markers, output_file=output_file)
            
            # Generate report if requested
            if generate_report:
                report = self.runner.generate_test_report(results)
                report_file = "integration_test_report.md"
                with open(report_file, "w") as f:
                    f.write(report)
                print(f"\nTest report generated: {report_file}")
            
            # Check if all tests passed
            all_passed = all(r.get("success", False) for r in results.values())
            return 0 if all_passed else 1
            
        except KeyboardInterrupt:
            print("\nTest execution interrupted by user")
            return 130
        except Exception as e:
            print(f"Error running tests with IntegrationTestRunner: {e}")
            return self._run_with_pytest(test_type, verbose, markers, output_file)
    
    def _run_with_pytest(self, test_type, verbose, markers, output_file):
        """Fallback to direct pytest execution."""
        import subprocess
        
        # Base pytest command
        cmd = ["python", "-m", "pytest"]
        
        # Add test paths based on type
        if test_type == "all":
            cmd.append("tests/integration/")
        elif test_type == "workflow":
            cmd.extend([
                "tests/integration/test_loan_origination_workflow.py",
                "tests/integration/test_customer_mastery_lifecycle.py",
                "tests/integration/test_compliance_rule_enforcement.py"
            ])
        elif test_type == "cross_domain":
            cmd.append("tests/integration/test_cross_domain_integration.py")
        elif test_type == "utilities":
            cmd.append("tests/integration/test_data_utilities.py")
        elif test_type == "document":
            cmd.append("tests/integration/test_document_integration.py")
        else:
            cmd.append(f"tests/integration/{test_type}")
        
        # Add markers if specified
        if markers:
            cmd.extend(["-m", markers])
        
        # Add verbosity
        if verbose:
            cmd.append("-v")
        
        # Add output options
        cmd.extend(["--tb=short", "--strict-markers"])
        
        # Add output file if specified
        if output_file:
            cmd.extend(["--junitxml", output_file])
        
        print(f"Running command: {' '.join(cmd)}")
        print("-" * 50)
        
        # Execute tests
        try:
            result = subprocess.run(cmd, cwd=Path(__file__).parent)
            return result.returncode
        except KeyboardInterrupt:
            print("\nTest execution interrupted by user")
            return 130
        except Exception as e:
            print(f"Error running tests: {e}")
            return 1


def main():
    """Main execution function."""
    
    parser = argparse.ArgumentParser(
        description="Run integration tests with enhanced reporting and orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --type workflow --report
  %(prog)s --type all --markers "not slow" --output results.xml
  %(prog)s --list-tests
  %(prog)s --type cross_domain --quiet
        """
    )
    
    parser.add_argument(
        "--type", 
        choices=["all", "workflow", "cross_domain", "utilities", "document"],
        default="all",
        help="Type of tests to run"
    )
    
    parser.add_argument(
        "--markers",
        help="Pytest markers to filter tests (e.g., 'not slow')"
    )
    
    parser.add_argument(
        "--output",
        help="Output file for test results (JUnit XML format)"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Run tests in quiet mode"
    )
    
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Generate detailed markdown test report"
    )
    
    parser.add_argument(
        "--list-tests",
        action="store_true",
        help="List available integration tests"
    )
    
    parser.add_argument(
        "--check-runner",
        action="store_true",
        help="Check if IntegrationTestRunner is available"
    )
    
    args = parser.parse_args()
    
    # Initialize CLI runner
    cli_runner = CLITestRunner()
    
    if args.check_runner:
        if cli_runner.runner:
            print("✅ IntegrationTestRunner is available")
            print("Enhanced reporting and orchestration features enabled")
        else:
            print("⚠️  IntegrationTestRunner not available")
            print("Falling back to direct pytest execution")
        return 0
    
    if args.list_tests:
        print("Available integration tests:")
        print("- test_loan_origination_workflow.py")
        print("- test_customer_mastery_lifecycle.py") 
        print("- test_compliance_rule_enforcement.py")
        print("- test_cross_domain_integration.py")
        print("- test_data_utilities.py")
        print("- test_document_integration.py")
        print("\nTest types:")
        print("- all: Run all integration tests")
        print("- workflow: Run workflow tests only")
        print("- cross_domain: Run cross-domain tests only")
        print("- utilities: Run utility tests only")
        print("- document: Run document integration tests only")
        print("\nFeatures:")
        if cli_runner.runner:
            print("- Enhanced reporting with --report flag")
            print("- Programmatic test orchestration")
            print("- Detailed test result analysis")
        else:
            print("- Basic pytest execution")
            print("- JUnit XML output support")
        return 0
    
    # Run tests
    return_code = cli_runner.run_tests(
        test_type=args.type,
        verbose=not args.quiet,
        markers=args.markers,
        output_file=args.output,
        generate_report=args.report
    )
    
    if return_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with return code: {return_code}")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())