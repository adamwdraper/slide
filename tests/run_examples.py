#!/usr/bin/env python3
"""
Test runner for Slide examples.

This script provides different ways to run example tests:
- All examples
- Smoke tests only  
- Specific examples
- Examples by category
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_pytest(args):
    """Run pytest with the given arguments using uv."""
    cmd = ["uv", "run", "pytest"] + args
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(description="Run Slide example tests")
    
    parser.add_argument(
        "--smoke", 
        action="store_true",
        help="Run only smoke tests (quick validation)"
    )
    
    parser.add_argument(
        "--category",
        choices=["getting-started", "use-cases", "integrations"],
        help="Run examples from specific category"
    )
    
    parser.add_argument(
        "--example",
        help="Run specific example (e.g., 'quickstart.py' or 'research-assistant/basic.py')"
    )
    
    parser.add_argument(
        "--no-api-key",
        action="store_true", 
        help="Deprecated: All examples now use load_dotenv() and handle missing API keys gracefully"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available examples"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("Available examples:")
        examples_dir = PROJECT_ROOT / "examples"
        for root, dirs, files in os.walk(examples_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    rel_path = Path(root).relative_to(examples_dir) / file
                    print(f"  {rel_path}")
        return 0
    
    # Build pytest arguments
    pytest_args = ["tests/test_examples.py"]
    
    if args.verbose:
        pytest_args.append("-v")
    
    if args.smoke:
        pytest_args.extend(["-m", "smoke"])
        print("Running smoke tests...")
        # Smoke tests don't need API keys, so skip the prompt
        
    elif args.category:
        # Run examples from specific category
        pytest_args.extend(["-k", args.category])
        print(f"Running {args.category} examples...")
        
    elif args.example:
        # Run specific example
        pytest_args.extend(["-k", args.example.replace('.py', '')])
        print(f"Running example: {args.example}")
        
    else:
        # Run all examples
        pytest_args.extend(["-m", "examples"])
        print("Running all example tests...")
    
    if args.no_api_key:
        # This flag is now deprecated - all examples handle missing API keys gracefully
        print("Note: --no-api-key flag is deprecated. Examples now use load_dotenv() and handle missing API keys gracefully.")
    
    # Check workspace setup
    if not (PROJECT_ROOT / "uv.lock").exists():
        print("\n⚠️  Warning: No uv.lock found!")
        print("This project uses uv workspace. Please run from project root:")
        print("  uv sync --dev")
        print("")
    
    # Check for API key and warn if missing (but skip prompt for smoke tests)
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        print("\n⚠️  Warning: No API key found!")
        print("Set OPENAI_API_KEY or ANTHROPIC_API_KEY to run all examples.")
        print("Some examples will be skipped.\n")
        
        if not args.no_api_key and not args.smoke:
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Exiting. Set an API key or use --no-api-key flag.")
                return 1
    
    # Run the tests
    result = run_pytest(pytest_args)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())