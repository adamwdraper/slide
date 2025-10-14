# Testing Thinking Tokens

## Quick Test Guide

### Option 1: DeepSeek Direct (EASIEST)

```bash
# Use the DeepSeek config
export DEEPSEEK_API_KEY=your_key
uv run tyler chat --config tyler-chat-config-deepseek-direct.yaml

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
- `DEEPSEEK_API_KEY` environment variable
- Model: `deepseek/deepseek-chat`
- Free tier available!

### Option 2: W&B Inference (DeepSeek)

```bash
# Edit tyler-chat-config-wandb.yaml to add your team/project:
# base_url: "https://api.wandb.ai/api/v1/inference/YOUR-TEAM/YOUR-PROJECT"

# Set API key
export WANDB_API_KEY=your_key

# Run chat
uv run tyler chat --config tyler-chat-config-wandb.yaml
```

**Requirements:**
- W&B account with Inference enabled
- Update `base_url` in config with your team/project
- Uses DeepSeek-R1-0528 (optimized for reasoning)

### Option 3: Anthropic Claude

```bash
# Get API key from: https://console.anthropic.com/
export ANTHROPIC_API_KEY=sk-ant-your-actual-key-here  # Replace with your real key!

uv run tyler chat --config tyler-chat-config-anthropic.yaml
```

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable
- Model: `anthropic/claude-3-7-sonnet-20250219`

### Option 3: Debug Script

```bash
# See what's actually in the delta
uv run python test_thinking_debug.py
```

## Supported Models for Thinking Tokens

According to [LiteLLM docs](https://docs.litellm.ai/docs/reasoning_content):

✅ **Supported (via LiteLLM):**
- Deepseek (`deepseek/deepseek-chat`) ← EASIEST TO TEST
- Anthropic (`anthropic/claude-3-7-sonnet-20250219`)
- Bedrock (Anthropic + Deepseek)
- Vertex AI (Anthropic)
- OpenRouter
- XAI
- Google AI Studio
- Perplexity
- Mistral AI
- Groq

✅ **Supported (via W&B Inference):**
- `deepseek-ai/DeepSeek-R1-0528` (optimized for reasoning)
- `deepseek-ai/DeepSeek-V3-0324`
- `deepseek-ai/DeepSeek-V3.1`
- `openai/gpt-oss-20b` (reasoning capabilities)
- `openai/gpt-oss-120b` (high-reasoning)
- `Qwen/Qwen3-235B-A22B-Thinking-2507` (thinking-optimized)
- `zai-org/GLM-4.5` (controllable thinking modes)

❌ **NOT Supported (yet):**
- OpenAI Direct API (o1, o3, gpt-4.1 models)
  - Note: W&B Inference has OpenAI GPT-OSS models that DO support reasoning!

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

