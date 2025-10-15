#!/bin/bash
# Test harness for release script constraint logic

set -e

echo "🧪 Testing Release Script Constraint Logic"
echo "=========================================="
echo ""

# Setup test fixtures
TEST_DIR="test_packages"
mkdir -p "$TEST_DIR"/{tyler,space-monkey}

# Cleanup function
cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_func="$2"
    
    echo -n "  Testing: $test_name... "
    if $test_func; then
        echo "✓ PASSED"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "✗ FAILED"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# AC1: Tyler constraints set (no existing constraint)
test_tyler_constraints_no_existing() {
    cat > "$TEST_DIR/tyler/pyproject.toml" << 'EOF'
[project]
dependencies = [
    "slide-narrator",
    "slide-lye",
    "litellm>=1.63.0",
]
EOF

    # Run constraint-setting logic
    NEW_VERSION="3.1.1"
    sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    sed -i.bak "s/\"slide-lye[^\"]*\"/\"slide-lye>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    
    # Verify
    grep -q "slide-narrator>=3.1.1" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "slide-lye>=3.1.1" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "litellm>=1.63.0" "$TEST_DIR/tyler/pyproject.toml"
}

# AC2: Space-monkey constraints set
test_space_monkey_constraints() {
    cat > "$TEST_DIR/space-monkey/pyproject.toml" << 'EOF'
[project]
dependencies = [
    "slide-tyler",
    "slide-narrator",
    "slack-bolt>=1.23.0",
]
EOF

    NEW_VERSION="3.1.1"
    sed -i.bak "s/\"slide-tyler[^\"]*\"/\"slide-tyler>=$NEW_VERSION\"/g" \
        "$TEST_DIR/space-monkey/pyproject.toml"
    sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
        "$TEST_DIR/space-monkey/pyproject.toml"
    
    grep -q "slide-tyler>=3.1.1" "$TEST_DIR/space-monkey/pyproject.toml" && \
    grep -q "slide-narrator>=3.1.1" "$TEST_DIR/space-monkey/pyproject.toml" && \
    grep -q "slack-bolt>=1.23.0" "$TEST_DIR/space-monkey/pyproject.toml"
}

# AC3: Override existing constraints
test_override_existing_constraint() {
    cat > "$TEST_DIR/tyler/pyproject.toml" << 'EOF'
[project]
dependencies = [
    "slide-narrator>=3.0.0",
    "slide-lye>=2.9.0",
]
EOF

    NEW_VERSION="3.1.1"
    sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    sed -i.bak "s/\"slide-lye[^\"]*\"/\"slide-lye>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    
    grep -q "slide-narrator>=3.1.1" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "slide-lye>=3.1.1" "$TEST_DIR/tyler/pyproject.toml"
}

# AC4: External dependencies unchanged
test_external_deps_unchanged() {
    cat > "$TEST_DIR/tyler/pyproject.toml" << 'EOF'
[project]
dependencies = [
    "slide-narrator",
    "litellm>=1.63.0",
    "openai>=1.61.0",
    "tiktoken>=0.8.0",
]
EOF

    NEW_VERSION="3.1.1"
    sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    
    grep -q "slide-narrator>=3.1.1" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "litellm>=1.63.0" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "openai>=1.61.0" "$TEST_DIR/tyler/pyproject.toml" && \
    grep -q "tiktoken>=0.8.0" "$TEST_DIR/tyler/pyproject.toml"
}

# AC5: Handle exact pins (theoretical)
test_exact_pin_override() {
    cat > "$TEST_DIR/tyler/pyproject.toml" << 'EOF'
[project]
dependencies = [
    "slide-narrator==3.0.0",
]
EOF

    NEW_VERSION="3.1.1"
    sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
        "$TEST_DIR/tyler/pyproject.toml"
    
    grep -q "slide-narrator>=3.1.1" "$TEST_DIR/tyler/pyproject.toml"
}

# Run all tests
echo "Running constraint-setting tests:"
echo ""

run_test "AC1: Tyler constraints set (no existing)" test_tyler_constraints_no_existing
run_test "AC2: Space-monkey constraints set" test_space_monkey_constraints
run_test "AC3: Override existing constraints" test_override_existing_constraint
run_test "AC4: External deps unchanged" test_external_deps_unchanged
run_test "AC5: Exact pin override (theoretical)" test_exact_pin_override

# Summary
echo ""
echo "=========================================="
echo "Test Results: $TESTS_PASSED passed, $TESTS_FAILED failed"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi

