# Narrator helper scripts

This directory contains helper scripts for common Narrator development tasks.

## Docker scripts

- `setup-docker.sh` - Starts PostgreSQL container and initializes database tables
- `teardown-docker.sh` - Stops containers and optionally removes data

## Usage

```bash
# Quick start with PostgreSQL
./scripts/setup-docker.sh

# Stop and clean up
./scripts/teardown-docker.sh
```

These scripts are provided for convenience during development. For production deployments, use your organization's standard database provisioning process.
