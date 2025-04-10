# Meta Ads MCP Server

A Model Context Protocol (MCP) server that provides tools for querying the Meta Ads API.

## Setup

1. Install dependencies:
```bash
# Using pip
pip install mcp>=1.2.0 httpx>=0.26.0

# Or using Poetry
poetry add mcp httpx

# Or using uv (recommended)
uv pip install mcp>=1.2.0 httpx>=0.26.0
```

2. Run the server:
```bash
# Direct execution (for development only)
python meta_ads.py

# Using uv (recommended)
uv run python meta_ads.py
```

Note: The server uses stdio transport, so it won't output anything when run directly. It's meant to be used with an MCP client like Claude for Desktop or Cursor.

## Tools

This MCP server provides the following tools:

1. `get_ads` - Retrieves ads from a Meta Ads account
2. `get_campaigns` - Retrieves campaigns from a Meta Ads account
3. `get_adsets` - Retrieves ad sets from a Meta Ads account

## Configuration with Claude for Desktop

To use this MCP server with Claude for Desktop, add the following to your Claude configuration file:

1. Open your Claude for Desktop configuration:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%AppData%\Claude\claude_desktop_config.json`

2. Add the server configuration:
```json
{
    "mcpServers": {
        "meta-ads": {
            "command": "uv",
            "args": [
                "--directory",
                "/ABSOLUTE/PATH/TO/PARENT/FOLDER",
                "run",
                "python",
                "meta_ads.py"
            ]
        }
    }
}
```

3. Replace `/ABSOLUTE/PATH/TO/PARENT/FOLDER` with the absolute path to the directory containing your `meta_ads.py` file. For example: `/Users/username/projects/meta-ads-mcp`

4. Restart Claude for Desktop.

## Configuration with Cursor

To use this MCP server with Cursor:

1. Edit the Cursor MCP configuration file:
   - macOS: `~/.cursor/mcp.json`
   - Windows: `%AppData%\Cursor\User\mcp.json` 

2. Add the server configuration:
```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER",
        "run",
        "python",
        "meta_ads.py"
      ],
      "description": "Meta Ads API MCP server",
      "autoconnect": true
    }
  }
}
```

3. Replace `/ABSOLUTE/PATH/TO/PARENT/FOLDER` with the absolute path to the directory containing your `meta_ads.py` file.

4. Restart Cursor or reconnect to the MCP server.

## Usage with Claude or Cursor

You can now ask about your Meta Ads account. Example prompts:
- "Show me the ads in my Meta Ads account with ID act_123456789"
- "What campaigns do I have running in my Meta Ads account?"
- "List the ad sets for my Meta account"

The assistant will use the provided access token and account ID to fetch the requested information.

## Important Notes

- You need a valid Meta Ads API access token to use these tools
- Your account ID should be in the format `act_XXXXXXXXX`
- The server will fetch a maximum of 10 items by default (configurable with the `limit` parameter)
- Using UV is recommended for better dependency management 