"""
Meta Ads MCP - Python Package

This package provides a Meta Ads Marketing Cloud Platform (MCP) integration
with the Claude LLM.
"""

from meta_ads_mcp.core.server import main

__version__ = "0.2.2"

__all__ = ["main"]

# Import key functions to make them available at package level
from .core import (
    get_ad_accounts,
    get_account_info,
    get_campaigns,
    get_campaign_details,
    create_campaign,
    get_adsets,
    get_adset_details,
    update_adset,
    get_ads,
    get_ad_details,
    get_ad_creatives,
    get_ad_image,
    get_insights,
    debug_image_download,
    save_ad_image_via_api,
    get_login_link,
    login_cli,
)

# Define a main function to be used as a package entry point
def entrypoint():
    """Main entry point for the package when invoked with uvx."""
    return main() 

# Re-export main for direct access
main = main 