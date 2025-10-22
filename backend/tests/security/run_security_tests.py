#!/usr/bin/env python3
"""
Security test execution script.

Provides different test execution modes for security tests.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_security_tests(test_type="all", verbose=True, markers=None, output_file=None):
    """Run security tests with specified parameters."""
    
    # Base pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test paths based on type
    if test_type == "all":
        cmd.append("tests/security/")
    elif test_type == "auth":
        cmd.append("tests/security/test_authentication_security.py")
    elif test_type == "encryption":
        cmd.append("tests/security/test_data_encryption_privacy.py")
    elif test_type == "audit":
        cmd.append("tests/security/test_audit_trail_immutability.py")
    elif test_type == "compliance":
        cmd.append("tests/security/test_regulatory_compliance_validation.py")
    elif test_type == "vulnerability":
        cmd.append("tests/security/test_vulnerability_scanning.py")
    elif test_type == "suite":
        cmd.append("tests/security/test_security_suite.py")
    else:
        cmd.append(f"tests/security/{test_type}")
    
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
        description="Run security tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --type all
  %(prog)s --type auth --markers "not slow"
  %(prog)s --type suite --output results.xml
        """
    )
    
    parser.add_argument(
        "--type", 
        choices=["all", "auth", "encryption", "audit", "compliance", "vulnerability", "suite"],
        default="all",
        help="Type of security tests to run"
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
    return_code = run_security_tests(
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
