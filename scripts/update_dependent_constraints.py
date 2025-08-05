#!/usr/bin/env python3
"""
Update constraints in dependent packages when a package is released.

This script finds all packages that depend on the given package and updates
their minimum version constraints to the new version.
"""
import re
import sys
from pathlib import Path

# Define the dependency relationships
DEPENDENCIES = {
    'narrator': ['tyler', 'space-monkey'],  # These packages depend on narrator
    'lye': ['tyler'],  # These packages depend on lye  
    'tyler': ['space-monkey'],  # These packages depend on tyler
    'space-monkey': [],  # Nothing depends on space-monkey
}

def update_constraint_in_file(file_path, package_name, new_version, dry_run=False, quiet=False):
    """Update the constraint for a package in a pyproject.toml file."""
    content = file_path.read_text()
    
    # Look for the constraint pattern: "slide-{package}>=x.y.z"
    slide_package = f"slide-{package_name}"
    pattern = rf'"{slide_package}>=[\d\.]+"'
    replacement = f'"{slide_package}>={new_version}"'
    
    # Check if the pattern exists
    if not re.search(pattern, content):
        if not quiet:
            print(f"  No {slide_package} constraint found in {file_path}")
        return False
    
    # Replace the constraint
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        if not quiet:
            print(f"  No changes needed in {file_path}")
        return False
    
    if not dry_run:
        file_path.write_text(new_content)
        if not quiet:
            print(f"  ✓ Updated {slide_package} constraint to >={new_version} in {file_path}")
    else:
        if not quiet:
            print(f"  [DRY RUN] Would update {slide_package} constraint to >={new_version} in {file_path}")
    
    return True

def update_dependent_constraints(updated_package, new_version, dry_run=False, quiet=False):
    """Update constraints in all packages that depend on the updated package."""
    
    if updated_package not in DEPENDENCIES:
        if not quiet:
            print(f"Unknown package: {updated_package}")
        return False
    
    dependent_packages = DEPENDENCIES[updated_package]
    
    if not dependent_packages:
        if not quiet:
            print(f"No packages depend on {updated_package}")
        return True
    
    if not quiet:
        print(f"Updating constraints for {updated_package} v{new_version}...")
    
    updated_any = False
    
    for dep_package in dependent_packages:
        dep_package_dir = Path(f"packages/{dep_package}")
        pyproject_path = dep_package_dir / "pyproject.toml"
        
        if not pyproject_path.exists():
            if not quiet:
                print(f"  Warning: {pyproject_path} not found")
            continue
        
        if not quiet:
            print(f"  Checking {dep_package}...")
        
        if update_constraint_in_file(pyproject_path, updated_package, new_version, dry_run, quiet):
            updated_any = True
    
    return updated_any

def main():
    if len(sys.argv) < 3:
        print("Usage: python update_dependent_constraints.py <package> <new_version> [--dry-run] [--quiet]")
        print("Available packages: tyler, narrator, space-monkey, lye")
        print("Example: python update_dependent_constraints.py narrator 0.4.0")
        sys.exit(1)
    
    package_name = sys.argv[1]
    new_version = sys.argv[2]
    
    # Parse flags
    dry_run = '--dry-run' in sys.argv
    quiet = '--quiet' in sys.argv
    
    # Validate package name
    valid_packages = ['tyler', 'narrator', 'space-monkey', 'lye']
    if package_name not in valid_packages:
        if not quiet:
            print(f"Package must be one of: {', '.join(valid_packages)}")
        sys.exit(1)
    
    # Validate version format
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        if not quiet:
            print(f"Version must be in format x.y.z, got: {new_version}")
        sys.exit(1)
    
    # Update constraints
    success = update_dependent_constraints(package_name, new_version, dry_run, quiet)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()