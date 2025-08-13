# Narrator helper scripts

This directory contains helper scripts for common Narrator development tasks when working with the source code.

## Docker scripts (Source Code Only)

- `setup-docker.sh` - Starts PostgreSQL container and initializes database tables
- `teardown-docker.sh` - Stops containers and optionally removes data

**Note**: These scripts are only available when working with the Narrator source code. If you've installed Narrator as a package, use the built-in CLI commands instead:

```bash
# Installed package users should use:
uv run narrator docker-setup    # Start PostgreSQL and initialize
uv run narrator docker-stop      # Stop container
```

## Source Code Usage

If you're working with the Narrator source code:

```bash
# Quick start with PostgreSQL
./scripts/setup-docker.sh

# Stop and clean up
./scripts/teardown-docker.sh
```

For production deployments, use your organization's standard database provisioning process.
