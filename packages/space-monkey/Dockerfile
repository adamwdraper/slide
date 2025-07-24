FROM python:3.12.9-slim

# Set up non-root user
RUN useradd -m -u 1000 agent && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system slide-space-monkey

# Copy application code
COPY --chown=agent:agent . .

# Switch to non-root user
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Use exec form to ensure proper signal handling
CMD ["python", "-u", "agent.py"] 