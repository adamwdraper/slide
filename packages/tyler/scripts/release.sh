#!/bin/bash
set -e

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed. Please install it first:"
    echo "  brew install gh    # on macOS"
    echo "  gh auth login      # to authenticate"
    exit 1
fi

# Check if version type is provided
VERSION_TYPE=${1:-patch}
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Version type must be one of: major, minor, patch"
    exit 1
fi

# Ensure we're starting from an up-to-date main
git checkout main
git pull origin main

# Get the new version number without making changes yet
NEW_VERSION=$(python scripts/bump_version.py "$VERSION_TYPE" --dry-run)
if [ $? -ne 0 ]; then
    echo "Failed to determine new version number"
    exit 1
fi

# Create and checkout a release branch
BRANCH_NAME="release/v$NEW_VERSION"
git checkout -b "$BRANCH_NAME"

# Now actually bump the version
NEW_VERSION=$(python scripts/bump_version.py "$VERSION_TYPE")

# Create git commit
git add pyproject.toml tyler/__init__.py
git commit -m "Bump version to $NEW_VERSION"

# Push the release branch
git push origin "$BRANCH_NAME"

# Create PR and add release label
PR_URL=$(gh pr create \
    --title "Release v$NEW_VERSION" \
    --body "Automated release PR for version $NEW_VERSION" \
    --label "release" \
    --base main \
    --head "$BRANCH_NAME")

echo "✨ Release PR prepared! ✨"
echo ""
echo "Pull Request created at: $PR_URL"
echo ""
echo "The GitHub Actions workflow will automatically:"
echo "- Create the git tag"
echo "- Build the package"
echo "- Publish to PyPI"
echo ""
echo "Please review and merge the PR when ready." 