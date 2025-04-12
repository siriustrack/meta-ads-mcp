"""
Meta Ads Generated - Backward compatibility wrapper

This file maintains backward compatibility with the previous monolithic version
by importing and re-exporting all functionality from the new modular structure.
"""

import os
import sys

# Add the current directory to the path so we can import the package
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and re-export all required functions and classes
from meta_ads_mcp.core.server import mcp_server
from meta_ads_mcp.core.auth import (
    auth_manager, needs_authentication, token_container,
    CallbackHandler, TokenInfo, AuthManager, start_callback_server,
    get_current_access_token, login
)
from meta_ads_mcp.core.api import (
    META_GRAPH_API_VERSION, META_GRAPH_API_BASE, USER_AGENT,
    GraphAPIError, make_api_request, meta_api_tool
)
from meta_ads_mcp.core.utils import (
    ad_creative_images, download_image, try_multiple_download_methods,
    create_resource_from_image
)
from meta_ads_mcp.core.accounts import (
    get_ad_accounts, get_account_info
)
from meta_ads_mcp.core.campaigns import (
    get_campaigns, get_campaign_details, create_campaign
)
from meta_ads_mcp.core.adsets import (
    get_adsets, get_adset_details, update_adset
)
from meta_ads_mcp.core.ads import (
    get_ads, get_ad_details, get_ad_creatives, get_ad_image
)
from meta_ads_mcp.core.insights import (
    get_insights, debug_image_download, save_ad_image_via_api
)
from meta_ads_mcp.core.authentication import (
    get_login_link
)
from meta_ads_mcp.core.resources import (
    list_resources, get_resource
)
from meta_ads_mcp.core.server import (
    login_cli, main
)

# Add the resource routes to maintain backward compatibility
mcp_server.resource(uri="meta-ads://resources")(list_resources)
mcp_server.resource(uri="meta-ads://images/{resource_id}")(get_resource)

# Initialize with default app ID, will be updated at runtime
META_APP_ID = os.environ.get("META_APP_ID", "YOUR_META_APP_ID")
if META_APP_ID != "YOUR_META_APP_ID":
    auth_manager.app_id = META_APP_ID

# This allows the script to be run directly
if __name__ == "__main__":
    main()