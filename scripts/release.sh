#!/bin/bash
set -e

# Check if package name is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <package> [version_type]"
    echo "Available packages: tyler, narrator, space-monkey, lye"
    echo "Version types: major, minor, patch (default: patch)"
    exit 1
fi

PACKAGE=$1
VERSION_TYPE=${2:-patch}

# Validate package name
if [[ ! "$PACKAGE" =~ ^(tyler|narrator|space-monkey|lye)$ ]]; then
    echo "Package must be one of: tyler, narrator, space-monkey, lye"
    exit 1
fi

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Version type must be one of: major, minor, patch"
    exit 1
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed. Please install it first:"
    echo "  brew install gh    # on macOS"
    echo "  gh auth login      # to authenticate"
    exit 1
fi

# Change to package directory
PACKAGE_DIR="packages/$PACKAGE"
if [ ! -d "$PACKAGE_DIR" ]; then
    echo "Package directory $PACKAGE_DIR does not exist"
    exit 1
fi

cd "$PACKAGE_DIR"

# Ensure we're starting from an up-to-date main
git checkout main
git pull origin main

# Get the new version number without making changes yet
NEW_VERSION=$(python ../../scripts/bump_version.py "$PACKAGE" "$VERSION_TYPE" --dry-run --quiet)
if [ $? -ne 0 ]; then
    echo "Failed to determine new version number"
    exit 1
fi

# Create and checkout a release branch
BRANCH_NAME="release/$PACKAGE-v$NEW_VERSION"
git checkout -b "$BRANCH_NAME"

# Now actually bump the version
python ../../scripts/bump_version.py "$PACKAGE" "$VERSION_TYPE"

# Convert package name to module name (replace hyphens with underscores)
MODULE_NAME=${PACKAGE//-/_}

# Create git commit
git add pyproject.toml ${MODULE_NAME}/__init__.py
git commit -m "Bump $PACKAGE version to $NEW_VERSION"

# Push the release branch
git push origin "$BRANCH_NAME"

# Create PR and add release label
PR_URL=$(gh pr create \
    --title "Release $PACKAGE v$NEW_VERSION" \
    --body "Automated release PR for $PACKAGE version $NEW_VERSION" \
    --label "release" \
    --base main \
    --head "$BRANCH_NAME")

echo "✨ Release PR prepared for $PACKAGE! ✨"
echo ""
echo "Pull Request created at: $PR_URL"
echo ""
echo "The GitHub Actions workflow will automatically:"
echo "- Create the git tag"
echo "- Build the package"
echo "- Publish to PyPI"
echo ""
echo "Please review and merge the PR when ready." 