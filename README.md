# Meta Ads MCP

A [Model Calling Protocol (MCP)](https://github.com/anthropics/anthropic-tools) plugin for interacting with Meta Ads API.

## Features

- Seamless authentication with Meta's Graph API for desktop applications
- Automatic token caching across sessions
- Cross-platform support (Windows, macOS, Linux)
- Access to ad accounts, campaigns, ad sets, and ads
- Image download and analysis capabilities
- Performance insights

## Setup

### 1. Create a Meta Developer App

1. Go to [Meta for Developers](https://developers.facebook.com/) and create a new app
2. Choose the "Consumer" app type
3. In your app settings, add the "Marketing API" product
4. Configure your app's OAuth redirect URI to include `http://localhost:8888/callback`
5. Note your App ID (Client ID) for use with the MCP

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## Authentication

The Meta Ads MCP uses the OAuth 2.0 flow designed for desktop apps. The first time you use it, it will:

1. Open a browser window to authenticate with Meta
2. Ask you to authorize the app
3. Redirect back to a local server running on your machine
4. Extract and store the token securely

### Initial Authentication

You can trigger the authentication process in two ways:

1. Using the dedicated login command:

```bash
python meta_ads_generated.py --login --app-id YOUR_APP_ID
```

2. Or by running any command which will automatically prompt for authentication if needed:

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID
```

### Token Caching

Tokens are cached in a platform-specific secure location:
- Windows: `%APPDATA%\meta-ads-mcp\token_cache.json`
- macOS: `~/Library/Application Support/meta-ads-mcp/token_cache.json`
- Linux: `~/.config/meta-ads-mcp/token_cache.json`

You do not need to provide your access token for each command; it will be automatically retrieved from the cache.

## Usage Examples

### Test Authentication

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID
```

### Get Ad Accounts

```python
import asyncio
from meta_ads_generated import get_ad_accounts

async def main():
    # Token will be automatically retrieved from cache
    accounts_json = await get_ad_accounts()
    print(accounts_json)

asyncio.run(main())
```

### Get Campaign Details

```python
import asyncio
from meta_ads_generated import get_campaign_details

async def main():
    # Provide a campaign ID
    campaign_details = await get_campaign_details(campaign_id="123456789")
    print(campaign_details)

asyncio.run(main())
```

### Create a Campaign

```python
import asyncio
from meta_ads_generated import create_campaign

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

Run the test script to verify authentication and basic functionality:

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID
```

Use the `--force-login` flag to force a new authentication even if a cached token exists:

```bash
python test_meta_ads_auth.py --app-id YOUR_APP_ID --force-login
```

## Troubleshooting

### Authentication Issues

If you encounter authentication issues:

1. Run with `--force-login` to get a fresh token
2. Check that your app is properly configured in the Meta Developers portal
3. Ensure your app has the necessary permissions (ads_management, ads_read)
4. Check the app's redirect URI includes http://localhost:8888/callback

### API Errors

If you receive errors from the Meta API:

1. Verify your app has the Marketing API product added
2. Ensure the user has appropriate permissions on the ad accounts
3. Check if there are rate limits or other restrictions on your app

# Meta Ads MCP Wrapper

This repository contains a wrapper for the Meta Ads Marketing API Client Protocol (MCP) implementation.

## Files

- `meta_ads_generated.py`: The main MCP implementation for Meta Ads API
- `meta_ads_watch.py`: A wrapper script that monitors for file changes and automatically restarts the MCP server

## Requirements

- Python 3.6+
- [uv](https://github.com/astral-sh/uv) - A Python package installer and resolver
- Required Python packages (installed via uv)

## Usage

### Running with Auto-Reload

To run the Meta Ads MCP server with auto-reload capability:

```bash
./meta_ads_watch.py
```

This will:
1. Start the MCP server using `uv run python meta_ads_generated.py`
2. Monitor the main script file for changes
3. Automatically restart the server when changes are detected
4. Preserve stdin/stdout connections to ensure MCP clients stay connected

### Authentication

You can pass authentication arguments to the underlying script:

```bash
./meta_ads_watch.py --login --app-id YOUR_APP_ID
```

### Development

When developing, simply edit the `meta_ads_generated.py` file. The wrapper will detect changes and restart the server automatically while preserving the connections to any MCP clients.

## How It Works

The wrapper script:
- Uses a separate thread to monitor file changes
- Properly handles process termination and signal forwarding
- Ensures stdin/stdout are properly passed to the child process
- Writes status messages to stderr to avoid interfering with the MCP protocol 