# Troubleshooting

Common issues and their solutions when working with Tyler.

## Installation issues

### Package conflicts
If you encounter package conflicts during installation:
1. Create a new virtual environment
2. Install Tyler in the clean environment
3. Install additional packages one by one

### Version mismatch
Make sure you have compatible versions:
- Python 3.9 or higher
- Latest pip version
- Latest Tyler version

## Runtime errors

### API key errors
- Check if OPENAI_API_KEY is set
- Verify API key is valid
- Check API key permissions

### Tool errors
- Ensure required tool dependencies are installed
- Check tool configuration
- Verify tool permissions

### Memory issues
- Reduce max_tokens if hitting context limits
- Use streaming for large responses
- Clear conversation history periodically

## Performance issues

### Slow responses
- Enable response streaming
- Reduce tool timeout values
- Use async where possible

### High memory usage
- Limit conversation history
- Use efficient storage backends
- Clean up temporary files

## Common error messages

### "API key not found"
Set your OpenAI API key:
```bash
export OPENAI_API_KEY=your-key-here
```

### "Tool not found"
Add the tool to your configuration:
```python
agent = Agent(
    tools=["web", "file", "your-tool"]
)
```

### "Context length exceeded"
Reduce the input size or clear history:
```python
agent.clear_history()
```

## Getting help

If you're still stuck:
1. Check the [GitHub issues](https://github.com/adamwdraper/tyler/issues)
2. Join our [Discord community](https://discord.gg/tyler)
3. Open a new issue with details about your problem 