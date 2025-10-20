"""
Performance test runner and configuration.

Provides a unified interface to run all performance tests with different
configurations and generate comprehensive reports.
"""

import argparse
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from main import app


class PerformanceTestConfig:
    """Configuration for performance tests."""
    
    def __init__(self):
        self.test_configs = {
            "quick": {
                "description": "Quick performance validation",
                "api_load": {"requests": 25, "workers": 5},
                "blockchain": {"operations": 15, "workers": 3},
                "database": {"operations": 30, "workers": 6},
                "stress": {"duration": 20, "workers": 8}
            },
            "standard": {
                "description": "Standard performance testing",
                "api_load": {"requests": 100, "workers": 10},
                "blockchain": {"operations": 50, "workers": 8},
                "database": {"operations": 80, "workers": 12},
                "stress": {"duration": 60, "workers": 15}
            },
            "comprehensive": {
                "description": "Comprehensive performance testing",
                "api_load": {"requests": 200, "workers": 20},
                "blockchain": {"operations": 100, "workers": 15},
                "database": {"operations": 150, "workers": 20},
                "stress": {"duration": 120, "workers": 25}
            },
            "stress": {
                "description": "Stress testing with high load",
                "api_load": {"requests": 500, "workers": 50},
                "blockchain": {"operations": 200, "workers": 30},
                "database": {"operations": 300, "workers": 40},
                "stress": {"duration": 300, "workers": 50}
            }
        }


class PerformanceTestRunner:
    """Main performance test runner."""
    
    def __init__(self, config_name: str = "standard"):
        self.config = PerformanceTestConfig()
        self.config_name = config_name
        self.test_config = self.config.test_configs.get(config_name, self.config.test_configs["standard"])
        
        self.results_dir = Path("performance_results")
        self.results_dir.mkdir(exist_ok=True)
        
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance tests with current configuration."""
        print(f"Starting performance test suite: {self.config_name}")
        print(f"Configuration: {self.test_config['description']}")
        print("-" * 60)
        
        self.start_time = datetime.utcnow()
        
        try:
            # Run API load tests
            print("Running API load tests...")
            self.test_results["api_load"] = self._run_api_load_tests()
            
            # Run blockchain throughput tests
            print("Running blockchain throughput tests...")
            self.test_results["blockchain"] = self._run_blockchain_tests()
            
            # Run database performance tests
            print("Running database performance tests...")
            self.test_results["database"] = self._run_database_tests()
            
            # Run stress tests
            print("Running stress tests...")
            self.test_results["stress"] = self._run_stress_tests()
            
            # Run benchmark suite
            print("Running benchmark suite...")
            self.test_results["benchmark"] = self._run_benchmark_suite()
            
        except Exception as e:
            print(f"Error during test execution: {e}")
            self.test_results["error"] = str(e)
        
        self.end_time = datetime.utcnow()
        
        # Generate final report
        report_path = self._generate_final_report()
        
        print("-" * 60)
        print(f"Performance test suite completed!")
        print(f"Total duration: {(self.end_time - self.start_time).total_seconds():.1f} seconds")
        print(f"Report generated: {report_path}")
        
        return self.test_results
    
    def _run_api_load_tests(self) -> Dict[str, Any]:
        """Run API load tests."""
        config = self.test_config["api_load"]
        
        try:
            # Run pytest with specific test file and configuration
            cmd = [
                sys.executable, "-m", "pytest",
                "backend/tests/performance/test_api_load.py",
                "-v", "--tb=short",
                f"--requests={config['requests']}",
                f"--workers={config['workers']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "config": config
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "config": config}
        except Exception as e:
            return {"status": "error", "error": str(e), "config": config}
    
    def _run_blockchain_tests(self) -> Dict[str, Any]:
        """Run blockchain throughput tests."""
        config = self.test_config["blockchain"]
        
        try:
            cmd = [
                sys.executable, "-m", "pytest",
                "backend/tests/performance/test_blockchain_throughput.py",
                "-v", "--tb=short",
                f"--operations={config['operations']}",
                f"--workers={config['workers']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "config": config
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "config": config}
        except Exception as e:
            return {"status": "error", "error": str(e), "config": config}
    
    def _run_database_tests(self) -> Dict[str, Any]:
        """Run database performance tests."""
        config = self.test_config["database"]
        
        try:
            cmd = [
                sys.executable, "-m", "pytest",
                "backend/tests/performance/test_database_performance.py",
                "-v", "--tb=short",
                f"--operations={config['operations']}",
                f"--workers={config['workers']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "config": config
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "config": config}
        except Exception as e:
            return {"status": "error", "error": str(e), "config": config}
    
    def _run_stress_tests(self) -> Dict[str, Any]:
        """Run stress tests."""
        config = self.test_config["stress"]
        
        try:
            cmd = [
                sys.executable, "-m", "pytest",
                "backend/tests/performance/test_stress_scenarios.py",
                "-v", "--tb=short",
                f"--duration={config['duration']}",
                f"--workers={config['workers']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=config["duration"] + 120)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "config": config
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "config": config}
        except Exception as e:
            return {"status": "error", "error": str(e), "config": config}
    
    def _run_benchmark_suite(self) -> Dict[str, Any]:
        """Run comprehensive benchmark suite."""
        try:
            cmd = [
                sys.executable, "-m", "pytest",
                "backend/tests/performance/benchmark_runner.py::TestPerformanceBenchmarks::test_run_full_benchmark_suite",
                "-v", "--tb=short"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _generate_final_report(self) -> str:
        """Generate final performance test report."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = self.results_dir / f"performance_test_report_{self.config_name}_{timestamp}.html"
        
        # Generate HTML report
        html_content = self._create_html_report()
        
        try:
            with open(report_file, 'w') as f:
                f.write(html_content)
            
            # Also save raw results as JSON
            json_file = report_file.with_suffix('.json')
            with open(json_file, 'w') as f:
                json.dump({
                    "config_name": self.config_name,
                    "config": self.test_config,
                    "start_time": self.start_time.isoformat(),
                    "end_time": self.end_time.isoformat(),
                    "duration_seconds": (self.end_time - self.start_time).total_seconds(),
                    "results": self.test_results
                }, f, indent=2)
            
            return str(report_file)
            
        except Exception as e:
            print(f"Error generating report: {e}")
            return f"Error: {e}"
    
    def _create_html_report(self) -> str:
        """Create HTML performance test report."""
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Performance Test Report - {self.config_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ margin: 20px 0; }}
        .test-section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .passed {{ background-color: #e8f5e8; border-left: 4px solid #4caf50; }}
        .failed {{ background-color: #ffebee; border-left: 4px solid #f44336; }}
        .timeout {{ background-color: #fff3e0; border-left: 4px solid #ff9800; }}
        .error {{ background-color: #fce4ec; border-left: 4px solid #e91e63; }}
        pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Performance Test Report</h1>
        <p><strong>Configuration:</strong> {self.config_name} - {self.test_config['description']}</p>
        <p><strong>Start Time:</strong> {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>End Time:</strong> {self.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Total Duration:</strong> {duration:.1f} seconds</p>
    </div>
    
    <div class="summary">
        <h2>Test Summary</h2>
        <table>
            <tr>
                <th>Test Category</th>
                <th>Status</th>
                <th>Configuration</th>
            </tr>
"""
        
        for test_name, result in self.test_results.items():
            if test_name == "error":
                continue
            
            status = result.get("status", "unknown")
            config = result.get("config", {})
            config_str = ", ".join([f"{k}: {v}" for k, v in config.items()]) if config else "N/A"
            
            html += f"""
            <tr class="{status}">
                <td>{test_name.replace('_', ' ').title()}</td>
                <td>{status.title()}</td>
                <td>{config_str}</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
"""
        
        # Detailed results for each test category
        for test_name, result in self.test_results.items():
            if test_name == "error":
                continue
            
            status = result.get("status", "unknown")
            
            html += f"""
    <div class="test-section {status}">
        <h3>{test_name.replace('_', ' ').title()}</h3>
        <p><strong>Status:</strong> {status.title()}</p>
"""
            
            if "config" in result:
                html += f"<p><strong>Configuration:</strong> {result['config']}</p>"
            
            if "stdout" in result and result["stdout"]:
                html += f"""
        <h4>Test Output</h4>
        <pre>{result['stdout']}</pre>
"""
            
            if "stderr" in result and result["stderr"]:
                html += f"""
        <h4>Error Output</h4>
        <pre>{result['stderr']}</pre>
"""
            
            if "error" in result:
                html += f"""
        <h4>Error Details</h4>
        <pre>{result['error']}</pre>
"""
            
            html += "</div>"
        
        # Overall error if present
        if "error" in self.test_results:
            html += f"""
    <div class="test-section error">
        <h3>Overall Test Error</h3>
        <pre>{self.test_results['error']}</pre>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        return html
    
    def run_locust_tests(self, host: str = "http://localhost:8000", 
                        users: int = 50, spawn_rate: int = 5, 
                        run_time: str = "300s") -> Dict[str, Any]:
        """Run Locust load tests."""
        print(f"Running Locust load tests...")
        print(f"  Host: {host}")
        print(f"  Users: {users}")
        print(f"  Spawn Rate: {spawn_rate}")
        print(f"  Run Time: {run_time}")
        
        try:
            cmd = [
                "locust",
                "-f", "backend/tests/performance/locust_load_tests.py",
                "--host", host,
                "--users", str(users),
                "--spawn-rate", str(spawn_rate),
                "--run-time", run_time,
                "--headless",
                "--html", str(self.results_dir / f"locust_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html")
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=int(run_time.rstrip('s')) + 60)
            
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "config": {
                    "host": host,
                    "users": users,
                    "spawn_rate": spawn_rate,
                    "run_time": run_time
                }
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except FileNotFoundError:
            return {"status": "error", "error": "Locust not installed. Install with: pip install locust"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


def main():
    """Main entry point for performance test runner."""
    parser = argparse.ArgumentParser(description="Run performance tests for blockchain financial platform")
    
    parser.add_argument(
        "--config", 
        choices=["quick", "standard", "comprehensive", "stress"],
        default="standard",
        help="Test configuration to use"
    )
    
    parser.add_argument(
        "--locust",
        action="store_true",
        help="Also run Locust load tests"
    )
    
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Host URL for Locust tests"
    )
    
    parser.add_argument(
        "--users",
        type=int,
        default=50,
        help="Number of users for Locust tests"
    )
    
    parser.add_argument(
        "--spawn-rate",
        type=int,
        default=5,
        help="Spawn rate for Locust tests"
    )
    
    parser.add_argument(
        "--run-time",
        default="300s",
        help="Run time for Locust tests"
    )
    
    args = parser.parse_args()
    
    # Create and run performance tests
    runner = PerformanceTestRunner(args.config)
    results = runner.run_all_tests()
    
    # Run Locust tests if requested
    if args.locust:
        locust_results = runner.run_locust_tests(
            host=args.host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            run_time=args.run_time
        )
        results["locust"] = locust_results
    
    # Print summary
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        if test_name == "error":
            continue
        status = result.get("status", "unknown")
        print(f"{test_name.replace('_', ' ').title()}: {status.upper()}")
    
    if "error" in results:
        print(f"Overall Error: {results['error']}")
    
    return 0 if all(r.get("status") == "passed" for r in results.values() if isinstance(r, dict)) else 1


if __name__ == "__main__":
    sys.exit(main())