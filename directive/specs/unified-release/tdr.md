# Technical Design Review (TDR) — Unified Monorepo Release Process

**Author**: AI Agent  
**Date**: 2025-10-13  
**Links**: 
- Spec: `/directive/specs/unified-release/spec.md`
- Impact: `/directive/specs/unified-release/impact.md`

---

## 1. Summary

We are transitioning from independent per-package releases to a unified monorepo release process. This involves:

1. **Version synchronization**: All 4 packages (tyler, narrator, space-monkey, lye) will share the same version number (starting at v2.2.0)
2. **Unified release script**: Single script that bumps all packages together and creates one release branch/PR
3. **Automated changelog generation**: Using git-cliff to generate CHANGELOGs from conventional commits
4. **Consolidated GitHub Actions workflow**: Single workflow that builds and publishes all packages to PyPI
5. **Simplified dependencies**: Remove version constraints between inter-package dependencies

**Why**: The current process of releasing 4 packages independently creates complexity with multiple release branches, sequential dependency releases, and version drift. This unified approach reduces release time by ~75%, eliminates dependency constraint conflicts, and provides clear version compatibility guarantees.

**Prerequisites**: GitHub CLI (`gh`) and git-cliff installed (`brew install gh git-cliff`)

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Developer productivity**: Reduce release overhead from 4 PRs to 1 PR
- **Dependency management**: Eliminate version constraint updates between packages
- **Clear compatibility**: Same version = guaranteed compatible
- **Reduced cognitive load**: No need to track "which version X works with version Y"
- **Faster iterations**: Ship features across packages atomically

### Non-Goals
- Creating a meta-package that installs all Slide packages together
- Supporting selective package releases (all packages always released together)
- Changing PyPI package names or structure
- Implementing canary/beta release channels

## 3. Current State — Codebase Map

### Current Release Scripts

**`/scripts/release.sh`** (101 lines)
- Takes package name and version type as arguments
- Creates branch: `release/{package}-v{version}`
- Bumps single package version
- Updates dependent package constraints
- Creates single-package PR

**`/scripts/release-all.sh`** (117 lines)
- Loops through all 4 packages
- Calls `release.sh` for each package
- Creates 4 separate branches and PRs
- Still results in 4 separate releases

**`/scripts/bump_version.py`** (121 lines)
- Bumps version in `pyproject.toml` and `__init__.py`
- Supports `major`, `minor`, `patch` bumps
- Works on one package at a time
- Has `--dry-run` and `--quiet` flags

**`/scripts/update_dependent_constraints.py`** (124 lines)
- Updates version constraints when dependencies are released
- Hardcoded dependency graph:
  ```python
  DEPENDENCIES = {
      'narrator': ['tyler', 'space-monkey'],
      'lye': ['tyler'],
      'tyler': ['space-monkey'],
      'space-monkey': [],
  }
  ```

### Current GitHub Actions Workflows

Four separate workflow files:
- `.github/workflows/release-tyler.yml`
- `.github/workflows/release-narrator.yml`
- `.github/workflows/release-space-monkey.yml`
- `.github/workflows/release-lye.yml`

**Structure** (same for all):
1. Trigger: PR merged to main with branch pattern `release/{package}-v*`
2. Extract version from branch name
3. Verify version matches `pyproject.toml`
4. Create git tag: `{package}-v{version}`
5. Build package with hatch
6. Publish to PyPI
7. Create GitHub release

### Current Package Dependencies

**Tyler** depends on:
```toml
dependencies = [
    "slide-narrator>=1.0.2",
    "slide-lye>=1.0.1",
]
```

**Space Monkey** depends on:
```toml
dependencies = [
    "slide-tyler>=2.1.0",
    "slide-narrator>=1.0.2",
]
```

### Current Versions
- tyler: 2.1.0 (highest)
- narrator: 1.0.2
- space-monkey: 1.0.0
- lye: 1.0.1

### Workspace Configuration
**`/pyproject.toml`** (root):
```toml
[tool.uv.workspace]
members = [
    "packages/narrator",
    "packages/tyler",
    "packages/space-monkey",
    "packages/lye",
]

[tool.uv.sources]
slide-narrator = { workspace = true }
slide-tyler = { workspace = true }
slide-space-monkey = { workspace = true }
slide-lye = { workspace = true }
```

## 4. Proposed Design

### 4.1 Version Synchronization Strategy

**Approach**: All packages share the same version number at all times

**Starting Version**: 2.2.0
- Tyler currently at 2.1.0 → bump to 2.2.0 (normal minor bump)
- Other packages jump to 2.2.0 (synchronization, not breaking changes)

**Version Bump Semantics**:
- `major`: 2.2.0 → 3.0.0 (breaking changes in any package)
- `minor`: 2.2.0 → 2.3.0 (new features in any package)
- `patch`: 2.2.0 → 2.2.1 (bug fixes in any package)

**Implication**: Even if only one package changes, all packages get bumped

### 4.2 Unified Release Script Design

**New `/scripts/release.sh`** - Complete rewrite

```bash
#!/bin/bash
set -e

# Usage: ./scripts/release.sh [version_type]
# Version types: major, minor, patch (default: patch)

VERSION_TYPE=${1:-patch}
PACKAGES=("tyler" "narrator" "space-monkey" "lye")

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Version type must be one of: major, minor, patch"
    exit 1
fi

# Check for required tools
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) required. Install: brew install gh"
    exit 1
fi

if ! command -v git-cliff &> /dev/null; then
    echo "git-cliff required. Install: brew install git-cliff"
    exit 1
fi

# Ensure on main branch
git checkout main
git pull origin main

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: Uncommitted changes. Commit or stash them first."
    exit 1
fi

# Determine new version (use tyler as reference package)
cd packages/tyler
CURRENT_VERSION=$(grep 'version = "' pyproject.toml | sed 's/.*version = "\([^"]*\)".*/\1/')
cd ../..

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

echo "Releasing all packages from $CURRENT_VERSION to $NEW_VERSION"
echo ""

# Create release branch
BRANCH_NAME="release/v$NEW_VERSION"
git checkout -b "$BRANCH_NAME"

# Update all packages
for PACKAGE in "${PACKAGES[@]}"; do
    echo "Updating $PACKAGE to $NEW_VERSION..."
    
    PACKAGE_DIR="packages/$PACKAGE"
    MODULE_NAME=${PACKAGE//-/_}
    
    # Update pyproject.toml
    sed -i.bak "s/version = \".*\"/version = \"$NEW_VERSION\"/" "$PACKAGE_DIR/pyproject.toml"
    rm "$PACKAGE_DIR/pyproject.toml.bak"
    
    # Update __init__.py
    sed -i.bak "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" "$PACKAGE_DIR/$MODULE_NAME/__init__.py"
    rm "$PACKAGE_DIR/$MODULE_NAME/__init__.py.bak"
done

# Remove version constraints from inter-package dependencies
echo ""
echo "Removing inter-package version constraints..."

# Tyler: slide-narrator>=X.Y.Z -> slide-narrator
sed -i.bak 's/"slide-narrator>=.*"/"slide-narrator"/g' packages/tyler/pyproject.toml
sed -i.bak 's/"slide-lye>=.*"/"slide-lye"/g' packages/tyler/pyproject.toml
rm packages/tyler/pyproject.toml.bak

# Space Monkey: slide-tyler>=X.Y.Z -> slide-tyler
sed -i.bak 's/"slide-tyler>=.*"/"slide-tyler"/g' packages/space-monkey/pyproject.toml
sed -i.bak 's/"slide-narrator>=.*"/"slide-narrator"/g' packages/space-monkey/pyproject.toml
rm packages/space-monkey/pyproject.toml.bak

# Generate CHANGELOGs
echo ""
echo "Generating CHANGELOGs..."

for PACKAGE in "${PACKAGES[@]}"; do
    echo "  Generating CHANGELOG for $PACKAGE..."
    git cliff --include-path "packages/$PACKAGE/**" \
        --tag "$PACKAGE-v$NEW_VERSION" \
        --output "packages/$PACKAGE/CHANGELOG.md"
done

# Stage all changes
git add packages/*/pyproject.toml packages/*/__init__.py packages/*/*/__init__.py packages/*/CHANGELOG.md

# Commit
git commit -m "Release v$NEW_VERSION

- Bump all packages to $NEW_VERSION
- Remove inter-package version constraints
- Synchronized release"

# Push branch
git push origin "$BRANCH_NAME"

# Create PR
PR_URL=$(gh pr create \
    --title "Release v$NEW_VERSION" \
    --body "Unified release of all Slide packages to version $NEW_VERSION

## Packages Updated
- slide-tyler: $CURRENT_VERSION → $NEW_VERSION
- slide-narrator: $CURRENT_VERSION → $NEW_VERSION
- slide-space-monkey: $CURRENT_VERSION → $NEW_VERSION
- slide-lye: $CURRENT_VERSION → $NEW_VERSION

## Changes
- All packages synchronized to version $NEW_VERSION
- Removed inter-package version constraints
- All packages with this version are guaranteed compatible

## Post-Merge
The unified release workflow will automatically:
- Create git tags for all packages
- Build and publish all packages to PyPI
- Create individual GitHub releases" \
    --label "release" \
    --base main \
    --head "$BRANCH_NAME")

echo ""
echo "✨ Release PR created! ✨"
echo ""
echo "PR URL: $PR_URL"
echo ""
echo "After merge, the workflow will:"
echo "  - Create tags: tyler-v$NEW_VERSION, narrator-v$NEW_VERSION, space-monkey-v$NEW_VERSION, lye-v$NEW_VERSION"
echo "  - Build and publish all packages to PyPI"
echo "  - Create 4 individual GitHub releases"
```

**Key Changes from Current**:
- No package name argument (always releases all)
- Creates single branch: `release/v{version}`
- Updates all 4 packages in one commit
- Removes version constraints as part of the process
- Single PR instead of 4

### 4.3 Unified GitHub Actions Workflow

**New `.github/workflows/release.yml`**

```yaml
name: Unified Release

on:
  pull_request:
    types: [closed]
    branches: [ main ]

permissions:
  contents: write
  pull-requests: write

jobs:
  publish-all:
    # Only run if PR was merged and branch matches release/v*
    if: github.event.pull_request.merged == true && startsWith(github.event.pull_request.head.ref, 'release/v')
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Validate release branch
        run: |
          if [[ ! "${{ github.event.pull_request.head.ref }}" =~ ^release/v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "ERROR: Branch must match pattern release/vX.Y.Z"
            echo "Branch: ${{ github.event.pull_request.head.ref }}"
            exit 1
          fi
          echo "✓ Valid release branch"
      
      - name: Extract version from branch
        id: version
        run: |
          BRANCH_NAME="${{ github.event.pull_request.head.ref }}"
          VERSION=${BRANCH_NAME#release/v}
          echo "VERSION=$VERSION" >> $GITHUB_OUTPUT
          echo "Extracted version: $VERSION"
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      
      - name: Install hatch
        run: uv tool install hatch
      
      - name: Verify versions in all packages
        run: |
          VERSION="${{ steps.version.outputs.VERSION }}"
          echo "Verifying all packages are at version $VERSION..."
          
          for PACKAGE in tyler narrator space-monkey lye; do
            PACKAGE_DIR="packages/$PACKAGE"
            PYPROJECT_VERSION=$(grep -Po '(?<=version = ")[^"]*' $PACKAGE_DIR/pyproject.toml)
            
            echo "  $PACKAGE: $PYPROJECT_VERSION"
            
            if [ "$PYPROJECT_VERSION" != "$VERSION" ]; then
              echo "ERROR: Version mismatch in $PACKAGE!"
              echo "  Expected: $VERSION"
              echo "  Found: $PYPROJECT_VERSION"
              exit 1
            fi
          done
          
          echo "✓ All packages at version $VERSION"
      
      - name: Create git tags
        run: |
          VERSION="${{ steps.version.outputs.VERSION }}"
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          
          for PACKAGE in tyler narrator space-monkey lye; do
            TAG="$PACKAGE-v$VERSION"
            echo "Creating tag: $TAG"
            git tag -a "$TAG" -m "Release $PACKAGE version $VERSION"
            git push origin "$TAG"
          done
          
          echo "✓ All tags created and pushed"
      
      - name: Build all packages
        run: |
          for PACKAGE in tyler narrator space-monkey lye; do
            echo "::group::Building $PACKAGE"
            cd "packages/$PACKAGE"
            uv tool run hatch build
            cd ../..
            echo "::endgroup::"
            echo "::notice::$PACKAGE built successfully"
          done
      
      - name: Publish all packages to PyPI
        env:
          HATCH_INDEX_USER: __token__
          HATCH_INDEX_AUTH: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          for PACKAGE in tyler narrator space-monkey lye; do
            echo "::group::Publishing $PACKAGE"
            cd "packages/$PACKAGE"
            uv tool run hatch publish
            cd ../..
            echo "::endgroup::"
            echo "::notice::$PACKAGE published successfully to PyPI"
          done
      
      - name: Create GitHub releases
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          VERSION="${{ steps.version.outputs.VERSION }}"
          
          # Tyler release
          gh release create "tyler-v$VERSION" \
            --title "Tyler v$VERSION" \
            --notes "Release Tyler v$VERSION

**Package**: slide-tyler  
**Version**: $VERSION

This is part of the unified Slide release v$VERSION. All Slide packages at version $VERSION are guaranteed compatible.

See [CHANGELOG](https://github.com/${{ github.repository }}/blob/main/packages/tyler/CHANGELOG.md) for details." \
            packages/tyler/dist/*
          
          # Narrator release
          gh release create "narrator-v$VERSION" \
            --title "Narrator v$VERSION" \
            --notes "Release Narrator v$VERSION

**Package**: slide-narrator  
**Version**: $VERSION

This is part of the unified Slide release v$VERSION. All Slide packages at version $VERSION are guaranteed compatible.

See [CHANGELOG](https://github.com/${{ github.repository }}/blob/main/packages/narrator/CHANGELOG.md) for details." \
            packages/narrator/dist/*
          
          # Space Monkey release
          gh release create "space-monkey-v$VERSION" \
            --title "Space Monkey v$VERSION" \
            --notes "Release Space Monkey v$VERSION

**Package**: slide-space-monkey  
**Version**: $VERSION

This is part of the unified Slide release v$VERSION. All Slide packages at version $VERSION are guaranteed compatible.

See [CHANGELOG](https://github.com/${{ github.repository }}/blob/main/packages/space-monkey/CHANGELOG.md) for details." \
            packages/space-monkey/dist/*
          
          # Lye release
          gh release create "lye-v$VERSION" \
            --title "Lye v$VERSION" \
            --notes "Release Lye v$VERSION

**Package**: slide-lye  
**Version**: $VERSION

This is part of the unified Slide release v$VERSION. All Slide packages at version $VERSION are guaranteed compatible.

See [CHANGELOG](https://github.com/${{ github.repository }}/blob/main/packages/lye/CHANGELOG.md) for details." \
            packages/lye/dist/*
          
          echo "✓ All GitHub releases created"
```

**Key Features**:
- Single workflow (replaces 4)
- Pattern matching: `release/v*` instead of `release/{package}-v*`
- Creates 4 tags in one workflow
- Builds all packages sequentially (could parallelize with matrix)
- Publishes all packages sequentially
- Creates 4 separate GitHub releases with individual notes
- Uses `::group::` for better log organization
- Uses `::notice::` for milestone visibility

### 4.4 Inter-Package Dependency Changes

**Before** (with constraints):
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator>=1.0.2",
    "slide-lye>=1.0.1",
]

# packages/space-monkey/pyproject.toml
dependencies = [
    "slide-tyler>=2.1.0",
    "slide-narrator>=1.0.2",
]
```

**After** (no constraints):
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator",
    "slide-lye",
]

# packages/space-monkey/pyproject.toml
dependencies = [
    "slide-tyler",
    "slide-narrator",
]
```

**Development** (workspace references remain unchanged):
```toml
# Root pyproject.toml - unchanged
[tool.uv.sources]
slide-narrator = { workspace = true }
slide-tyler = { workspace = true }
slide-space-monkey = { workspace = true }
slide-lye = { workspace = true }
```

**Rationale**:
- Synchronized versions guarantee compatibility
- Package managers will install latest available versions
- Simpler dependency resolution
- No more constraint update scripts needed

### 4.5 CHANGELOG Management

**Automated Generation Using git-cliff**

We'll use [git-cliff](https://git-cliff.org/) to automatically generate CHANGELOGs from conventional commit messages.

**Why git-cliff:**
- Fast (Rust-based)
- Monorepo support (filter by path patterns)
- Parses conventional commits (feat:, fix:, chore:, docs:, etc.)
- Zero config to start, customizable if needed

**Installation:**
```bash
brew install git-cliff
# or: cargo install git-cliff
# or: cargo binstall git-cliff
```

**Integration in Release Script:**

For each package, generate changelog scoped to that package's directory:

```bash
# Tyler changelog
git cliff --include-path "packages/tyler/**" \
  --tag "tyler-v$NEW_VERSION" \
  --output packages/tyler/CHANGELOG.md

# Narrator changelog  
git cliff --include-path "packages/narrator/**" \
  --tag "narrator-v$NEW_VERSION" \
  --output packages/narrator/CHANGELOG.md

# Space Monkey changelog
git cliff --include-path "packages/space-monkey/**" \
  --tag "space-monkey-v$NEW_VERSION" \
  --output packages/space-monkey/CHANGELOG.md

# Lye changelog
git cliff --include-path "packages/lye/**" \
  --tag "lye-v$NEW_VERSION" \
  --output packages/lye/CHANGELOG.md
```

**Generated Format** (from conventional commits):
```markdown
# Changelog

## [2.2.0] - 2025-10-13

### Features
- add new streaming mode support

### Bug Fixes  
- handle authentication errors gracefully
- restore weave.op decorator

### Documentation
- update streaming guide with raw mode

### Refactor
- extract completion handler to separate module

## [2.1.0] - 2025-10-01
...
```

**First Release (v2.2.0) Special Handling:**

Since there are no existing CHANGELOGs, we'll need to:
1. Generate from git history
2. Add special note about unified versioning at the top
3. Manually prepend the version sync message

**Post-Generation Manual Edit** (optional):
- After git-cliff generates the changelog, can manually edit for clarity
- Add migration notes or special announcements
- Combine as needed for user-friendliness

**Location**:
- `/packages/tyler/CHANGELOG.md`
- `/packages/narrator/CHANGELOG.md`
- `/packages/space-monkey/CHANGELOG.md`
- `/packages/lye/CHANGELOG.md`

**Maintenance**:
- Automatic generation during release process
- Scoped to package-specific changes
- Share version number but independent content

### 4.6 Error Handling & Recovery

#### Scenario A: Version Mismatch Detected
**Trigger**: Workflow detects packages have different versions

```bash
# Workflow fails with clear message:
ERROR: Version mismatch in narrator!
  Expected: 2.2.0
  Found: 2.1.0
```

**Recovery**: Fix versions locally, update PR, merge again

#### Scenario B: PyPI Publish Fails Mid-Release
**Trigger**: Tyler publishes but narrator fails

**Detection**: Workflow fails after partial success

**Recovery Options**:
1. **Retry workflow**: Re-run from GitHub Actions UI (PyPI handles duplicates)
2. **Manual publish**: Publish remaining packages manually
3. **Roll forward**: Release patch version with fix

**Mitigation**: Use `continue-on-error: false` (default) to fail fast

#### Scenario C: GitHub Release Creation Fails
**Trigger**: All packages published but release creation fails

**Impact**: Packages on PyPI but no GitHub releases

**Recovery**: Manually create releases via GitHub UI or gh CLI

### 4.7 Performance Characteristics

**Release Script Performance**:
- Version parsing: <1s
- Git operations: ~3-5s
- PR creation: ~2-3s
- **Total**: ~10s

**Workflow Performance**:
- Setup (checkout, Python, tools): ~30s
- Version verification: ~5s
- Tag creation: ~10s
- Build all packages: ~60-90s (sequential)
- Publish all packages: ~40-60s (sequential)
- Create releases: ~20-30s
- **Total**: ~3-5 minutes

**Comparison to Current**:
- Current: 4 workflows × 3-5 min = 12-20 min wall-clock (if sequential)
- New: 1 workflow × 3-5 min = 3-5 min
- **Improvement**: 60-75% faster

## 5. Alternatives Considered

### Alternative A: Keep Independent Releases, Just Sync Versions
Synchronize versions but maintain separate release scripts and workflows

**Pros**:
- Less drastic change
- Can still release packages independently if needed
- Smaller implementation effort

**Cons**:
- Still requires 4 PRs
- Still requires managing constraints
- Doesn't solve the core complexity problem
- Version sync can drift without automation

**Rejected**: Doesn't achieve the goal of simplifying the release process

### Alternative B: Parallel Package Publishing (Matrix Strategy)
Use GitHub Actions matrix to build/publish packages in parallel

```yaml
jobs:
  publish:
    strategy:
      matrix:
        package: [tyler, narrator, space-monkey, lye]
    steps:
      - name: Build ${{ matrix.package }}
        run: cd packages/${{ matrix.package }} && hatch build
```

**Pros**:
- Faster workflow execution (parallel builds)
- More concise YAML

**Cons**:
- Harder to handle dependencies between steps
- Less clear error messages (which package failed?)
- Can't easily share artifacts between matrix jobs
- Tag creation needs to be separate job

**Deferred**: Could optimize later, sequential is clearer for first implementation

### Alternative C: Meta-Package Approach
Create a `slide` meta-package that depends on all sub-packages

```toml
# packages/slide/pyproject.toml
dependencies = [
    "slide-tyler==2.2.0",
    "slide-narrator==2.2.0",
    "slide-space-monkey==2.2.0",
    "slide-lye==2.2.0",
]
```

**Pros**:
- Users can `pip install slide` to get everything
- Clear version guarantee

**Cons**:
- Additional package to maintain
- Users who want only one package still need individual packages
- Doesn't solve release complexity
- Adds another layer

**Rejected**: Out of scope, could add later if users request it

### Alternative D: Keep Current Process, Improve Documentation
Keep everything as-is, just document the process better

**Pros**:
- Zero implementation work
- No risk of breaking anything

**Cons**:
- Doesn't solve any problems
- Pain points remain
- Still complex for maintainers

**Rejected**: Doesn't address the core issues

### Alternative E: Semantic Release Automation
Use semantic-release or similar tool to fully automate releases

**Pros**:
- Automatic version bumping from commit messages
- Automatic changelog generation
- Automatic publishing
- Industry standard tool

**Cons**:
- Requires specific commit message format (already using conventional commits)
- Learning curve for team
- May not support monorepo patterns well
- More complex setup
- Less control over release timing

**Partial Adoption**: We're using git-cliff for automated changelog generation (same principle, simpler tool)

**Deferred for Full Automation**: Could revisit fully automated releases after unified process is stable

## 6. Data Model & Contract Changes

### PyPI Package Metadata

**Breaking Change Classification**: Minor/patch release (packaging change, not API change)

#### Version Dependencies Contract Change

**Before**:
```toml
# slide-tyler published on PyPI
dependencies = ["slide-narrator>=1.0.2", "slide-lye>=1.0.1"]
```

**After**:
```toml
# slide-tyler published on PyPI
dependencies = ["slide-narrator", "slide-lye"]
```

**Impact on Users**:
- Installing `slide-tyler` will pull latest `slide-narrator` and `slide-lye`
- No ability to pin to specific inter-package version combinations
- All packages at same version guaranteed compatible

**Backward Compatibility**:
- Old published versions still available on PyPI with constraints
- Users can still pin to older versions if needed
- New versions follow standard semantic versioning

### Git Tag Format

**No Breaking Change** - maintains existing convention:
```
tyler-v2.2.0
narrator-v2.2.0
space-monkey-v2.2.0
lye-v2.2.0
```

**Historical tags preserved**:
```
tyler-v2.1.0 (still exists)
tyler-v2.0.0 (still exists)
...
```

### Release Branch Convention

**Breaking Change**:
- **Old pattern**: `release/tyler-v2.1.0`
- **New pattern**: `release/v2.2.0`
- **Impact**: Old release workflows will not trigger (intentional)
- **Mitigation**: Complete all in-flight releases before deploying new process

## 7. Security, Privacy, Compliance

### Security Assessment

**Risk Level**: Low

#### PyPI Token Management
**Current**: Token stored in `PYPI_API_TOKEN` secret, used by 4 workflows  
**New**: Same token, used by 1 workflow  
**Impact**: No change in security posture

**Mitigation**:
- Use scoped PyPI token (only allows publishing to Slide packages)
- Enable GitHub environment protection (optional)
- Audit workflow file carefully for secret leakage

#### Supply Chain Security
**Concern**: Failed publish could create inconsistent state

**Scenario**: Tyler v2.2.0 published, Narrator v2.2.0 fails
**Impact**: Users installing latest get mismatched versions
**Likelihood**: Low (PyPI publish rarely fails)

**Mitigation**:
- Workflow fails fast on any publish error
- Document rollback procedure (yank version, release patch)
- Monitor workflow execution

#### Workflow Permissions
**Current**: `contents: write`, `pull-requests: write`  
**New**: Same permissions  
**Impact**: No change

**Justification**:
- `contents: write`: Required for creating tags
- `pull-requests: write`: Required for PR operations

### Privacy & Compliance
**Assessment**: No privacy or compliance impact
- No user data involved
- No PII handling
- No GDPR implications
- Public open-source packages

## 8. Observability & Operations

### Logging Strategy

#### Release Script Logs
**Output to**: Console (stdout/stderr)

**Log Levels**:
- Info: Version bumps, git operations
- Warning: Non-fatal issues
- Error: Fatal issues with clear instructions

**Example Output**:
```
Releasing all packages from 2.1.0 to 2.2.0

Updating tyler to 2.2.0...
Updating narrator to 2.2.0...
Updating space-monkey to 2.2.0...
Updating lye to 2.2.0...

Removing inter-package version constraints...

✨ Release PR created! ✨

PR URL: https://github.com/org/repo/pull/123

After merge, the workflow will:
  - Create tags: tyler-v2.2.0, narrator-v2.2.0, space-monkey-v2.2.0, lye-v2.2.0
  - Build and publish all packages to PyPI
  - Create 4 individual GitHub releases
```

#### Workflow Logs
**GitHub Actions provides**:
- Structured logs per step
- Expandable groups (`::group::`)
- Annotations (`::notice::`, `::warning::`, `::error::`)
- Timing information
- Exit codes

**Organization**:
```
✓ Validate release branch
✓ Extract version from branch
✓ Install tools
✓ Verify versions in all packages
  ├─ tyler: 2.2.0
  ├─ narrator: 2.2.0
  ├─ space-monkey: 2.2.0
  └─ lye: 2.2.0
✓ Create git tags
  ├─ tyler-v2.2.0
  ├─ narrator-v2.2.0
  ├─ space-monkey-v2.2.0
  └─ lye-v2.2.0
▼ Build all packages
  ├─ Building tyler ✓
  ├─ Building narrator ✓
  ├─ Building space-monkey ✓
  └─ Building lye ✓
▼ Publish all packages
  ├─ Publishing tyler ✓
  ├─ Publishing narrator ✓
  ├─ Publishing space-monkey ✓
  └─ Publishing lye ✓
✓ Create GitHub releases
```

### Metrics to Track

#### Release Metrics
| Metric | Source | Goal |
|--------|--------|------|
| Release success rate | GitHub Actions | >95% |
| Release duration | GitHub Actions | <5 min |
| Time from PR merge to PyPI | GitHub Actions | <5 min |
| Failed publishes | GitHub Actions | <5% |

#### Version Consistency Metrics
| Metric | Source | Goal |
|--------|--------|------|
| Version drift detected | CI check (new) | 0 |
| Manual fixes needed | GitHub issues | <1/release |

### Alerts & Notifications

#### Critical Alerts
1. **Release Workflow Failure**
   - **Trigger**: Workflow exits with non-zero code
   - **Channel**: GitHub Actions UI, email (GitHub settings)
   - **Response**: Investigate immediately, may need manual intervention

2. **Version Mismatch Detected**
   - **Trigger**: Workflow verification step fails
   - **Channel**: Workflow failure, PR status check
   - **Response**: Fix versions and update PR

3. **PyPI Publish Partial Failure**
   - **Trigger**: Some packages publish, others fail
   - **Channel**: Workflow logs, email
   - **Response**: Manual publish or rollback decision

#### Informational Notifications
1. **Release Completed Successfully**
   - **Trigger**: All workflow steps succeed
   - **Channel**: GitHub Actions, release notifications
   - **Response**: None (success)

2. **Tags Created**
   - **Trigger**: Tag creation step succeeds
   - **Channel**: GitHub Activity, watchers notified
   - **Response**: None (informational)

### Dashboards

**GitHub Actions Dashboard** (built-in):
- Workflow run history
- Success/failure rates
- Duration trends
- Recent releases

**PyPI Dashboard** (per package):
- Download statistics
- Version history
- File checksums

**No custom dashboard needed** - GitHub provides sufficient visibility

### Runbooks

#### Runbook: Release Failed - Version Mismatch
**Symptom**: Workflow fails at "Verify versions in all packages"

**Diagnosis**:
```bash
# Check versions
grep version packages/*/pyproject.toml
```

**Resolution**:
1. Update PR to fix version mismatches
2. Ensure all packages at same version
3. Force-push to release branch
4. Merge PR again

#### Runbook: Release Failed - PyPI Publish Error
**Symptom**: Workflow fails at "Publish all packages"

**Diagnosis**:
- Check workflow logs for error message
- Check PyPI status page
- Verify PyPI token hasn't expired

**Resolution Option 1** - Retry:
```bash
# Re-run workflow from GitHub Actions UI
# PyPI handles duplicate uploads gracefully
```

**Resolution Option 2** - Manual Publish:
```bash
# For remaining packages that didn't publish
cd packages/{package}
uv tool run hatch build
uv tool run hatch publish
```

**Resolution Option 3** - Rollback:
```bash
# Yank versions from PyPI (if needed)
# Release patch version with fix
```

#### Runbook: Tags Created But Publish Failed
**Symptom**: Tags exist but packages not on PyPI

**Resolution**:
1. Determine which packages need publishing
2. Manually publish:
   ```bash
   cd packages/{package}
   uv tool run hatch publish
   ```
3. Create GitHub releases manually if needed
4. Document incident for process improvement

#### Runbook: Rollback a Release
**Scenario**: Released version has critical bug

**Steps**:
1. **Yank versions on PyPI** (not delete):
   ```bash
   # Via web UI or API
   # Makes version unavailable for new installs
   ```

2. **Create patch release** with fix:
   ```bash
   ./scripts/release.sh patch
   # This creates v2.2.1 with fix
   ```

3. **Update release notes** to indicate v2.2.0 was yanked

4. **Notify users** via GitHub release notes, Discord, etc.

## 9. Rollout & Migration

### Feature Flags
**Not Applicable** - This is a process change, not a feature flag candidate

### Migration Strategy

#### Phase 1: Preparation (Pre-Release)
**Objective**: Ensure readiness for unified release

**Tasks**:
1. Complete all in-flight releases using old process
2. Merge all pending PRs that affect versions
3. Coordinate team freeze on individual package releases
4. Review and approve TDR

**Duration**: 1-2 days

**Success Criteria**:
- No pending release branches
- All packages at known versions
- Team aware of upcoming change

#### Phase 2: Implementation
**Objective**: Deploy new release process

**Tasks**:
1. Update release script
2. Create unified workflow
3. Remove old workflows
4. Create CHANGELOGs
5. Update documentation

**Duration**: 2-3 hours

**Success Criteria**:
- All files updated per TDR
- Tests pass
- Documentation updated

#### Phase 3: First Unified Release (v2.2.0)
**Objective**: Execute first release with new process

**Tasks**:
1. Run new release script
2. Review PR carefully
3. Merge PR
4. Monitor workflow execution
5. Verify all packages published
6. Test installations

**Duration**: 30 minutes active, 5 minutes workflow

**Success Criteria**:
- Single PR created
- All packages at v2.2.0
- All packages published to PyPI
- GitHub releases created
- Installation works

**Rollback Plan**:
If first release fails:
1. Don't delete workflow file yet
2. Investigate failure
3. Fix issues
4. Retry with v2.2.1

#### Phase 4: Validation
**Objective**: Confirm unified release works

**Tasks**:
1. Create second release (v2.2.1 or v2.3.0)
2. Verify repeatability
3. Document any issues
4. Gather team feedback

**Duration**: 1 week after first release

**Success Criteria**:
- Second release succeeds smoothly
- No manual intervention needed
- Team comfortable with new process

#### Phase 5: Cleanup
**Objective**: Remove old infrastructure

**Tasks**:
1. Archive old release scripts
2. Update `.github/workflows/` directory
3. Document new process in team wiki/docs
4. Create training materials if needed

**Duration**: 1 hour

**Success Criteria**:
- Old files removed
- Documentation complete
- Team trained

### Rollback Plan

**If unified release must be reverted**:

1. **Restore old workflow files** from git history:
   ```bash
   git checkout main~1 -- .github/workflows/release-*.yml
   ```

2. **Restore old release scripts**:
   ```bash
   git checkout main~1 -- scripts/release.sh scripts/release-all.sh
   ```

3. **Add version constraints back** to package dependencies

4. **Release patch versions** using old process

5. **Document lessons learned** for future attempt

**Blast Radius**:
- Only affects release process
- Does not affect published packages
- Does not affect users
- Does not affect production systems

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Approach

**Challenge**: This is infrastructure/tooling change, not application code

**Adapted TDD Strategy**:
1. **Scripts**: Test in dry-run mode before actual execution
2. **Workflows**: Test on test repository or fork first
3. **Integration**: First release is the integration test

### Spec→Test Mapping

| Acceptance Criterion | Test Method | Implementation |
|---------------------|-------------|----------------|
| **AC-1**: Synchronized version numbers | Manual verification + workflow check | Workflow step |
| **AC-2**: Single release script | Execute script, verify output | Bash script |
| **AC-3**: No inter-package version constraints | grep verification | sed commands |
| **AC-4**: Single unified workflow | Workflow execution | GitHub Actions |
| **AC-5**: Individual GitHub releases | Verify releases created | gh CLI commands |
| **AC-6**: Per-package CHANGELOGs | File existence check | Created files |
| **AC-7**: Backward compatibility | Historical tag check | Git operations |
| **AC-8**: Failed publish handling | Simulate failure, verify error | Workflow logic |

### Test Tiers

#### Unit Tests (Scripts)

**Test: Release Script Argument Validation**
```bash
# Test invalid version type
./scripts/release.sh invalid
# Expected: Error message, exit 1

# Test valid version types
./scripts/release.sh major  # Should work
./scripts/release.sh minor  # Should work
./scripts/release.sh patch  # Should work
```

**Test: Version Bumping Logic**
```bash
# Test major bump: 2.1.0 → 3.0.0
# Test minor bump: 2.1.0 → 2.2.0
# Test patch bump: 2.1.0 → 2.1.1
```

**Test: Git Operations**
```bash
# Test branch creation
# Test commit creation
# Test push operation (dry-run)
```

#### Integration Tests (Workflow)

**Test: Version Verification Step**
```yaml
# Create test scenario with mismatched versions
# packages/tyler: 2.2.0
# packages/narrator: 2.1.0
# Verify workflow fails with clear error
```

**Test: Tag Creation**
```bash
# Verify 4 tags created
# Verify tag names correct
# Verify tags point to correct commit
```

**Test: Build Step**
```bash
# Verify all packages build successfully
# Verify dist/ directories created
# Verify wheel and sdist files exist
```

#### End-to-End Tests

**Test: Complete Release Flow**
1. Run release script locally
2. Create PR
3. Merge PR
4. Verify workflow runs
5. Verify packages on PyPI
6. Verify GitHub releases
7. Test installation

**Test: Installation Verification**
```bash
# Create fresh virtual environment
python3 -m venv test-env
source test-env/bin/activate

# Install packages
pip install slide-tyler==2.2.0
pip install slide-narrator==2.2.0
pip install slide-space-monkey==2.2.0
pip install slide-lye==2.2.0

# Verify imports work
python -c "from tyler import Agent; from narrator import Thread; print('Success')"
```

### Negative & Edge Cases

| Test Case | Expected Behavior | Verification Method |
|-----------|------------------|---------------------|
| Run release script with uncommitted changes | Error, exit 1 | Manual test |
| Run release script not on main branch | Checkout main first | Script logic |
| Version mismatch in workflow | Workflow fails, clear error | Workflow logic |
| PyPI publish fails for one package | Workflow fails, other packages may be published | Simulated failure |
| Network error during git push | Script fails, branch not pushed | Error handling |
| PR creation fails | Script fails, branch pushed but no PR | Error handling |
| Duplicate tag already exists | Git error, workflow fails | Git operations |
| Invalid version format in branch name | Workflow validation fails | Regex check |

### Dry-Run Testing

**Before first real release**, test the process:

```bash
# 1. Fork repository or create test repo
# 2. Copy new scripts and workflows
# 3. Run release script in dry-run mode (add --dry-run flag)
# 4. Verify all steps execute correctly
# 5. Test workflow on test repository with test PyPI
```

### Monitoring During First Release

**Checklist for first release**:
- [ ] Watch workflow in real-time
- [ ] Verify each step completes
- [ ] Check logs for errors/warnings
- [ ] Verify tags created
- [ ] Check PyPI for all 4 packages
- [ ] Verify GitHub releases
- [ ] Test installation in clean environment
- [ ] Document any issues/surprises

## 11. Risks & Open Questions

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|---------|------------|
| **First release fails** | Medium | Medium | Test thoroughly on fork/test repo first; have rollback plan ready |
| **PyPI rate limiting** | Low | Medium | Add delays between publishes if needed; publish sequentially |
| **Version drift over time** | Low | High | Add CI check to verify versions match; automate verification |
| **Users confused by version jump** | Medium | Low | Clear release notes explaining synchronization; document in README |
| **Partial publish creates inconsistency** | Low | High | Fail fast on errors; document recovery procedures |
| **Team unfamiliar with new process** | Medium | Low | Documentation, runbooks, first release walkthrough |
| **Workflow permissions insufficient** | Low | Medium | Test on fork first; verify permissions in advance |
| **GitHub CLI not authenticated** | Low | Low | Check authentication before running script |

### Open Questions & Resolutions

**Q1**: Should we parallelize package builds in the workflow?
- **Answer**: Start sequential for simplicity, optimize later if needed
- **Rationale**: Sequential is easier to debug, only adds ~2 minutes

**Q2**: How do we handle hotfixes for a single package?
- **Answer**: Still release all packages with patch bump
- **Rationale**: Maintains synchronization, minimal overhead for patch

**Q3**: What if a package has no changes in a release?
- **Answer**: Version still bumps, changelog says "No changes"
- **Rationale**: Acceptable trade-off for consistency

**Q4**: Should we validate CHANGELOGs are updated before release?
- **Answer**: Out of scope for first version, could add later
- **Rationale**: Manual validation sufficient initially

**Q5**: How do we handle breaking changes in one package?
- **Answer**: Major version bump for all packages
- **Rationale**: Entire ecosystem moves together, clear versioning

**Q6**: Should the release script support a `--dry-run` flag?
- **Answer**: Yes, add this feature
- **Rationale**: Helpful for testing and validation

**Q7**: What happens if someone manually creates a tag?
- **Answer**: Workflow will fail, manual cleanup required
- **Rationale**: Acceptable, unusual scenario

**Q8**: Should we notify users about the unified release change?
- **Answer**: Yes, via release notes, README, Discord/Slack
- **Rationale**: Transparency about packaging changes

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

#### Milestone 1: Script Development
**Objective**: Create and test new release script

**Tasks**:

**Task 1.1: Implement Unified Release Script**
- [ ] Create new `/scripts/release.sh`
- [ ] Implement version bumping for all packages
- [ ] Implement version constraint removal
- [ ] Implement PR creation logic
- [ ] Add input validation
- [ ] Add error handling
- [ ] Test with `--dry-run` flag

**DoD**:
- Script creates single branch
- All packages updated to same version
- Version constraints removed
- PR created with correct content
- Error cases handled gracefully

**Time**: 1.5 hours  
**Owner**: AI Agent

**Task 1.2: Test Release Script**
- [ ] Test on fork/test repository
- [ ] Test all version types (major, minor, patch)
- [ ] Test error cases
- [ ] Verify PR content
- [ ] Document any issues

**DoD**:
- Script tested successfully
- All edge cases handled
- Documentation updated

**Time**: 30 minutes  
**Owner**: AI Agent + Human Review

#### Milestone 2: Workflow Development
**Objective**: Create and test unified workflow

**Tasks**:

**Task 2.1: Implement Unified Workflow**
- [ ] Create `.github/workflows/release.yml`
- [ ] Implement version verification step
- [ ] Implement tag creation step
- [ ] Implement build step
- [ ] Implement publish step
- [ ] Implement GitHub release step
- [ ] Add error handling and logging

**DoD**:
- Workflow file valid YAML
- All steps implemented
- Error handling in place
- Logging with groups/notices

**Time**: 1.5 hours  
**Owner**: AI Agent

**Task 2.2: Test Workflow**
- [ ] Test on fork/test repository with test PyPI
- [ ] Verify all steps execute
- [ ] Test failure scenarios
- [ ] Verify tags created correctly
- [ ] Verify releases created correctly

**DoD**:
- Workflow executes successfully
- All outputs correct
- Error cases handled

**Time**: 1 hour  
**Owner**: AI Agent + Human Review

#### Milestone 3: Cleanup & Documentation
**Objective**: Remove old infrastructure and update docs

**Tasks**:

**Task 3.1: Remove Old Infrastructure**
- [ ] Delete `.github/workflows/release-tyler.yml`
- [ ] Delete `.github/workflows/release-narrator.yml`
- [ ] Delete `.github/workflows/release-space-monkey.yml`
- [ ] Delete `.github/workflows/release-lye.yml`
- [ ] Archive or delete `scripts/release-all.sh`
- [ ] Archive or delete `scripts/update_dependent_constraints.py`

**DoD**:
- Old files removed
- Git history preserved
- No dangling references

**Time**: 15 minutes  
**Owner**: AI Agent

**Task 3.2: Setup CHANGELOG Generation**
- [ ] Install git-cliff: `brew install git-cliff`
- [ ] Test git-cliff on one package to verify output
- [ ] Verify conventional commits are being parsed correctly
- [ ] Create optional `.cliff.toml` config if needed for customization

**DoD**:
- git-cliff installed
- Tested and working
- Generates appropriate changelog format

**Time**: 15 minutes  
**Owner**: Human (tool installation) + AI Agent (testing)

**Note**: Actual CHANGELOGs will be generated automatically by the release script

**Task 3.3: Update Documentation**
- [ ] Update `/scripts/README.md` with new process
- [ ] Update root `/README.md` if mentions releases
- [ ] Update inter-package dependencies in pyproject.toml
- [ ] Create runbooks document

**DoD**:
- All documentation updated
- New process documented
- Runbooks available

**Time**: 1 hour  
**Owner**: AI Agent

#### Milestone 4: First Unified Release
**Objective**: Execute first unified release (v2.2.0)

**Tasks**:

**Task 4.1: Pre-Release Preparation**
- [ ] Ensure all pending PRs merged
- [ ] Verify no in-flight releases
- [ ] Coordinate with team
- [ ] Review all changes

**DoD**:
- Workspace clean
- Team coordinated
- Ready to release

**Time**: 30 minutes  
**Owner**: Human

**Task 4.2: Execute Release**
- [ ] Run `./scripts/release.sh minor`
- [ ] Review generated PR carefully
- [ ] Verify all changes correct
- [ ] Merge PR
- [ ] Monitor workflow

**DoD**:
- PR created
- PR merged
- Workflow completes successfully
- No errors

**Time**: 15 minutes active, 5 minutes workflow  
**Owner**: Human + AI Agent support

**Task 4.3: Verify Release**
- [ ] Check all tags created
- [ ] Check all packages on PyPI
- [ ] Check all GitHub releases
- [ ] Test installation in clean environment
- [ ] Verify versions match

**DoD**:
- All packages published
- Installation works
- Versions synchronized
- No issues detected

**Time**: 20 minutes  
**Owner**: Human + AI Agent

**Task 4.4: Post-Release**
- [ ] Announce unified release in Discord/Slack
- [ ] Update README with version sync note
- [ ] Monitor for issues
- [ ] Document lessons learned

**DoD**:
- Communication sent
- Monitoring in place
- Documentation complete

**Time**: 30 minutes  
**Owner**: Human

#### Milestone 5: Validation & Iteration
**Objective**: Ensure process is repeatable

**Tasks**:

**Task 5.1: Second Release**
- [ ] Execute second release (patch or minor)
- [ ] Verify process smooth
- [ ] Document any friction points
- [ ] Make improvements if needed

**DoD**:
- Second release successful
- Process feels stable
- Team confident

**Time**: 1 hour  
**Owner**: Human (when next release needed)

**Task 5.2: Retrospective**
- [ ] Gather team feedback
- [ ] Review what worked/didn't
- [ ] Identify improvements
- [ ] Update documentation

**DoD**:
- Feedback collected
- Improvements identified
- Documentation updated

**Time**: 1 hour  
**Owner**: Team

### Total Timeline

**Development Phase**: 5-6 hours
- Script development: 2 hours
- Workflow development: 2.5 hours
- Cleanup & docs: 1.5 hours

**Execution Phase**: 2 hours
- First release: 1 hour
- Verification: 1 hour

**Total**: ~8 hours spread over 2-3 days

### Critical Path

1. Script development (2 hours) → Must complete first
2. Workflow development (2.5 hours) → Must complete second
3. Documentation (1.5 hours) → Can overlap
4. First release (1 hour) → Must complete after 1-3
5. Validation (1 hour+) → Final step

### Dependencies

- **No external dependencies**: All work can be done within repository
- **GitHub CLI required**: Must be installed and authenticated
- **Team coordination**: Need freeze on releases during implementation
- **Approval gate**: TDR must be approved before implementation

---

**Approval Gate**: Do not start implementation until this TDR is reviewed and approved.

**Review Checklist**:
- [ ] Spec alignment verified - all acceptance criteria covered
- [ ] Technical approach sound - scripts and workflows well-designed
- [ ] Risk assessment acceptable - mitigations in place
- [ ] Test coverage sufficient - all scenarios covered
- [ ] Rollback plan clear - can revert if needed
- [ ] No security concerns - token management appropriate
- [ ] Timeline realistic - 8 hours total reasonable
- [ ] Documentation complete - all necessary docs covered

