"""Ad Set-related functionality for Meta Ads API."""

import json
from typing import Optional, Dict, Any, List
from .api import meta_api_tool, make_api_request
from .accounts import get_ad_accounts
from .server import mcp_server
import asyncio
from .auth import start_callback_server, update_confirmation


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
        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,frequency_control_specs{event,interval_days,max_frequency}",
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
        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,attribution_spec,destination_type,promoted_object,pacing_type,budget_remaining,frequency_control_specs{event,interval_days,max_frequency}"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def update_adset(adset_id: str, frequency_control_specs: List[Dict[str, Any]] = None, bid_strategy: str = None, 
                        bid_amount: int = None, status: str = None, access_token: str = None) -> str:
    """
    Update an ad set with new settings including frequency caps.
    
    Args:
        adset_id: Meta Ads ad set ID
        frequency_control_specs: List of frequency control specifications 
                                 (e.g. [{"event": "IMPRESSIONS", "interval_days": 7, "max_frequency": 3}])
        bid_strategy: Bid strategy (e.g., 'LOWEST_COST_WITH_BID_CAP')
        bid_amount: Bid amount in account currency (in cents for USD)
        status: Update ad set status (ACTIVE, PAUSED, etc.)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not adset_id:
        return json.dumps({"error": "No ad set ID provided"}, indent=2)
    
    # Debug print
    print(f"DEBUG: update_adset called with adset_id: {adset_id}")
    print(f"DEBUG: frequency_control_specs: {frequency_control_specs}")
    
    # Build the changes dictionary directly from parameters
    changes = {}
    if bid_strategy is not None:
        changes['bid_strategy'] = bid_strategy
    if bid_amount is not None:
        changes['bid_amount'] = bid_amount
    if frequency_control_specs is not None:
        changes['frequency_control_specs'] = frequency_control_specs
    if status is not None:
        changes['status'] = status
    
    if not changes:
        return json.dumps({"error": "No update parameters provided"}, indent=2)
    
    print(f"DEBUG: Final changes to apply: {changes}")
    
    # Get current ad set details for comparison
    current_details_json = await get_adset_details(adset_id=adset_id, access_token=access_token)
    current_details = json.loads(current_details_json)
    
    # Start the callback server if not already running
    port = start_callback_server()
    
    # Generate confirmation URL with properly encoded parameters
    changes_json = json.dumps(changes)
    confirmation_url = f"http://localhost:{port}/confirm-update?adset_id={adset_id}&token={access_token}&changes={changes_json}"
    
    # Reset the update confirmation
    update_confirmation.clear()
    update_confirmation.update({"approved": False})
    
    # Return the confirmation link
    response = {
        "message": "Please confirm the ad set update",
        "confirmation_url": confirmation_url,
        "markdown_link": f"[Click here to confirm ad set update]({confirmation_url})",
        "current_details": current_details,
        "proposed_changes": changes,
        "instructions_for_llm": "You must present this link as clickable Markdown to the user using the markdown_link format provided.",
        "note": "After authenticating, the token will be automatically saved and your ad set will be updated. Refresh the browser page if it doesn't load immediately."
    }
    
    return json.dumps(response, indent=2) 