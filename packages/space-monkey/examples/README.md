# Running the Space Monkey Example

## Quick Start

1. **Set up your Slack App**
   - Go to https://api.slack.com/apps
   - Create a new app or use an existing one
   - Enable Socket Mode
   - Add bot scopes: `chat:write`, `app_mentions:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`
   - Install the app to your workspace

2. **Get your tokens**
   - Bot Token: Found in OAuth & Permissions (starts with `xoxb-`)
   - App Token: Found in Basic Information > App-Level Tokens (starts with `xapp-`)

3. **Create `.env` file** in the parent directory:
   ```bash
   # Copy the example file
   cp ../env.example ../.env
   
   # Then edit with your tokens:
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_APP_TOKEN=xapp-your-app-token
   ```

4. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -e .
   ```

5. **Run the example**:
   ```bash
   # Basic example (minimal setup)
   python basic.py
   
   # Or the full example with more features
   python full_example.py
   ```

6. **Test in Slack**:
   - Invite your bot to a channel: `/invite @YourBotName`
   - Mention your bot: `@YourBotName Hello!`

## What's the difference?

- `basic.py` - Bare minimum to get a bot running
- `full_example.py` - Full example with error handling and database example

## Troubleshooting

- **Bot not responding?** Check that Socket Mode is enabled in your Slack app settings
- **Permission errors?** Make sure you've added all the required bot scopes
- **Connection errors?** Verify your tokens are correct in the `.env` file 