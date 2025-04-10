from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# = FastMCP("meta-ads")
# dont use mcp name because it conflicts with the mcp module
mcp_server = FastMCP("meta-ads")

# Constants
META_ADS_API_BASE = "https://graph.facebook.com/v20.0"
USER_AGENT = "meta-ads-mcp/1.0"

async def make_meta_request(url: str, access_token: str) -> dict[str, Any] | None:
    """Make a request to the Meta Ads API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
    }
    params = {
        "access_token": access_token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

def format_ad(ad: dict) -> str:
    """Format an ad into a readable string."""
    return f"""
Ad ID: {ad.get('id', 'Unknown')}
Name: {ad.get('name', 'Unknown')}
Status: {ad.get('status', 'Unknown')}
Created Time: {ad.get('created_time', 'Unknown')}
"""

def format_campaign(campaign: dict) -> str:
    """Format a campaign into a readable string."""
    return f"""
Campaign ID: {campaign.get('id', 'Unknown')}
Name: {campaign.get('name', 'Unknown')}
Status: {campaign.get('status', 'Unknown')}
Objective: {campaign.get('objective', 'Unknown')}
"""

def format_adset(adset: dict) -> str:
    """Format an adset into a readable string."""
    return f"""
AdSet ID: {adset.get('id', 'Unknown')}
Name: {adset.get('name', 'Unknown')}
Status: {adset.get('status', 'Unknown')}
Daily Budget: {adset.get('daily_budget', 'Unknown')}
"""

@mcp_server.tool()
async def get_ads(access_token: str, account_id: str, limit: int = 10) -> str:
    """Get ads for a Meta Ads account.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ads to return (default: 10)
    """
    url = f"{META_ADS_API_BASE}/{account_id}/ads"
    params = {
        "limit": limit,
        "fields": "id,name,status,created_time"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data or "data" not in data:
        if "error" in data:
            return f"Error fetching ads: {data['error']}"
        return "Unable to fetch ads or no ads found."
    
    if not data["data"]:
        return "No ads found for this account."
    
    ads = [format_ad(ad) for ad in data["data"]]
    return "\n---\n".join(ads)

@mcp_server.tool()
async def get_campaigns(access_token: str, account_id: str, limit: int = 10) -> str:
    """Get campaigns for a Meta Ads account.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of campaigns to return (default: 10)
    """
    url = f"{META_ADS_API_BASE}/{account_id}/campaigns"
    params = {
        "limit": limit,
        "fields": "id,name,status,objective"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data or "data" not in data:
        if "error" in data:
            return f"Error fetching campaigns: {data['error']}"
        return "Unable to fetch campaigns or no campaigns found."
    
    if not data["data"]:
        return "No campaigns found for this account."
    
    campaigns = [format_campaign(campaign) for campaign in data["data"]]
    return "\n---\n".join(campaigns)

@mcp_server.tool()
async def get_adsets(access_token: str, account_id: str, limit: int = 10) -> str:
    """Get ad sets for a Meta Ads account.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ad sets to return (default: 10)
    """
    url = f"{META_ADS_API_BASE}/{account_id}/adsets"
    params = {
        "limit": limit,
        "fields": "id,name,status,daily_budget"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data or "data" not in data:
        if "error" in data:
            return f"Error fetching ad sets: {data['error']}"
        return "Unable to fetch ad sets or no ad sets found."
    
    if not data["data"]:
        return "No ad sets found for this account."
    
    adsets = [format_adset(adset) for adset in data["data"]]
    return "\n---\n".join(adsets)

if __name__ == "__main__":
    # Initialize and run the server
    mcp_server.run(transport='stdio')

