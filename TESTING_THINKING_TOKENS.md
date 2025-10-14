# Testing Thinking Tokens

## Quick Test Guide

### Option 1: Use Anthropic Claude (RECOMMENDED)

```bash
# Use the Anthropic config
uv run tyler chat --config tyler-chat-config-anthropic.yaml

# Ask a reasoning question
You: What's 137 * 284? Show your work.

# You should see:
┌─ 💭 Thinking (reasoning) ──────┐  ← Gray panel
│ Let me calculate step by step  │
└─────────────────────────────────┘

┌─ Agent ────────────────────────┐  ← Blue panel
│ The answer is 38,908           │
└─────────────────────────────────┘
```

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable
- Model: `anthropic/claude-3-7-sonnet-20250219`
- Config includes: `reasoning_effort: "low"`

### Option 2: Use Deepseek

```bash
# Edit your config:
# model_name: "deepseek/deepseek-chat"
# reasoning_effort: "low"

# Set API key
export DEEPSEEK_API_KEY=your_key

# Run chat
uv run tyler chat
```

### Option 3: Debug Script

```bash
# See what's actually in the delta
uv run python test_thinking_debug.py
```

## Supported Models for Thinking Tokens

According to [LiteLLM docs](https://docs.litellm.ai/docs/reasoning_content):

✅ **Supported:**
- Deepseek (`deepseek/deepseek-chat`)
- Anthropic (`anthropic/claude-3-7-sonnet-20250219`)
- Bedrock (Anthropic + Deepseek)
- Vertex AI (Anthropic)
- OpenRouter
- XAI
- Google AI Studio
- Perplexity
- Mistral AI
- Groq

❌ **NOT Supported (yet):**
- OpenAI (o1, o3, gpt-4.1 models)

## Why OpenAI Models Don't Show Thinking

OpenAI's o1/o3 models do have reasoning capabilities, but LiteLLM v1.63.0 hasn't added them to the `reasoning_content` standardization yet. 

**Workaround:** Use Anthropic Claude or Deepseek for now.

## Required Config

Your config MUST include `reasoning_effort` to enable thinking:

```yaml
model_name: "anthropic/claude-3-7-sonnet-20250219"
reasoning_effort: "low"  # ← REQUIRED!
```

Or for Anthropic, you can use:

```yaml
thinking:
  type: "enabled"
  budget_tokens: 1024
```

## Troubleshooting

**Not seeing thinking panel?**
1. Check model is in supported list
2. Verify `reasoning_effort` is in config
3. Run with debug: `TYLER_LOG_LEVEL=DEBUG uv run tyler chat`
4. Look for: `DEBUG - Found reasoning_content: ...`

**No reasoning_content in delta?**
- Model may not support thinking in streaming (only final message)
- Try different provider (Anthropic most reliable)
- Check LiteLLM version: `pip show litellm` (need >=1.63.0)

