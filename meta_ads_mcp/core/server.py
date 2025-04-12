"""MCP server configuration for Meta Ads API."""

from mcp.server.fastmcp import FastMCP
import argparse
import os
import sys
from .auth import login as login_auth
from .resources import list_resources, get_resource
from .utils import logger

# Initialize FastMCP server
mcp_server = FastMCP("meta-ads", use_consistent_tool_format=True)

# Register resource URIs
mcp_server.resource(uri="meta-ads://resources")(list_resources)
mcp_server.resource(uri="meta-ads://images/{resource_id}")(get_resource)


def login_cli():
    """
    Command-line function to authenticate with Meta
    """
    logger.info("Starting Meta Ads CLI authentication flow")
    print("Starting Meta Ads CLI authentication flow...")
    
    # Call the common login function
    login_auth()


def main():
    """Main entry point for the package"""
    # Log startup information
    logger.info("Meta Ads MCP server starting")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Args: {sys.argv}")
    
    # Initialize argument parser
    parser = argparse.ArgumentParser(description="Meta Ads MCP Server")
    parser.add_argument("--login", action="store_true", help="Authenticate with Meta and store the token")
    parser.add_argument("--app-id", type=str, help="Meta App ID (Client ID) for authentication")
    parser.add_argument("--version", action="store_true", help="Show the version of the package")
    
    args = parser.parse_args()
    logger.info(f"Parsed args: login={args.login}, app_id={args.app_id}, version={args.version}")
    
    # Update app ID if provided as environment variable or command line arg
    from .auth import auth_manager, meta_config
    
    # Check environment variable first (early init)
    env_app_id = os.environ.get("META_APP_ID")
    if env_app_id:
        logger.info(f"Found META_APP_ID in environment: {env_app_id}")
    else:
        logger.warning("META_APP_ID not found in environment variables")
    
    # Command line takes precedence
    if args.app_id:
        logger.info(f"Setting app_id from command line: {args.app_id}")
        auth_manager.app_id = args.app_id
        meta_config.set_app_id(args.app_id)
    elif env_app_id:
        logger.info(f"Setting app_id from environment: {env_app_id}")
        auth_manager.app_id = env_app_id
        meta_config.set_app_id(env_app_id)
    
    # Log the final app ID that will be used
    logger.info(f"Final app_id from meta_config: {meta_config.get_app_id()}")
    logger.info(f"Final app_id from auth_manager: {auth_manager.app_id}")
    logger.info(f"ENV META_APP_ID: {os.environ.get('META_APP_ID')}")
    
    # Show version if requested
    if args.version:
        from meta_ads_mcp import __version__
        logger.info(f"Displaying version: {__version__}")
        print(f"Meta Ads MCP v{__version__}")
        return 0
    
    # Handle login command
    if args.login:
        login_cli()
    else:
        # Initialize and run the server
        logger.info("Starting MCP server with stdio transport")
        mcp_server.run(transport='stdio') 