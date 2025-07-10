#!/usr/bin/env python3
"""
Development utilities for Space Monkey

This script provides common development tasks for working with space-monkey.
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_tests(coverage=False, verbose=False):
    """Run the test suite."""
    print("🧪 Running tests...")
    
    cmd = ["uv", "run", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=space_monkey", "--cov-report=term-missing"])
    
    result = subprocess.run(cmd)
    return result.returncode == 0


def run_linting():
    """Run code linting."""
    print("🔍 Running linting...")
    
    # Try to run common linters if available
    linters = [
        (["uv", "run", "black", "--check", "space_monkey/", "tests/"], "Black (formatting)"),
        (["uv", "run", "isort", "--check-only", "space_monkey/", "tests/"], "isort (imports)"),
        (["uv", "run", "flake8", "space_monkey/", "tests/"], "flake8 (style)"),
    ]
    
    all_passed = True
    for cmd, name in linters:
        try:
            print(f"  Running {name}...")
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                print(f"  ✓ {name} passed")
            else:
                print(f"  ✗ {name} failed")
                all_passed = False
        except FileNotFoundError:
            print(f"  ⚠ {name} not available (install with: uv add --dev {cmd[2]})")
    
    return all_passed


def generate_example_agent():
    """Generate an example agent for testing."""
    print("🐒 Generating example agent...")
    
    cmd = [
        "uv", "run", "space-monkey", "generate", "agent", "example-bot",
        "--description", "An example Slack bot for testing",
        "--tools", "notion:notion-search",
        "--tools", "slack:send-message",
        "--sub-agents", "helper",
        "--bot-user-id",
        "--citations",
        "--guidelines", "Always be helpful and test thoroughly",
        "--output-dir", "./dev-test-agent"
    ]
    
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("✓ Example agent generated in ./dev-test-agent/")
        return True
    else:
        print("✗ Failed to generate example agent")
        return False


def clean_dev_files():
    """Clean up development files."""
    print("🧹 Cleaning development files...")
    
    patterns_to_clean = [
        "**/__pycache__",
        "**/*.pyc", 
        "**/*.pyo",
        ".pytest_cache",
        ".coverage",
        "htmlcov/",
        "dev-test-agent/",
        "generated_hr_bot/",
        "*.egg-info/"
    ]
    
    cleaned = 0
    for pattern in patterns_to_clean:
        for path in Path(".").glob(pattern):
            if path.is_file():
                path.unlink()
                cleaned += 1
            elif path.is_dir():
                import shutil
                shutil.rmtree(path)
                cleaned += 1
    
    print(f"✓ Cleaned {cleaned} files/directories")


def run_type_checking():
    """Run type checking with mypy if available."""
    print("🔍 Running type checking...")
    
    try:
        cmd = ["uv", "run", "mypy", "space_monkey/"]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print("✓ Type checking passed")
            return True
        else:
            print("✗ Type checking failed")
            return False
    except FileNotFoundError:
        print("⚠ mypy not available (install with: uv add --dev mypy)")
        return True


def run_performance_tests():
    """Run performance tests specifically."""
    print("⚡ Running performance tests...")
    
    cmd = ["uv", "run", "pytest", "tests/test_performance.py", "-v"]
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    """Main development script."""
    parser = argparse.ArgumentParser(description="Space Monkey development utilities")
    parser.add_argument("command", choices=[
        "test", "lint", "example", "clean", "type-check", "perf", "all"
    ], help="Development command to run")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("🐒 Space Monkey Development Tools")
    print("=" * 40)
    
    success = True
    
    if args.command == "test":
        success = run_tests(coverage=args.coverage, verbose=args.verbose)
    
    elif args.command == "lint":
        success = run_linting()
    
    elif args.command == "example":
        success = generate_example_agent()
    
    elif args.command == "clean":
        clean_dev_files()
    
    elif args.command == "type-check":
        success = run_type_checking()
    
    elif args.command == "perf":
        success = run_performance_tests()
    
    elif args.command == "all":
        print("\n1. Cleaning...")
        clean_dev_files()
        
        print("\n2. Running linting...")
        lint_success = run_linting()
        
        print("\n3. Running type checking...")
        type_success = run_type_checking()
        
        print("\n4. Running tests...")
        test_success = run_tests(coverage=True, verbose=args.verbose)
        
        print("\n5. Running performance tests...")
        perf_success = run_performance_tests()
        
        print("\n6. Generating example...")
        example_success = generate_example_agent()
        
        success = all([lint_success, type_success, test_success, perf_success, example_success])
        
        print(f"\n{'🎉 All checks passed!' if success else '❌ Some checks failed'}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 