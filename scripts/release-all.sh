#!/bin/bash
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Release All Packages Script${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if version type is provided
VERSION_TYPE=${1:-patch}

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo -e "${RED}Error: Version type must be one of: major, minor, patch${NC}"
    echo "Usage: $0 [version_type]"
    echo "  version_type: major, minor, patch (default: patch)"
    exit 1
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}GitHub CLI (gh) is not installed. Please install it first:${NC}"
    echo "  brew install gh    # on macOS"
    echo "  gh auth login      # to authenticate"
    exit 1
fi

# List of packages to release
PACKAGES=("tyler" "narrator" "space-monkey" "lye")

# Ensure we're on main branch
echo -e "${YELLOW}Switching to main branch and pulling latest changes...${NC}"
git checkout main
git pull origin main

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}Error: You have uncommitted changes. Please commit or stash them first.${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Package versions to be released:${NC}"
echo -e "${BLUE}--------------------------------${NC}"

# Display current and new versions for each package
for PACKAGE in "${PACKAGES[@]}"; do
    cd "packages/$PACKAGE"
    CURRENT_VERSION=$(grep 'version = "' pyproject.toml | sed 's/.*version = "\([^"]*\)".*/\1/')
    NEW_VERSION=$(python ../../scripts/bump_version.py "$PACKAGE" "$VERSION_TYPE" --dry-run --quiet)
    echo -e "${GREEN}$PACKAGE:${NC} $CURRENT_VERSION → $NEW_VERSION"
    cd ../..
done

echo ""
echo -e "${YELLOW}This will create release PRs for all packages with $VERSION_TYPE version bumps.${NC}"
echo -e "${YELLOW}Continue? (y/N)${NC}"
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo -e "${RED}Release cancelled.${NC}"
    exit 0
fi

# Track created PRs
declare -a PR_URLS

echo ""
echo -e "${BLUE}Creating release PRs...${NC}"
echo -e "${BLUE}=======================${NC}"

# Create release for each package
for PACKAGE in "${PACKAGES[@]}"; do
    echo ""
    echo -e "${GREEN}📦 Releasing $PACKAGE...${NC}"
    
    # Run the individual release script
    ./scripts/release.sh "$PACKAGE" "$VERSION_TYPE"
    
    # Extract the PR URL from the output (assumes it's printed by release.sh)
    # This is a bit fragile but works with the current release.sh output
    PR_URL=$(gh pr list --head "release/$PACKAGE-v*" --json url --jq '.[0].url' 2>/dev/null || echo "")
    
    if [ -n "$PR_URL" ]; then
        PR_URLS+=("$PACKAGE: $PR_URL")
    fi
    
    # Return to main branch for next package
    git checkout main
done

echo ""
echo -e "${GREEN}✨ All release PRs created successfully! ✨${NC}"
echo ""
echo -e "${BLUE}Summary of created PRs:${NC}"
echo -e "${BLUE}=======================${NC}"

for PR in "${PR_URLS[@]}"; do
    echo -e "${GREEN}$PR${NC}"
done

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review each PR to ensure the version bumps are correct"
echo "2. Merge the PRs when ready"
echo "3. GitHub Actions will automatically:"
echo "   - Create git tags for each package"
echo "   - Build and publish to PyPI"
echo "   - Create GitHub releases"
echo ""
echo -e "${GREEN}Happy releasing! 🎉${NC}"