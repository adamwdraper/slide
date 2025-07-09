import pytest
import subprocess
from unittest.mock import patch, MagicMock
from tyler.tools.command_line import (
    is_safe_path,
    is_safe_command,
    validate_file_operation,
    run_command,
    SAFE_COMMANDS,
    FILE_MODIFYING_COMMANDS
)

@pytest.fixture
def mock_cwd():
    """Fixture to mock current working directory"""
    with patch('os.getcwd') as mock:
        mock.return_value = '/workspace'
        yield mock

def test_is_safe_path(mock_cwd):
    """Test path safety validation"""
    # Valid paths
    assert is_safe_path('/workspace/test.txt')
    assert is_safe_path('test.txt')
    assert is_safe_path('./test.txt')
    
    # Invalid paths
    assert not is_safe_path('/etc/passwd')
    assert not is_safe_path('../outside.txt')
    assert not is_safe_path(None)
    assert not is_safe_path('')
    assert not is_safe_path('   ')
    assert not is_safe_path('/workspace/../etc/passwd')
    assert not is_safe_path('\0malicious')

def test_is_safe_command():
    """Test command safety validation"""
    # Valid commands
    assert is_safe_command('ls')
    assert is_safe_command('ls -la')
    assert is_safe_command('cat test.txt')
    assert is_safe_command('grep pattern file.txt')
    
    # Invalid commands
    assert not is_safe_command('rm -rf /')
    assert not is_safe_command('ls && rm -rf /')
    assert not is_safe_command('ls; rm -rf /')
    assert not is_safe_command('ls | rm -rf /')
    assert not is_safe_command('`rm -rf /`')
    assert not is_safe_command('$(rm -rf /)')
    assert not is_safe_command('sudo rm -rf /')
    assert not is_safe_command('not_whitelisted_cmd')

def test_validate_file_operation(mock_cwd):
    """Test validation of file modification commands"""
    # Valid operations
    assert validate_file_operation('rm', ['rm', 'test.txt'])
    assert validate_file_operation('cp', ['cp', 'source.txt', 'dest.txt'])
    assert validate_file_operation('mv', ['mv', 'old.txt', 'new.txt'])
    assert validate_file_operation('echo', ['echo', 'text', '>', 'file.txt'])
    assert validate_file_operation('mkdir', ['mkdir', 'newdir'])
    
    # Invalid operations
    assert not validate_file_operation('rm', ['rm', '-rf', '/'])
    assert not validate_file_operation('rm', ['rm', '-r', 'dir'])
    assert not validate_file_operation('cp', ['cp', '/etc/passwd', 'hack.txt'])
    assert not validate_file_operation('mv', ['mv', 'file.txt', '/etc/passwd'])
    assert not validate_file_operation('cp', ['cp', 'file1', 'file2', 'file3'])

@patch('subprocess.run')
def test_run_command_success(mock_run, mock_cwd):
    """Test successful command execution"""
    mock_process = MagicMock()
    mock_process.stdout = "command output"
    mock_process.stderr = ""
    mock_process.returncode = 0
    mock_run.return_value = mock_process

    result = run_command(command="ls -la")
    
    assert result["command"] == "ls -la"
    assert result["output"] == "command output"
    assert result["error"] is None
    assert result["exit_code"] == 0
    
    mock_run.assert_called_once_with(
        "ls -la",
        shell=True,
        cwd=".",
        capture_output=True,
        text=True,
        timeout=30
    )

@patch('subprocess.run')
def test_run_command_with_error(mock_run):
    """Test command execution with error"""
    mock_process = MagicMock()
    mock_process.stdout = ""
    mock_process.stderr = "error message"
    mock_process.returncode = 1
    mock_run.return_value = mock_process

    result = run_command(command="cat nonexistent.txt")
    
    assert result["command"] == "cat nonexistent.txt"
    assert result["output"] == ""
    assert result["error"] == "error message"
    assert result["exit_code"] == 1

def test_run_command_unsafe():
    """Test rejection of unsafe commands"""
    result = run_command(command="rm -rf /")
    assert "error" in result
    assert "Command not allowed" in result["error"]

@patch('subprocess.run')
def test_run_command_timeout(mock_run):
    """Test command timeout handling"""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 100", timeout=30)
    
    result = run_command(command="sleep 100")
    assert "error" in result
    assert "Command timed out" in result["error"]

def test_safe_commands_consistency():
    """Test consistency between SAFE_COMMANDS and FILE_MODIFYING_COMMANDS"""
    # All file modifying commands should be in safe commands
    assert all(cmd in SAFE_COMMANDS for cmd in FILE_MODIFYING_COMMANDS)
    
    # All commands should have descriptions
    assert all(isinstance(desc, str) and desc for desc in SAFE_COMMANDS.values())

@patch('subprocess.run')
def test_run_command_working_dir(mock_run):
    """Test command execution with custom working directory"""
    mock_process = MagicMock()
    mock_process.stdout = "command output"
    mock_process.stderr = ""
    mock_process.returncode = 0
    mock_run.return_value = mock_process

    result = run_command(command="ls", working_dir="/workspace/subdir")
    
    mock_run.assert_called_once_with(
        "ls",
        shell=True,
        cwd="/workspace/subdir",
        capture_output=True,
        text=True,
        timeout=30
    ) 