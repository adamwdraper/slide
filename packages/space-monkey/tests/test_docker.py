"""
Tests for Docker build and runtime functionality.

These tests verify that the Docker configuration works correctly,
including build process, health checks, and signal handling.
"""
import json
import os
import subprocess
import tempfile
import time
import pytest
import requests
from pathlib import Path


TRANSIENT_DOCKER_ERRORS = (
    "context deadline exceeded",
    "deadlineexceeded",
    "failed to do request",
    "failed to resolve source metadata",
    "i/o timeout",
    "net/http: request canceled",
    "network is unreachable",
    "temporary failure",
    "timed out",
    "tls handshake timeout",
)


def docker_output(result):
    """Return combined Docker command output for assertions and skips."""
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def short_output(output, limit=1000):
    """Trim long Docker output while keeping the actionable tail."""
    if len(output) <= limit:
        return output
    return f"...{output[-limit:]}"


def is_transient_docker_error(output):
    """Check whether Docker failed because an external registry/network was unavailable."""
    lower_output = output.lower()
    return any(error in lower_output for error in TRANSIENT_DOCKER_ERRORS)


def run_docker_command(command, **kwargs):
    """Run a Docker command and skip tests on transient external network errors."""
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    output = docker_output(result)
    if result.returncode != 0 and is_transient_docker_error(output):
        pytest.skip(f"Docker registry/network unavailable: {short_output(output)}")
    return result


def build_test_image(package_dir, tag):
    """Build the Space Monkey Docker image for a test."""
    result = run_docker_command(
        ["docker", "build", "-t", tag, "."],
        cwd=package_dir,
    )
    assert result.returncode == 0, f"Docker build failed: {docker_output(result)}"


def is_docker_compose_available():
    """Check if docker-compose is available on the system."""
    try:
        result = subprocess.run(["docker-compose", "version"], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        # docker-compose command not found
        return False


def is_docker_available():
    """Check if docker is available on the system."""
    try:
        result = subprocess.run(["docker", "version"], capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        # docker command not found
        return False


class TestDockerBuild:
    """Test Docker image building."""
    
    @pytest.mark.integration
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists in the package."""
        dockerfile_path = Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile not found in package"
    
    @pytest.mark.integration
    def test_dockerignore_exists(self):
        """Test that .dockerignore exists."""
        dockerignore_path = Path(__file__).parent.parent / ".dockerignore"
        assert dockerignore_path.exists(), ".dockerignore not found in package"
    
    @pytest.mark.integration
    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml not found in package"
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not is_docker_available(),
        reason="Docker not available"
    )
    def test_docker_build(self):
        """Test that the Docker image builds successfully."""
        package_dir = Path(__file__).parent.parent
        image_tag = "space-monkey-test:latest"
        
        try:
            build_test_image(package_dir, image_tag)
        finally:
            subprocess.run(["docker", "rmi", image_tag], capture_output=True)
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not is_docker_available(),
        reason="Docker not available"
    )
    def test_docker_image_metadata(self):
        """Test that the built image has correct metadata."""
        package_dir = Path(__file__).parent.parent
        image_tag = "space-monkey-test:metadata"
        
        try:
            build_test_image(package_dir, image_tag)

            # Inspect the image
            result = run_docker_command(["docker", "inspect", image_tag])
            assert result.returncode == 0, f"Docker inspect failed: {docker_output(result)}"

            image_data = json.loads(result.stdout)
            assert image_data, f"Docker inspect returned no metadata: {docker_output(result)}"
            image_config = image_data[0]["Config"]

            # Check exposed port
            assert "8000/tcp" in image_config["ExposedPorts"]

            # Check user is not root
            assert image_config["User"] == "agent"

            # Check health check exists
            assert image_config["Healthcheck"] is not None
            assert "curl" in " ".join(image_config["Healthcheck"]["Test"])
        finally:
            subprocess.run(["docker", "rmi", image_tag], capture_output=True)


class TestDockerRuntime:
    """Test Docker container runtime behavior."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not is_docker_available(),
        reason="Docker not available"
    )
    def test_container_starts_with_env_vars(self):
        """Test that container starts with required environment variables."""
        package_dir = Path(__file__).parent.parent
        image_tag = "space-monkey-test:env"
        
        # Create a test agent.py that exits cleanly
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import os
import sys

# Check required env vars
required_vars = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN', 'OPENAI_API_KEY']
for var in required_vars:
    if var not in os.environ:
        print(f"ERROR: Missing required environment variable: {var}")
        sys.exit(1)

print("All required environment variables present")
sys.exit(0)
""")
            test_script = f.name
        
        # Set file permissions so the 'agent' user in container can read it
        os.chmod(test_script, 0o644)
        
        try:
            build_test_image(package_dir, image_tag)
            
            # Run container with env vars
            result = run_docker_command(
                [
                    "docker", "run", "--rm",
                    "-e", "SLACK_BOT_TOKEN=xoxb-test",
                    "-e", "SLACK_APP_TOKEN=xapp-test",
                    "-e", "OPENAI_API_KEY=sk-test",
                    "-v", f"{test_script}:/app/agent.py:ro",
                    image_tag
                ]
            )
            
            assert result.returncode == 0, f"Docker run failed: {docker_output(result)}"
            assert "All required environment variables present" in result.stdout
            
            # Test missing env var
            result = run_docker_command(
                [
                    "docker", "run", "--rm",
                    "-e", "SLACK_BOT_TOKEN=xoxb-test",
                    "-e", "SLACK_APP_TOKEN=xapp-test",
                    # Missing OPENAI_API_KEY
                    "-v", f"{test_script}:/app/agent.py:ro",
                    image_tag
                ]
            )
            
            assert result.returncode == 1, f"Docker run should fail without OPENAI_API_KEY: {docker_output(result)}"
            assert "Missing required environment variable: OPENAI_API_KEY" in result.stdout
            
        finally:
            os.unlink(test_script)
            subprocess.run(["docker", "rmi", image_tag], capture_output=True)
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not is_docker_compose_available(),
        reason="Docker Compose not available"
    )
    def test_docker_compose_config(self):
        """Test that docker-compose.yml is valid."""
        package_dir = Path(__file__).parent.parent
        
        # Validate docker-compose config
        result = subprocess.run(
            ["docker-compose", "config"],
            cwd=package_dir,
            capture_output=True,
            text=True,
            env={**os.environ, 
                 "SLACK_BOT_TOKEN": "xoxb-test",
                 "SLACK_APP_TOKEN": "xapp-test",
                 "OPENAI_API_KEY": "sk-test"}
        )
        
        assert result.returncode == 0, f"docker-compose config invalid: {result.stderr}"
        
        # Check that the config includes our service
        assert "slack-agent:" in result.stdout
        assert "SLACK_BOT_TOKEN" in result.stdout
