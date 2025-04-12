"""Ad Set-related functionality for Meta Ads API."""

import json
from typing import Optional, Dict, Any, List
from .api import meta_api_tool, make_api_request
from .accounts import get_ad_accounts
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_adsets(access_token: str = None, account_id: str = None, limit: int = 10, campaign_id: str = "") -> str:
    """
    Get ad sets for a Meta Ads account with optional filtering by campaign.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ad sets to return (default: 10)
        campaign_id: Optional campaign ID to filter by
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts("me", json.dumps({"limit": 1}), access_token)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
    endpoint = f"{account_id}/adsets"
    params = {
        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time",
        "limit": limit
    }
    
    if campaign_id:
        params["campaign_id"] = campaign_id
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_adset_details(access_token: str = None, adset_id: str = None) -> str:
    """
    Get detailed information about a specific ad set.
    
    Args:
        adset_id: Meta Ads ad set ID (required)
        access_token: Meta API access token (optional - will use cached token if not provided)
    
    Example:
        To call this function through MCP, pass the adset_id as the first argument:
        {
            "args": "YOUR_ADSET_ID"
        }
    """
    if not adset_id:
        return json.dumps({"error": "No ad set ID provided"}, indent=2)
    
    endpoint = f"{adset_id}"
    params = {
        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,attribution_spec,destination_type,promoted_object,pacing_type,budget_remaining"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def update_adset(access_token: str = None, adset_id: str = None, 
                       bid_strategy: Optional[str] = None, 
                       bid_amount: Optional[int] = None,
                       frequency_control_specs: Optional[List[Dict[str, Any]]] = None,
                       status: Optional[str] = None) -> str:
    """
    Update an existing ad set with new settings including frequency caps.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        adset_id: Meta Ads ad set ID
        bid_strategy: Bid strategy (e.g., 'LOWEST_COST_WITH_BID_CAP')
        bid_amount: Bid amount in your account's currency (in cents for USD)
        frequency_control_specs: List of frequency control specifications. Each spec should have:
            - event: Type of event (e.g., 'IMPRESSIONS')
            - interval_days: Number of days for the frequency cap
            - max_frequency: Maximum number of times to show the ad
        status: Update ad set status (ACTIVE, PAUSED, etc.)
    """
    if not adset_id:
        return json.dumps({"error": "No ad set ID provided"}, indent=2)
    
    endpoint = f"{adset_id}"
    params = {}
    
    if bid_strategy:
        params["bid_strategy"] = bid_strategy
    
    if bid_amount is not None:
        params["bid_amount"] = bid_amount
    
    if frequency_control_specs:
        params["frequency_control_specs"] = frequency_control_specs
    
    if status:
        params["status"] = status
    
    if not params:
        return json.dumps({"error": "No update parameters provided"}, indent=2)
    
    data = await make_api_request(endpoint, access_token, params, method="POST")
    
    return json.dumps(data, indent=2) 