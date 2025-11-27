#!/usr/bin/env python3
"""
Test runner script for the procurement platform.

This script provides various options for running tests including:
- All tests
- Specific test modules
- Coverage reporting
- Verbose output
- Performance testing
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, description=""):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    if description:
        print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for the procurement platform")
    parser.add_argument("--module", "-m", help="Run specific test module (e.g., test_auth)")
    parser.add_argument("--coverage", "-c", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", "-f", action="store_true", help="Skip slow tests")
    parser.add_argument("--integration", "-i", action="store_true", help="Run integration tests only")
    parser.add_argument("--unit", "-u", action="store_true", help="Run unit tests only")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--html-report", action="store_true", help="Generate HTML coverage report")
    
    args = parser.parse_args()
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    # Add test path
    if args.module:
        test_path = f"tests/api/v1/test_{args.module}.py"
        if not Path(test_path).exists():
            test_path = f"tests/{args.module}"
        pytest_cmd.append(test_path)
    else:
        pytest_cmd.append("tests/")
    
    # Add verbose flag
    if args.verbose:
        pytest_cmd.extend(["-v", "-s"])
    
    # Add parallel execution
    if args.parallel:
        pytest_cmd.extend(["-n", "auto"])
    
    # Add markers for test types
    if args.fast:
        pytest_cmd.extend(["-m", "not slow"])
    elif args.integration:
        pytest_cmd.extend(["-m", "integration"])
    elif args.unit:
        pytest_cmd.extend(["-m", "not integration"])
    
    # Coverage options
    if args.coverage:
        pytest_cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
        
        if args.html_report:
            pytest_cmd.append("--cov-report=html")
    
    # Additional pytest options
    pytest_cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--disable-warnings"
    ])
    
    print("🧪 Procurement Platform Test Suite")
    print("=" * 50)
    
    # Check if dependencies are installed
    print("Checking test dependencies...")
    try:
        import pytest
        import httpx
        import pytest_asyncio
        print("✅ All test dependencies found")
    except ImportError as e:
        print(f"❌ Missing test dependency: {e}")
        print("Install with: pip install pytest pytest-asyncio httpx")
        return 1
    
    # Run the tests
    success = run_command(pytest_cmd, "Running pytest")
    
    if success:
        print("\n🎉 All tests passed!")
        
        if args.coverage:
            print("\n📊 Coverage Report Generated")
            if args.html_report:
                print("HTML report: htmlcov/index.html")
            print("XML report: coverage.xml")
    else:
        print("\n❌ Some tests failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
