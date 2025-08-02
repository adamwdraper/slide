#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def update_version_in_file(file_path, current_version, new_version, pattern=None, dry_run=False, quiet=False):
    content = file_path.read_text()
    if pattern is None:
        pattern = f'"{current_version}"'
        replacement = f'"{new_version}"'
    else:
        replacement = pattern.replace(current_version, new_version)
    
    new_content = content.replace(pattern, replacement)
    if new_content == content:
        if not quiet:
            print(f"Warning: No version update made in {file_path}")
        return False
    
    if not dry_run:
        file_path.write_text(new_content)
        if not quiet:
            print(f"Updated version in {file_path}")
    return True

def bump_version(package_name, version_type='patch', dry_run=False, quiet=False):
    # Validate package name
    valid_packages = ['tyler', 'narrator', 'space-monkey', 'lye']
    if package_name not in valid_packages:
        if not quiet:
            print(f"Package must be one of: {', '.join(valid_packages)}")
        sys.exit(1)
    
    # Convert space-monkey to space_monkey for file path
    package_dir = package_name.replace('-', '_')
    
    pyproject_path = Path('pyproject.toml')
    init_path = Path(f'{package_dir}/__init__.py')
    
    # Validate paths exist
    if not pyproject_path.exists():
        if not quiet:
            print(f"Could not find pyproject.toml in current directory")
        sys.exit(1)
    
    if not init_path.exists():
        if not quiet:
            print(f"Could not find {init_path}")
        sys.exit(1)
    
    # Find current version in pyproject.toml
    content = pyproject_path.read_text()
    version_match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', content)
    if not version_match:
        if not quiet:
            print("Could not find version in pyproject.toml")
        sys.exit(1)
        
    current_version = version_match.group(1)
    major, minor, patch = map(int, current_version.split('.'))
    
    # Bump version according to type
    if version_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif version_type == 'minor':
        minor += 1
        patch = 0
    else:  # patch
        patch += 1
        
    new_version = f"{major}.{minor}.{patch}"
    
    if not dry_run:
        # Update version in pyproject.toml
        pyproject_pattern = f'version = "{current_version}"'
        update_version_in_file(pyproject_path, current_version, new_version, pyproject_pattern, dry_run, quiet)
        
        # Update version in __init__.py
        init_pattern = f'__version__ = "{current_version}"'
        update_version_in_file(init_path, current_version, new_version, init_pattern, dry_run, quiet)
        
        if not quiet:
            print(f"Version bumped from {current_version} to {new_version}")
    
    return new_version

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <package> [version_type] [--dry-run] [--quiet]")
        print("Available packages: tyler, narrator, space-monkey, lye")
        print("Version types: major, minor, patch (default: patch)")
        sys.exit(1)
    
    package_name = sys.argv[1]
    version_type = 'patch'
    dry_run = False
    quiet = False
    
    # Parse remaining arguments
    args = sys.argv[2:]
    if '--dry-run' in args:
        dry_run = True
        args.remove('--dry-run')
    
    if '--quiet' in args:
        quiet = True
        args.remove('--quiet')
    
    if args:
        version_type = args[0]
        
    if version_type not in ('major', 'minor', 'patch'):
        if not quiet:
            print("Version type must be one of: major, minor, patch")
        sys.exit(1)
        
    new_version = bump_version(package_name, version_type, dry_run, quiet)
    if dry_run or quiet:
        print(new_version)  # Only print version number for dry run or quiet mode 