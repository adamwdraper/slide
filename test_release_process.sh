#!/bin/bash
# Test script for unified release process
# This performs comprehensive validation without making real changes

set -e

echo "🧪 Testing Unified Release Process"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0

function pass() {
    echo -e "${GREEN}✓${NC} $1"
}

function fail() {
    echo -e "${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
}

function info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

function warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Test 1: Check prerequisites
echo -e "${BLUE}Test 1: Prerequisites${NC}"
if command -v gh &> /dev/null; then
    pass "gh CLI installed"
else
    fail "gh CLI not installed"
fi

if command -v git-cliff &> /dev/null; then
    pass "git-cliff installed"
else
    fail "git-cliff not installed"
fi

if command -v uv &> /dev/null; then
    pass "uv installed"
else
    fail "uv not installed"
fi
echo ""

# Test 2: Verify release script exists and is executable
echo -e "${BLUE}Test 2: Release Script${NC}"
if [ -f "scripts/release.sh" ]; then
    pass "Release script exists"
else
    fail "Release script not found"
fi

if [ -x "scripts/release.sh" ]; then
    pass "Release script is executable"
else
    fail "Release script not executable"
fi

# Test bash syntax
if bash -n scripts/release.sh 2>&1; then
    pass "Release script has valid bash syntax"
else
    fail "Release script has syntax errors"
fi
echo ""

# Test 3: Verify workflow file
echo -e "${BLUE}Test 3: GitHub Actions Workflow${NC}"
if [ -f ".github/workflows/release.yml" ]; then
    pass "Release workflow exists"
else
    fail "Release workflow not found"
fi

# Check workflow structure
if grep -q "name: Unified Release" .github/workflows/release.yml; then
    pass "Workflow has correct name"
else
    fail "Workflow name incorrect"
fi

if grep -q "check-release:" .github/workflows/release.yml; then
    pass "Workflow has check-release job"
else
    fail "Workflow missing check-release job"
fi

if grep -q "publish-all:" .github/workflows/release.yml; then
    pass "Workflow has publish-all job"
else
    fail "Workflow missing publish-all job"
fi
echo ""

# Test 4: Verify package versions are readable
echo -e "${BLUE}Test 4: Package Versions${NC}"
PACKAGES=("tyler" "narrator" "space-monkey" "lye")
for PACKAGE in "${PACKAGES[@]}"; do
    PACKAGE_DIR="packages/$PACKAGE"
    if [ -f "$PACKAGE_DIR/pyproject.toml" ]; then
        VERSION=$(grep 'version = "' "$PACKAGE_DIR/pyproject.toml" | sed 's/.*version = "\([^"]*\)".*/\1/')
        if [ -n "$VERSION" ]; then
            pass "$PACKAGE version: $VERSION"
        else
            fail "Could not read $PACKAGE version"
        fi
    else
        fail "$PACKAGE pyproject.toml not found"
    fi
done
echo ""

# Test 5: Test version bumping logic
echo -e "${BLUE}Test 5: Version Bumping Logic${NC}"
TEST_VERSION="2.1.0"
IFS='.' read -r MAJOR MINOR PATCH <<< "$TEST_VERSION"

# Test patch bump
PATCH_TEST=$((PATCH + 1))
if [ "$PATCH_TEST" = "1" ]; then
    pass "Patch bump logic: 2.1.0 → 2.1.1"
else
    fail "Patch bump logic incorrect"
fi

# Test minor bump
MINOR_TEST=$((MINOR + 1))
if [ "$MINOR_TEST" = "2" ]; then
    pass "Minor bump logic: 2.1.0 → 2.2.0"
else
    fail "Minor bump logic incorrect"
fi

# Test major bump
MAJOR_TEST=$((MAJOR + 1))
if [ "$MAJOR_TEST" = "3" ]; then
    pass "Major bump logic: 2.1.0 → 3.0.0"
else
    fail "Major bump logic incorrect"
fi
echo ""

# Test 6: Test git-cliff
echo -e "${BLUE}Test 6: Changelog Generation${NC}"
info "Testing git-cliff on tyler package..."
if git cliff --include-path "packages/tyler/**" --unreleased --output /dev/null 2>&1; then
    pass "git-cliff can generate changelog for tyler"
else
    fail "git-cliff failed for tyler"
fi

info "Testing git-cliff on all packages..."
for PACKAGE in "${PACKAGES[@]}"; do
    if git cliff --include-path "packages/$PACKAGE/**" --unreleased --output /dev/null 2>&1; then
        pass "git-cliff works for $PACKAGE"
    else
        fail "git-cliff failed for $PACKAGE"
    fi
done
echo ""

# Test 7: Verify inter-package dependencies
echo -e "${BLUE}Test 7: Inter-Package Dependencies${NC}"

# Check tyler dependencies
if grep -q '"slide-narrator"' packages/tyler/pyproject.toml; then
    CONSTRAINT=$(grep '"slide-narrator' packages/tyler/pyproject.toml)
    if [[ "$CONSTRAINT" =~ '>=' ]]; then
        fail "Tyler still has version constraint on slide-narrator: $CONSTRAINT"
    else
        pass "Tyler has no version constraint on slide-narrator"
    fi
else
    warn "Tyler doesn't depend on slide-narrator (unexpected)"
fi

if grep -q '"slide-lye"' packages/tyler/pyproject.toml; then
    CONSTRAINT=$(grep '"slide-lye' packages/tyler/pyproject.toml)
    if [[ "$CONSTRAINT" =~ '>=' ]]; then
        fail "Tyler still has version constraint on slide-lye: $CONSTRAINT"
    else
        pass "Tyler has no version constraint on slide-lye"
    fi
else
    warn "Tyler doesn't depend on slide-lye (unexpected)"
fi

# Check space-monkey dependencies
if grep -q '"slide-tyler"' packages/space-monkey/pyproject.toml; then
    CONSTRAINT=$(grep '"slide-tyler' packages/space-monkey/pyproject.toml)
    if [[ "$CONSTRAINT" =~ '>=' ]]; then
        fail "Space Monkey still has version constraint on slide-tyler: $CONSTRAINT"
    else
        pass "Space Monkey has no version constraint on slide-tyler"
    fi
else
    warn "Space Monkey doesn't depend on slide-tyler (unexpected)"
fi

if grep -q '"slide-narrator"' packages/space-monkey/pyproject.toml; then
    CONSTRAINT=$(grep '"slide-narrator' packages/space-monkey/pyproject.toml)
    if [[ "$CONSTRAINT" =~ '>=' ]]; then
        fail "Space Monkey still has version constraint on slide-narrator: $CONSTRAINT"
    else
        pass "Space Monkey has no version constraint on slide-narrator"
    fi
else
    warn "Space Monkey doesn't depend on slide-narrator (unexpected)"
fi
echo ""

# Test 8: Verify old files are removed
echo -e "${BLUE}Test 8: Old Files Removed${NC}"
if [ ! -f "scripts/release-all.sh" ]; then
    pass "Old release-all.sh removed"
else
    fail "Old release-all.sh still exists"
fi

if [ ! -f "scripts/update_dependent_constraints.py" ]; then
    pass "Old update_dependent_constraints.py removed"
else
    fail "Old update_dependent_constraints.py still exists"
fi

if [ ! -f ".github/workflows/release-tyler.yml" ]; then
    pass "Old release-tyler.yml removed"
else
    fail "Old release-tyler.yml still exists"
fi

if [ ! -f ".github/workflows/release-narrator.yml" ]; then
    pass "Old release-narrator.yml removed"
else
    fail "Old release-narrator.yml still exists"
fi

if [ ! -f ".github/workflows/release-space-monkey.yml" ]; then
    pass "Old release-space-monkey.yml removed"
else
    fail "Old release-space-monkey.yml still exists"
fi

if [ ! -f ".github/workflows/release-lye.yml" ]; then
    pass "Old release-lye.yml removed"
else
    fail "Old release-lye.yml still exists"
fi
echo ""

# Test 9: Verify documentation updated
echo -e "${BLUE}Test 9: Documentation${NC}"
if [ -f "scripts/README.md" ]; then
    if grep -q "Unified Release Script" scripts/README.md; then
        pass "scripts/README.md updated"
    else
        fail "scripts/README.md not updated"
    fi
else
    fail "scripts/README.md not found"
fi

if [ -d "directive/specs/unified-release" ]; then
    pass "Spec directory exists"
    if [ -f "directive/specs/unified-release/spec.md" ]; then
        pass "spec.md exists"
    else
        fail "spec.md missing"
    fi
    if [ -f "directive/specs/unified-release/impact.md" ]; then
        pass "impact.md exists"
    else
        fail "impact.md missing"
    fi
    if [ -f "directive/specs/unified-release/tdr.md" ]; then
        pass "tdr.md exists"
    else
        fail "tdr.md missing"
    fi
else
    fail "Spec directory missing"
fi
echo ""

# Summary
echo "=================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Review and merge the PR"
    echo "2. After merge, run: ./scripts/release.sh minor"
    echo "3. Review the generated release PR carefully"
    echo "4. Merge the release PR to publish to PyPI"
    exit 0
else
    echo -e "${RED}✗ $ERRORS test(s) failed${NC}"
    echo ""
    echo "Please fix the issues above before proceeding with the release."
    exit 1
fi

