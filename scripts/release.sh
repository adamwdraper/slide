#!/bin/bash
set -e

# Unified Release Script for Slide Monorepo
# Usage: ./scripts/release.sh [version_type]
# Version types: major, minor, patch (default: patch)

VERSION_TYPE=${1:-patch}
PACKAGES=("tyler" "narrator" "space-monkey" "lye")

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Unified Release Script${NC}"
echo -e "${BLUE}=========================${NC}"
echo ""

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Error: Version type must be one of: major, minor, patch"
    echo "Usage: $0 [version_type]"
    exit 1
fi

# Check for required tools
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) required. Install: brew install gh"
    exit 1
fi

if ! command -v git-cliff &> /dev/null; then
    echo "Error: git-cliff required. Install: brew install git-cliff"
    exit 1
fi

# Ensure on main branch
echo -e "${YELLOW}Ensuring on main branch...${NC}"
git checkout main
git pull origin main

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: Uncommitted changes detected. Commit or stash them first."
    exit 1
fi

# Determine new version (use tyler as reference package)
cd packages/tyler
CURRENT_VERSION=$(grep 'version = "' pyproject.toml | sed 's/.*version = "\([^"]*\)".*/\1/')
cd ../..

echo -e "${BLUE}Current version: ${CURRENT_VERSION}${NC}"

# Parse current version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version
case "$VERSION_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

echo -e "${GREEN}New version: ${NEW_VERSION}${NC}"
echo ""
echo -e "${YELLOW}This will:${NC}"
echo "  - Bump all 4 packages to v$NEW_VERSION"
echo "  - Remove inter-package version constraints"
echo "  - Generate CHANGELOGs automatically"
echo "  - Create release branch: release/v$NEW_VERSION"
echo "  - Create PR for review"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Create release branch
BRANCH_NAME="release/v$NEW_VERSION"
echo -e "${BLUE}Creating branch: ${BRANCH_NAME}${NC}"
git checkout -b "$BRANCH_NAME"

# Update all packages
echo ""
echo -e "${BLUE}Updating package versions...${NC}"
for PACKAGE in "${PACKAGES[@]}"; do
    echo -e "  ${GREEN}✓${NC} Updating $PACKAGE to $NEW_VERSION..."
    
    PACKAGE_DIR="packages/$PACKAGE"
    MODULE_NAME=${PACKAGE//-/_}
    
    # Update pyproject.toml
    sed -i.bak "s/version = \".*\"/version = \"$NEW_VERSION\"/" "$PACKAGE_DIR/pyproject.toml"
    rm "$PACKAGE_DIR/pyproject.toml.bak"
    
    # Update __init__.py
    sed -i.bak "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" "$PACKAGE_DIR/$MODULE_NAME/__init__.py"
    rm "$PACKAGE_DIR/$MODULE_NAME/__init__.py.bak"
done

# Set inter-package minimum version constraints
echo ""
echo -e "${BLUE}Setting inter-package minimum version constraints...${NC}"

# Tyler: Set narrator and lye to >=NEW_VERSION
sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" packages/tyler/pyproject.toml
echo -e "  ${GREEN}✓${NC} Tyler: slide-narrator>=$NEW_VERSION"

sed -i.bak "s/\"slide-lye[^\"]*\"/\"slide-lye>=$NEW_VERSION\"/g" packages/tyler/pyproject.toml
echo -e "  ${GREEN}✓${NC} Tyler: slide-lye>=$NEW_VERSION"

# Space Monkey: Set tyler and narrator to >=NEW_VERSION
sed -i.bak "s/\"slide-tyler[^\"]*\"/\"slide-tyler>=$NEW_VERSION\"/g" packages/space-monkey/pyproject.toml
echo -e "  ${GREEN}✓${NC} Space Monkey: slide-tyler>=$NEW_VERSION"

sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" packages/space-monkey/pyproject.toml
echo -e "  ${GREEN}✓${NC} Space Monkey: slide-narrator>=$NEW_VERSION"

# Clean up backup files
rm -f packages/tyler/pyproject.toml.bak
rm -f packages/space-monkey/pyproject.toml.bak

# Generate CHANGELOGs
echo ""
echo -e "${BLUE}Generating CHANGELOGs...${NC}"

for PACKAGE in "${PACKAGES[@]}"; do
    echo -e "  Generating CHANGELOG for $PACKAGE..."
    if git cliff --include-path "packages/$PACKAGE/**" \
        --tag "$PACKAGE-v$NEW_VERSION" \
        --output "packages/$PACKAGE/CHANGELOG.md" 2>&1; then
        echo -e "  ${GREEN}✓${NC} $PACKAGE CHANGELOG generated"
    else
        echo -e "  ${YELLOW}⚠${NC} Warning: Failed to generate CHANGELOG for $PACKAGE"
        echo -e "  ${YELLOW}  Creating empty CHANGELOG - please update manually${NC}"
        echo "# Changelog" > "packages/$PACKAGE/CHANGELOG.md"
        echo "" >> "packages/$PACKAGE/CHANGELOG.md"
        echo "## [$NEW_VERSION] - $(date +%Y-%m-%d)" >> "packages/$PACKAGE/CHANGELOG.md"
        echo "" >> "packages/$PACKAGE/CHANGELOG.md"
        echo "Please add changelog entries manually." >> "packages/$PACKAGE/CHANGELOG.md"
    fi
done

# Stage all changes
git add packages/*/pyproject.toml packages/*/__init__.py packages/*/*/__init__.py packages/*/CHANGELOG.md

# Commit
echo ""
echo -e "${BLUE}Creating commit...${NC}"
git commit -m "Release v$NEW_VERSION

- Bump all packages to $NEW_VERSION
- Remove inter-package version constraints
- Generate CHANGELOGs
- Synchronized release across all packages"

# Push branch
echo -e "${BLUE}Pushing branch to origin...${NC}"
git push origin "$BRANCH_NAME"

# Create PR
echo ""
echo -e "${BLUE}Creating Pull Request...${NC}"
PR_URL=$(gh pr create \
    --title "Release v$NEW_VERSION" \
    --body "## Unified Release v$NEW_VERSION

This PR implements a unified release for all Slide packages.

### Packages Updated
- **slide-tyler**: $CURRENT_VERSION → $NEW_VERSION
- **slide-narrator**: $CURRENT_VERSION → $NEW_VERSION  
- **slide-space-monkey**: $CURRENT_VERSION → $NEW_VERSION
- **slide-lye**: $CURRENT_VERSION → $NEW_VERSION

### Changes
- ✅ All packages synchronized to version $NEW_VERSION
- ✅ Removed inter-package version constraints
- ✅ Auto-generated CHANGELOGs from conventional commits
- ✅ All packages with this version are guaranteed compatible

### What Happens After Merge
The unified release workflow will automatically:
1. Create git tags for all packages (\`tyler-v$NEW_VERSION\`, \`narrator-v$NEW_VERSION\`, etc.)
2. Build all packages
3. Publish all packages to PyPI
4. Create individual GitHub releases for each package

### Testing
\`\`\`bash
# Verify all versions match
grep version packages/*/pyproject.toml

# Verify CHANGELOGs created
ls packages/*/CHANGELOG.md
\`\`\`

---
**Note**: This is the first unified release. All future releases will use this process." \
    --label "release" \
    --base main \
    --head "$BRANCH_NAME")

echo ""
echo -e "${GREEN}✨ Release PR Created! ✨${NC}"
echo ""
echo -e "${BLUE}PR URL:${NC} $PR_URL"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review the PR and verify all changes"
echo "  2. Merge the PR when ready"
echo "  3. The unified release workflow will automatically:"
echo "     - Create tags: tyler-v$NEW_VERSION, narrator-v$NEW_VERSION, space-monkey-v$NEW_VERSION, lye-v$NEW_VERSION"
echo "     - Build and publish all packages to PyPI"
echo "     - Create 4 individual GitHub releases"
echo ""
