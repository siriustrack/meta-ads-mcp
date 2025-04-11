# Meta Ads MCP

A [Model Calling Protocol (MCP)](https://github.com/anthropics/anthropic-tools) plugin for interacting with Meta Ads API.

## Features

- Seamless authentication with Meta's Graph API for desktop applications
- Automatic token caching across sessions
- Cross-platform support (Windows, macOS, Linux)
- Access to ad accounts, campaigns, ad sets, and ads
- Image download and analysis capabilities
- Performance insights

## Installation

### Using uv (recommended)

When using uv no specific installation is needed. We can use uvx to directly run meta-ads-mcp:

```bash
uvx meta-ads-mcp
```

If you want to install the package:

```bash
uv pip install meta-ads-mcp
```

For development (if you've cloned the repository):

```bash
# From the repository root
uv pip install -e .
```

### Using pip

Alternatively, you can install meta-ads-mcp via pip:

```bash
pip install meta-ads-mcp
```

After installation, you can run it as:

```bash
python -m meta_ads_mcp
```

## Configuration

### Usage with Claude in Cursor

Add this to your `claude_desktop_config.json` to integrate with Claude in Cursor:

```json
"mcpServers": {
  "meta-ads": {
    "command": "uvx",
    "args": ["meta-ads-mcp"]
  }
}
```

### 1. Create a Meta Developer App

Before using the MCP server, you'll need to set up a Meta Developer App:

1. Go to [Meta for Developers](https://developers.facebook.com/) and create a new app
2. Choose the "Consumer" app type
3. In your app settings, add the "Marketing API" product
4. Configure your app's OAuth redirect URI to include `http://localhost:8888/callback`
5. Note your App ID (Client ID) for use with the MCP

## Usage

### Command-line Usage

```bash
# Start the MCP server
uvx meta-ads-mcp

# Authenticate with Meta Ads
uvx meta-ads-mcp --login --app-id YOUR_APP_ID
```

### Authentication

The Meta Ads MCP uses the OAuth 2.0 flow designed for desktop apps. When authenticating, it will:

1. Start a local callback server on your machine
2. Open a browser window to authenticate with Meta
3. Ask you to authorize the app
4. Redirect back to the local server to extract and store the token securely

### Authentication Methods

There are two ways to authenticate with the Meta Ads API:

1. **LLM/MCP Interface Authentication** (Recommended)
   
   When using the Meta Ads MCP through an LLM interface (like Claude), simply use any Meta Ads function. If you're not authenticated, the system will automatically provide a clickable Markdown link to complete the authentication flow.

   ```
   [Click here to authenticate with Meta Ads API](https://www.facebook.com/dialog/oauth?...)
   ```

   Just click the link, complete the authorization in your browser, and the token will be automatically captured and stored.

2. **Command Line Authentication**

   You can authenticate directly from the command line:

   ```bash
   uvx meta-ads-mcp --login --app-id YOUR_APP_ID
   ```

### Token Caching

Tokens are cached in a platform-specific secure location:
- Windows: `%APPDATA%\meta-ads-mcp\token_cache.json`
- macOS: `~/Library/Application Support/meta-ads-mcp/token_cache.json`
- Linux: `~/.config/meta-ads-mcp/token_cache.json`

You do not need to provide your access token for each command; it will be automatically retrieved from the cache.

## Usage Examples

### Get Ad Accounts

```python
import asyncio
from meta_ads_mcp import get_ad_accounts

async def main():
    # Token will be automatically retrieved from cache
    accounts_json = await get_ad_accounts()
    print(accounts_json)

asyncio.run(main())
```

### Get Campaign Details

```python
import asyncio
from meta_ads_mcp import get_campaign_details

async def main():
    # Provide a campaign ID
    campaign_details = await get_campaign_details(campaign_id="123456789")
    print(campaign_details)

asyncio.run(main())
```

### Create a Campaign

```python
import asyncio
from meta_ads_mcp import create_campaign

async def main():
    result = await create_campaign(
        account_id="act_123456789",
        name="Test Campaign via MCP",
        objective="AWARENESS",
        status="PAUSED",
        daily_budget=1000  # $10.00
    )
    print(result)

asyncio.run(main())
```

## Environment Variables

You can set the following environment variables instead of passing them as arguments:

- `META_APP_ID`: Your Meta App ID (Client ID)

## Testing

### CLI Testing

Run the test script to verify authentication and basic functionality:

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID
```

Use the `--force-login` flag to force a new authentication even if a cached token exists:

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID --force-login
```

### LLM Interface Testing

When using the Meta Ads MCP with an LLM interface (like Claude):

1. Test authentication by calling the `get_login_link` tool
2. Verify account access by calling `get_ad_accounts`
3. Check specific account details with `get_account_info`

These functions will automatically handle authentication if needed and provide a clickable login link.

## Troubleshooting

### Authentication Issues

If you encounter authentication issues:

1. When using the LLM interface:
   - Use the `get_login_link` tool to generate a fresh authentication link
   - Ensure you click the link and complete the authorization flow in your browser
   - Check that the callback server is running properly (the tool will report this)

2. When using the command line:
   - Run with `--force-login` to get a fresh token: `uvx meta-ads-mcp --login --app-id YOUR_APP_ID --force-login`
   - Make sure the terminal has permissions to open a browser window

3. General authentication troubleshooting:
   - Check that your app is properly configured in the Meta Developers portal
   - Ensure your app has the necessary permissions (ads_management, ads_read, business_management)
   - Verify the app's redirect URI includes `http://localhost:8888/callback`
   - Try clearing the token cache (located in platform-specific directories listed in the Token Caching section)

### API Errors

If you receive errors from the Meta API:

1. Verify your app has the Marketing API product added
2. Ensure the user has appropriate permissions on the ad accounts
3. Check if there are rate limits or other restrictions on your app

## Versioning

You can check the current version of the package:

```python
import meta_ads_mcp
print(meta_ads_mcp.__version__)
``` 