#!/usr/bin/env python3
"""
ETL test execution script.

Provides different test execution modes for ETL tests.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_etl_tests(test_type="all", verbose=True, markers=None, output_file=None):
    """Run ETL tests with specified parameters."""
    
    # Base pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test paths based on type
    if test_type == "all":
        cmd.append("tests/etl/")
    elif test_type == "transformers":
        cmd.extend([
            "tests/etl/test_base_transformer.py",
            "tests/etl/test_customer_transformer.py",
            "tests/etl/test_loan_events_transformer.py",
            "tests/etl/test_compliance_events_transformer.py"
        ])
    elif test_type == "analytics":
        cmd.append("tests/etl/analytics/")
    elif test_type == "orchestration":
        cmd.append("tests/etl/orchestration/")
    else:
        cmd.append(f"tests/etl/{test_type}")
    
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
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)
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
        description="Run ETL tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --type all
  %(prog)s --type transformers --markers "not slow"
  %(prog)s --type analytics --output results.xml
        """
    )
    
    parser.add_argument(
        "--type", 
        choices=["all", "transformers", "analytics", "orchestration"],
        default="all",
        help="Type of ETL tests to run"
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
    
    args = parser.parse_args()
    
    # Run tests
    return_code = run_etl_tests(
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
