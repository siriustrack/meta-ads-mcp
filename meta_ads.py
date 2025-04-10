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
    
    # Print the URL we're calling for debugging (mask the token for security)
    masked_url = url.replace(access_token, "***TOKEN***") if access_token in url else url
    print(f"Making request to: {masked_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_info = {}
            try:
                error_info = response.json()
            except:
                error_info = {"status_code": e.response.status_code, "text": e.response.text}
            
            print(f"HTTP Error: {e.response.status_code} - {error_info}")
            return {"error": f"HTTP Error: {e.response.status_code}", "details": error_info}
        except Exception as e:
            print(f"Request Error: {str(e)}")
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
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch ads."
    
    if "error" in data:
        return f"Error fetching ads: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

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
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch campaigns."
    
    if "error" in data:
        return f"Error fetching campaigns: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

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
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch ad sets."
    
    if "error" in data:
        return f"Error fetching ad sets: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_campaign_details(access_token: str, campaign_id: str) -> str:
    """Get detailed information about a specific campaign.
    
    Args:
        access_token: Meta API access token
        campaign_id: Meta Ads campaign ID
    """
    url = f"{META_ADS_API_BASE}/{campaign_id}"
    
    data = await make_meta_request(url, access_token)
    
    if not data:
        return "Unable to fetch campaign details."
    
    if "error" in data:
        return f"Error fetching campaign details: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_adset_details(access_token: str, adset_id: str) -> str:
    """Get detailed information about a specific ad set.
    
    Args:
        access_token: Meta API access token
        adset_id: Meta Ads ad set ID
    """
    url = f"{META_ADS_API_BASE}/{adset_id}"
    
    data = await make_meta_request(url, access_token)
    
    if not data:
        return "Unable to fetch ad set details."
    
    if "error" in data:
        return f"Error fetching ad set details: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_insights(access_token: str, object_id: str, time_range: str = "last_30_days") -> str:
    """Get performance insights for a campaign, ad set, or ad.
    
    Args:
        access_token: Meta API access token
        object_id: ID of the campaign, ad set, or ad
        time_range: Time range for insights (default: last_30_days, options: today, yesterday, last_7_days, last_30_days)
    """
    url = f"{META_ADS_API_BASE}/{object_id}/insights"
    params = {
        "date_preset": time_range,
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch insights."
    
    if "error" in data:
        return f"Error fetching insights: {data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_ad_creatives(access_token: str, ad_id: str) -> str:
    """Get creative details for a specific ad.
    
    Args:
        access_token: Meta API access token
        ad_id: Meta Ads ad ID
    """
    # First, get the creative ID from the ad
    url = f"{META_ADS_API_BASE}/{ad_id}"
    params = {
        "fields": "creative"
    }
    
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    ad_data = await make_meta_request(full_url, access_token)
    
    if not ad_data:
        return "Unable to fetch ad creative information."
    
    if "error" in ad_data:
        return f"Error fetching ad creative ID: {ad_data['error']}"
    
    if "creative" not in ad_data:
        # Return the raw ad data without creative
        import json
        return json.dumps(ad_data, indent=2)
    
    creative_id = ad_data.get("creative", {}).get("id")
    if not creative_id:
        import json
        return json.dumps(ad_data, indent=2)
    
    # Now get the creative details
    creative_url = f"{META_ADS_API_BASE}/{creative_id}"
    
    creative_data = await make_meta_request(creative_url, access_token)
    
    if not creative_data:
        return "Unable to fetch creative details."
    
    if "error" in creative_data:
        return f"Error fetching creative details: {creative_data['error']}"
    
    # Return the raw data without parsing
    import json
    return json.dumps(creative_data, indent=2)

@mcp_server.tool()
async def get_account_info(access_token: str, account_id: str) -> str:
    """Get information about a Meta Ads account including spending and performance.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
    """
    # Get basic account info
    url = f"{META_ADS_API_BASE}/{account_id}"
    
    account_data = await make_meta_request(url, access_token)
    
    if not account_data:
        return "Unable to fetch account information."
    
    if "error" in account_data:
        return f"Error fetching account information: {account_data['error']}"
    
    # Get account insights
    insights_url = f"{META_ADS_API_BASE}/{account_id}/insights"
    insights_params = {
        "date_preset": "last_30_days",
    }
    
    insights_param_str = "&".join(f"{k}={v}" for k, v in insights_params.items())
    insights_full_url = f"{insights_url}?{insights_param_str}"
    
    insights_data = await make_meta_request(insights_full_url, access_token)
    
    # Combine both sets of data
    combined_data = {
        "account_data": account_data,
        "insights_data": insights_data
    }
    
    # Return the raw data without parsing
    import json
    return json.dumps(combined_data, indent=2)

if __name__ == "__main__":
    # Initialize and run the server
    mcp_server.run(transport='stdio')

