"""Meta Ads MCP - Model Calling Protocol plugin for Meta Ads API."""

__version__ = "0.2.0"

# Import key functions to make them available at package level
from .api import (
    get_ad_accounts,
    get_account_info,
    get_campaigns,
    get_campaign_details,
    create_campaign,
    get_adsets,
    get_adset_details,
    get_ads,
    get_ad_details,
    get_ad_creatives,
    get_ad_image,
    get_insights,
    get_login_link,
    login_cli,
    main,  # Import main function for entry point
)

# Define a main function to be used as a package entry point
def entrypoint():
    """Main entry point for the package when invoked with uvx."""
    return main() 