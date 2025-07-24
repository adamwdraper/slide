"""
Tests for Docker build and runtime functionality.

These tests verify that the Docker configuration works correctly,
including build process, health checks, and signal handling.
"""
import os
import subprocess
import tempfile
import time
import pytest
import requests
from pathlib import Path


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
        
        # Build the image with a test tag
        result = subprocess.run(
            ["docker", "build", "-t", "space-monkey-test:latest", "."],
            cwd=package_dir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
        
        # Clean up
        subprocess.run(["docker", "rmi", "space-monkey-test:latest"], capture_output=True)
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        not is_docker_available(),
        reason="Docker not available"
    )
    def test_docker_image_metadata(self):
        """Test that the built image has correct metadata."""
        package_dir = Path(__file__).parent.parent
        
        # Build the image
        subprocess.run(
            ["docker", "build", "-t", "space-monkey-test:metadata", "."],
            cwd=package_dir,
            capture_output=True
        )
        
        # Inspect the image
        result = subprocess.run(
            ["docker", "inspect", "space-monkey-test:metadata"],
            capture_output=True,
            text=True
        )
        
        import json
        image_data = json.loads(result.stdout)[0]
        
        # Check exposed port
        assert "8000/tcp" in image_data["Config"]["ExposedPorts"]
        
        # Check user is not root
        assert image_data["Config"]["User"] == "agent"
        
        # Check health check exists
        assert image_data["Config"]["Healthcheck"] is not None
        assert "curl" in " ".join(image_data["Config"]["Healthcheck"]["Test"])
        
        # Clean up
        subprocess.run(["docker", "rmi", "space-monkey-test:metadata"], capture_output=True)


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
            # Build test image
            subprocess.run(
                ["docker", "build", "-t", "space-monkey-test:env", "."],
                cwd=package_dir,
                capture_output=True
            )
            
            # Run container with env vars
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-e", "SLACK_BOT_TOKEN=xoxb-test",
                    "-e", "SLACK_APP_TOKEN=xapp-test",
                    "-e", "OPENAI_API_KEY=sk-test",
                    "-v", f"{test_script}:/app/agent.py:ro",
                    "space-monkey-test:env"
                ],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
            assert "All required environment variables present" in result.stdout
            
            # Test missing env var
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-e", "SLACK_BOT_TOKEN=xoxb-test",
                    "-e", "SLACK_APP_TOKEN=xapp-test",
                    # Missing OPENAI_API_KEY
                    "-v", f"{test_script}:/app/agent.py:ro",
                    "space-monkey-test:env"
                ],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 1
            assert "Missing required environment variable: OPENAI_API_KEY" in result.stdout
            
        finally:
            os.unlink(test_script)
            subprocess.run(["docker", "rmi", "space-monkey-test:env"], capture_output=True)
    
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