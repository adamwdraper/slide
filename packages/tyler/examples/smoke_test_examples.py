#!/usr/bin/env python3
"""
Smoke test script to run selected examples in sequence.
This helps with manual testing before releases.
"""
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Examples to run in order
EXAMPLES_TO_RUN = [
    "001_docs_introduction.py",
    "002_basic.py", 
    "003_docs_quickstart.py",
    "004_streaming.py",
    "100_tools_basic.py",
    "101_tools_streaming.py",
    "102_selective_tools.py",
    "200_attachments.py"
]

def print_separator(char: str = "=", length: int = 80) -> None:
    """Print a separator line."""
    print(char * length)

def print_header(title: str) -> None:
    """Print a formatted header."""
    print_separator("=")
    print(f"🚀 {title}")
    print_separator("=")
    print()

def run_example(example_file: str) -> Tuple[bool, str]:
    """
    Run a single example file using uv.
    Returns (success, output_or_error)
    """
    print(f"📄 Running: {example_file}")
    print_separator("-", 60)
    
    try:
        # Run the example using uv from the workspace root
        # Going up 3 levels from examples/ to reach the workspace root
        workspace_root = Path(__file__).parent.parent.parent.parent
        cmd = ["uv", "run", f"packages/tyler/examples/{example_file}"]
        
        result = subprocess.run(
            cmd,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout per example
        )
        
        if result.returncode == 0:
            print(result.stdout)
            if result.stderr:
                print("Warnings/Info:", result.stderr)
            return True, "Success"
        else:
            error_msg = f"Exit code: {result.returncode}\n"
            if result.stdout:
                error_msg += f"Output:\n{result.stdout}\n"
            if result.stderr:
                error_msg += f"Error:\n{result.stderr}"
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, "Timeout: Example took longer than 30 seconds"
    except Exception as e:
        return False, f"Exception: {str(e)}"

def main():
    """Run all examples and report results."""
    print_header("Tyler Examples Smoke Test")
    print(f"Running {len(EXAMPLES_TO_RUN)} examples...\n")
    
    results: List[Tuple[str, bool, str]] = []
    successful = 0
    failed = 0
    
    for i, example in enumerate(EXAMPLES_TO_RUN, 1):
        print(f"\n[{i}/{len(EXAMPLES_TO_RUN)}] ", end="")
        
        success, message = run_example(example)
        results.append((example, success, message))
        
        if success:
            successful += 1
            print("✅ PASSED")
        else:
            failed += 1
            print("❌ FAILED")
            print(f"Error: {message}")
        
        # Brief pause between examples to see output clearly
        if i < len(EXAMPLES_TO_RUN):
            time.sleep(1)
        
        print()
    
    # Print summary
    print_header("Test Summary")
    print(f"Total examples: {len(EXAMPLES_TO_RUN)}")
    print(f"✅ Passed: {successful}")
    print(f"❌ Failed: {failed}")
    print()
    
    if failed > 0:
        print("Failed examples:")
        for example, success, message in results:
            if not success:
                print(f"  - {example}")
                print(f"    {message.split(chr(10))[0]}")  # First line of error
        print()
        
    # Exit with error code if any failed
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    print("💡 Tip: Make sure you have your API keys set in .env file")
    print("   This script will run examples that make real API calls.\n")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Smoke test interrupted by user")
        sys.exit(1)
