"""
Baseline Performance Benchmarks for Tyler Refactoring

Run this before and after each refactoring phase to ensure no performance regression.
Target: Performance must remain within 5% of baseline.
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any
import statistics

# Direct imports to avoid initialization overhead in measurements
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tyler import Agent, Thread, Message


def measure_time(func, iterations=10):
    """Measure function execution time over multiple iterations"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds
    
    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times)
    }


async def measure_time_async(func, iterations=10):
    """Measure async function execution time over multiple iterations"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds
    
    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times)
    }


def benchmark_agent_init_simple():
    """Measure simple Agent initialization time"""
    def create_agent():
        agent = Agent(
            model_name="gpt-4.1",
            purpose="Test agent"
        )
    
    return measure_time(create_agent, iterations=20)


def benchmark_agent_init_with_tools():
    """Measure Agent initialization with tools"""
    def create_agent():
        agent = Agent(
            model_name="gpt-4.1",
            purpose="Test agent",
            tools=["web"]
        )
    
    return measure_time(create_agent, iterations=10)


def benchmark_message_creation():
    """Measure message creation time"""
    def create_messages():
        for _ in range(100):
            Message(role="user", content="test message")
    
    result = measure_time(create_messages, iterations=10)
    # Divide by 100 to get per-message time
    return {k: v/100 for k, v in result.items()}


def benchmark_thread_creation():
    """Measure thread creation and message addition"""
    def create_thread_with_messages():
        thread = Thread()
        for i in range(10):
            thread.add_message(Message(role="user", content=f"message {i}"))
    
    result = measure_time(create_thread_with_messages, iterations=20)
    # Divide by 10 to get per-message time
    return {k: v/10 for k, v in result.items()}


async def run_benchmarks():
    """Run all benchmarks and return results"""
    print("=" * 70)
    print("Tyler Performance Benchmarks - Baseline")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print()
    
    results = {}
    
    # Agent initialization (simple)
    print("📊 Benchmark: Agent initialization (simple)...")
    results['agent_init_simple'] = benchmark_agent_init_simple()
    print(f"   Mean: {results['agent_init_simple']['mean']:.2f}ms")
    print(f"   Median: {results['agent_init_simple']['median']:.2f}ms")
    print(f"   StdDev: {results['agent_init_simple']['stdev']:.2f}ms")
    print()
    
    # Agent initialization (with tools)
    print("📊 Benchmark: Agent initialization (with tools)...")
    results['agent_init_with_tools'] = benchmark_agent_init_with_tools()
    print(f"   Mean: {results['agent_init_with_tools']['mean']:.2f}ms")
    print(f"   Median: {results['agent_init_with_tools']['median']:.2f}ms")
    print(f"   StdDev: {results['agent_init_with_tools']['stdev']:.2f}ms")
    print()
    
    # Message creation
    print("📊 Benchmark: Message creation...")
    results['message_creation'] = benchmark_message_creation()
    print(f"   Mean: {results['message_creation']['mean']:.4f}ms per message")
    print(f"   Median: {results['message_creation']['median']:.4f}ms per message")
    print()
    
    # Thread creation with messages
    print("📊 Benchmark: Thread creation + message addition...")
    results['thread_with_messages'] = benchmark_thread_creation()
    print(f"   Mean: {results['thread_with_messages']['mean']:.4f}ms per message")
    print(f"   Median: {results['thread_with_messages']['median']:.4f}ms per message")
    print()
    
    print("=" * 70)
    print("✅ Baseline benchmarks complete!")
    print()
    print("💡 Save these results for comparison after refactoring.")
    print("   Performance must remain within 5% of these baseline values.")
    print("=" * 70)
    
    return results


def save_results(results: Dict[str, Any], filename: str = "baseline-performance.txt"):
    """Save benchmark results to file"""
    with open(filename, 'w') as f:
        f.write("Tyler Performance Benchmarks - Baseline\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Python: {sys.version.split()[0]}\n")
        f.write("=" * 70 + "\n\n")
        
        for name, metrics in results.items():
            f.write(f"{name}:\n")
            for metric, value in metrics.items():
                f.write(f"  {metric}: {value:.4f}ms\n")
            f.write("\n")
        
        f.write("=" * 70 + "\n")
        f.write("Target: Performance must remain within 5% after refactoring\n")


if __name__ == "__main__":
    results = asyncio.run(run_benchmarks())
    
    # Save to file
    save_path = os.path.join(os.path.dirname(__file__), "..", "baseline-performance.txt")
    save_results(results, save_path)
    print(f"\n💾 Results saved to: {save_path}")

