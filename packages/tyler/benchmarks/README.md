# Tyler Performance Benchmarks

This directory contains performance benchmarking tools for Tyler.

## Running Benchmarks

```bash
cd /path/to/packages/tyler
uv run python benchmarks/baseline.py
```

This will:
- Measure Agent initialization time
- Measure message creation performance
- Measure thread operations
- Save results to `baseline-performance.txt`

## Benchmark Files

- **`baseline.py`** - Main benchmark script (run this)
- **`baseline-*.txt`** - Output files (gitignored, generated on each run)

## When to Run Benchmarks

- Before major refactoring (establish baseline)
- After refactoring (validate no regression)
- Before releases (ensure performance)
- When investigating performance issues

## Interpreting Results

**Targets** (from original baseline):
- Agent init (simple): ~0.3ms
- Agent init (with tools): ~4ms
- Message creation: ~0.007ms per message
- Thread operations: ~0.01ms per message

**Acceptable variance**: ±5-10% is normal due to:
- System load
- I/O operations (module loading)
- Background processes

**When to worry**: If metrics are consistently >20% worse than baseline.

## Baseline Files

The `baseline-*.txt` files from the refactoring are kept for historical reference:
- `baseline-test-results.txt` - Test results before refactoring
- `baseline-coverage.txt` - Coverage before refactoring
- `baseline-performance.txt` - Performance before refactoring
- `baseline-summary.txt` - Summary of all metrics

These show the state before the 2025-01-11 refactoring and can be used for future comparisons.

---

**Last Updated**: 2025-01-11

