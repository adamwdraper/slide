#!/usr/bin/env python3
"""
Smoke test script to run selected examples in sequence.
This helps with manual testing before releases.
"""
import subprocess
import sys
import time
import os
import logging
from pathlib import Path
from typing import List, Tuple

# Suppress ALL LiteLLM logging (including errors)
# We need to set this before any imports that might load litellm
os.environ["LITELLM_LOG"] = "CRITICAL"  # Highest level - only critical errors
os.environ["LITELLM_SUPPRESS_DEBUG_LOGS"] = "true"

# Suppress Weave logging
os.environ["WEAVE_DISABLE_ANALYTICS"] = "true"
os.environ["WEAVE_SUPPRESS_LOGS"] = "true"

# Configure logging to suppress ALL LiteLLM messages
# Create a null handler to send logs to nowhere
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

logging.basicConfig(level=logging.WARNING)
null_handler = NullHandler()

for logger_name in [
    'litellm',
    'litellm.utils',
    'litellm.llms',
    'litellm._logging',
    'LiteLLM',
    'weave',
    'weave.trace',
    'weave.trace.op',
    'wandb',
]:
    logger = logging.getLogger(logger_name)
    logger.handlers = [null_handler]  # Replace all handlers with null handler
    logger.setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL to suppress everything
    logger.disabled = True  # Completely disable the logger
    logger.propagate = False

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

def is_filtered_log_line(line: str) -> bool:
    """Check if a log line should be filtered out (LiteLLM/Weave noise)."""
    # Match LiteLLM log patterns with timestamps
    if "- LiteLLM" in line and any(level in line for level in ["INFO:", "ERROR:", "WARNING:", "DEBUG:"]):
        return True
    if "- LiteLLM -" in line:
        return True
    if line.strip().startswith("LiteLLM") and "completion()" in line:
        return True
    
    # Match Weave log patterns
    if line.strip().startswith("weave:"):
        return True
    if "weave.trace.op" in line:
        return True
    if "🍩" in line and "wandb.ai" in line:
        return True
    
    return False

def run_example(example_file: str) -> Tuple[bool, str]:
    """
    Run a single example file using uv.
    Returns (success, output_or_error)
    """
    print(f"📄 Running: {example_file}")
    print_separator("-", 60)
    
    try:
        # Run the example using uv from the workspace root
        # Going up 1 level from scripts/ to reach the workspace root
        workspace_root = Path(__file__).parent.parent
        cmd = ["uv", "run", f"packages/tyler/examples/{example_file}"]
        
        # Prepare environment with LiteLLM and Weave suppression
        env = os.environ.copy()
        env["LITELLM_LOG"] = "CRITICAL"
        env["LITELLM_SUPPRESS_DEBUG_LOGS"] = "true"
        env["WEAVE_DISABLE_ANALYTICS"] = "true"
        env["WEAVE_SUPPRESS_LOGS"] = "true"
        
        result = subprocess.run(
            cmd,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout per example
            env=env
        )
        
        if result.returncode == 0:
            # Always print stdout - this contains the actual example output
            # (streams, tool outputs, agent responses, etc.)
            print(result.stdout)
            if result.stderr:
                # Filter out LiteLLM and Weave log lines
                filtered_stderr = "\n".join(
                    line for line in result.stderr.split("\n")
                    if not is_filtered_log_line(line)
                )
                if filtered_stderr.strip():
                    print("Warnings/Info:", filtered_stderr)
            return True, "Success"
        else:
            error_msg = f"Exit code: {result.returncode}\n"
            if result.stdout:
                error_msg += f"Output:\n{result.stdout}\n"
            if result.stderr:
                # Filter out LiteLLM and Weave log lines in error messages too
                filtered_stderr = "\n".join(
                    line for line in result.stderr.split("\n")
                    if not is_filtered_log_line(line)
                )
                if filtered_stderr.strip():
                    error_msg += f"Error:\n{filtered_stderr}"
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
