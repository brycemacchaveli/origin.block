#!/usr/bin/env python3
"""
Integration test execution script.

Provides different test execution modes and comprehensive reporting.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_tests(test_type="all", verbose=True, markers=None, output_file=None):
    """Run integration tests with specified parameters."""
    
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
    
    parser = argparse.ArgumentParser(description="Run integration tests")
    
    parser.add_argument(
        "--type", 
        choices=["all", "workflow", "cross_domain", "utilities"],
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
        "--list-tests",
        action="store_true",
        help="List available integration tests"
    )
    
    args = parser.parse_args()
    
    if args.list_tests:
        print("Available integration tests:")
        print("- test_loan_origination_workflow.py")
        print("- test_customer_mastery_lifecycle.py") 
        print("- test_compliance_rule_enforcement.py")
        print("- test_cross_domain_integration.py")
        print("- test_data_utilities.py")
        print("\nTest types:")
        print("- all: Run all integration tests")
        print("- workflow: Run workflow tests only")
        print("- cross_domain: Run cross-domain tests only")
        print("- utilities: Run utility tests only")
        return 0
    
    # Run tests
    return_code = run_tests(
        test_type=args.type,
        verbose=not args.quiet,
        markers=args.markers,
        output_file=args.output
    )
    
    if return_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with return code: {return_code}")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())