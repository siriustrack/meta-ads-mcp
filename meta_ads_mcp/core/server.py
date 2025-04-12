"""MCP server configuration for Meta Ads API."""

from mcp.server.fastmcp import FastMCP
import argparse
import os
from .auth import login as login_auth
from .resources import list_resources, get_resource

# Initialize FastMCP server
mcp_server = FastMCP("meta-ads", use_consistent_tool_format=True)

# Register resource URIs
mcp_server.resource(uri="meta-ads://resources")(list_resources)
mcp_server.resource(uri="meta-ads://images/{resource_id}")(get_resource)


def login_cli():
    """
    Command-line function to authenticate with Meta
    """
    print("Starting Meta Ads CLI authentication flow...")
    
    # Call the common login function
    login_auth()


def main():
    """Main entry point for the package"""
    parser = argparse.ArgumentParser(description="Meta Ads MCP Server")
    parser.add_argument("--login", action="store_true", help="Authenticate with Meta and store the token")
    parser.add_argument("--app-id", type=str, help="Meta App ID (Client ID) for authentication")
    parser.add_argument("--version", action="store_true", help="Show the version of the package")
    
    args = parser.parse_args()
    
    # Update app ID if provided as environment variable or command line arg
    from .auth import auth_manager
    if args.app_id:
        auth_manager.app_id = args.app_id
    elif os.environ.get("META_APP_ID"):
        auth_manager.app_id = os.environ.get("META_APP_ID")
    
    # Show version if requested
    if args.version:
        from meta_ads_mcp import __version__
        print(f"Meta Ads MCP v{__version__}")
        return 0
    
    # Handle login command
    if args.login:
        login_cli()
    else:
        # Initialize and run the server
        mcp_server.run(transport='stdio') 