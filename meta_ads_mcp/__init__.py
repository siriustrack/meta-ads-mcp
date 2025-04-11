"""Meta Ads MCP - Model Calling Protocol plugin for Meta Ads API."""

__version__ = "0.1.0"

# Import key functions to make them available at package level
from .meta_ads_generated import (
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
) 