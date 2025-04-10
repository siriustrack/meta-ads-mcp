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

@mcp_server.tool()
async def get_campaign_details(access_token: str, campaign_id: str) -> str:
    """Get detailed information about a specific campaign.
    
    Args:
        access_token: Meta API access token
        campaign_id: Meta Ads campaign ID
    """
    url = f"{META_ADS_API_BASE}/{campaign_id}"
    params = {
        "fields": "id,name,status,objective,special_ad_categories,created_time,start_time,stop_time,budget_remaining,daily_budget,lifetime_budget,bid_strategy,pacing_type,effective_status"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch campaign details."
    
    if "error" in data:
        return f"Error fetching campaign details: {data['error']}"
    
    # Format the detailed campaign information
    details = []
    for k, v in data.items():
        details.append(f"{k.replace('_', ' ').title()}: {v}")
    
    return "\n".join(details)

@mcp_server.tool()
async def get_adset_details(access_token: str, adset_id: str) -> str:
    """Get detailed information about a specific ad set.
    
    Args:
        access_token: Meta API access token
        adset_id: Meta Ads ad set ID
    """
    url = f"{META_ADS_API_BASE}/{adset_id}"
    params = {
        "fields": "id,name,status,daily_budget,lifetime_budget,bid_amount,optimization_goal,billing_event,targeting,start_time,end_time,created_time,campaign_id,effective_status,pacing_type,budget_remaining"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data:
        return "Unable to fetch ad set details."
    
    if "error" in data:
        return f"Error fetching ad set details: {data['error']}"
    
    # Handle targeting field specifically as it's a complex object
    targeting = data.get("targeting", {})
    if targeting:
        targeting_summary = []
        if "geo_locations" in targeting:
            geo = targeting["geo_locations"]
            countries = geo.get("countries", [])
            cities = geo.get("cities", [])
            if countries:
                targeting_summary.append(f"Countries: {', '.join(countries)}")
            if cities:
                city_names = [city.get("name", "Unknown") for city in cities]
                targeting_summary.append(f"Cities: {', '.join(city_names)}")
        
        if "age_min" in targeting or "age_max" in targeting:
            age_min = targeting.get("age_min", "N/A")
            age_max = targeting.get("age_max", "N/A")
            targeting_summary.append(f"Age Range: {age_min}-{age_max}")
            
        if "genders" in targeting:
            gender_map = {1: "Male", 2: "Female"}
            genders = targeting.get("genders", [])
            gender_names = [gender_map.get(g, str(g)) for g in genders]
            targeting_summary.append(f"Genders: {', '.join(gender_names)}")
            
        data["targeting_summary"] = "\n    " + "\n    ".join(targeting_summary)
        del data["targeting"]
    
    # Format the detailed ad set information
    details = []
    for k, v in data.items():
        if k == "targeting_summary":
            details.append(f"Targeting:\n{v}")
        else:
            details.append(f"{k.replace('_', ' ').title()}: {v}")
    
    return "\n".join(details)

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
        "time_range": f'{{"since":"{time_range}"}}',
        "fields": "impressions,clicks,ctr,spend,reach,frequency,cpm,cpp,cpc,actions,action_values,conversion_values,conversions,cost_per_action_type,cost_per_conversion,website_purchase_roas"
    }
    
    # Add parameters to the URL
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    data = await make_meta_request(full_url, access_token)
    
    if not data or "data" not in data:
        if "error" in data:
            return f"Error fetching insights: {data['error']}"
        return "Unable to fetch insights or no data available."
    
    if not data["data"]:
        return "No insights data available for the specified time range."
    
    insight = data["data"][0]  # Get the first insight
    
    # Format the basic metrics
    basic_metrics = [
        f"Impressions: {insight.get('impressions', 'N/A')}",
        f"Clicks: {insight.get('clicks', 'N/A')}",
        f"CTR: {insight.get('ctr', 'N/A')}",
        f"Spend: ${insight.get('spend', 'N/A')}",
        f"Reach: {insight.get('reach', 'N/A')}",
        f"Frequency: {insight.get('frequency', 'N/A')}",
        f"CPM: ${insight.get('cpm', 'N/A')}",
        f"CPC: ${insight.get('cpc', 'N/A')}"
    ]
    
    # Format actions and conversions if available
    actions = insight.get('actions', [])
    action_metrics = []
    if actions:
        action_metrics.append("Actions:")
        for action in actions:
            action_type = action.get('action_type', 'unknown')
            action_value = action.get('value', '0')
            action_metrics.append(f"  {action_type}: {action_value}")
    
    # Combine all metrics
    all_metrics = basic_metrics + action_metrics
    
    return f"Insights for time range: {time_range}\n" + "\n".join(all_metrics)

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
    
    if not ad_data or "creative" not in ad_data:
        if "error" in ad_data:
            return f"Error fetching ad creative ID: {ad_data['error']}"
        return "Unable to fetch ad creative information."
    
    creative_id = ad_data.get("creative", {}).get("id")
    if not creative_id:
        return "No creative ID found for this ad."
    
    # Now get the creative details
    creative_url = f"{META_ADS_API_BASE}/{creative_id}"
    creative_params = {
        "fields": "id,name,title,body,image_url,link_url,video_id,object_story_spec,thumbnail_url,asset_feed_spec,object_type,effective_object_story_id"
    }
    
    creative_param_str = "&".join(f"{k}={v}" for k, v in creative_params.items())
    creative_full_url = f"{creative_url}?{creative_param_str}"
    
    creative_data = await make_meta_request(creative_full_url, access_token)
    
    if not creative_data:
        return "Unable to fetch creative details."
    
    if "error" in creative_data:
        return f"Error fetching creative details: {creative_data['error']}"
    
    # Format the creative information
    formatted_data = []
    
    # Basic creative info
    formatted_data.append(f"Creative ID: {creative_data.get('id', 'N/A')}")
    formatted_data.append(f"Name: {creative_data.get('name', 'N/A')}")
    
    # Ad copy elements
    title = creative_data.get('title')
    if title:
        formatted_data.append(f"Title: {title}")
    
    body = creative_data.get('body')
    if body:
        formatted_data.append(f"Body: {body}")
    
    # Media URLs
    image_url = creative_data.get('image_url')
    if image_url:
        formatted_data.append(f"Image URL: {image_url}")
    
    link_url = creative_data.get('link_url')
    if link_url:
        formatted_data.append(f"Link URL: {link_url}")
    
    video_id = creative_data.get('video_id')
    if video_id:
        formatted_data.append(f"Video ID: {video_id}")
    
    thumbnail_url = creative_data.get('thumbnail_url')
    if thumbnail_url:
        formatted_data.append(f"Thumbnail URL: {thumbnail_url}")
    
    # Check for story spec (for complex creatives)
    story_spec = creative_data.get('object_story_spec')
    if story_spec:
        formatted_data.append("Story Specification:")
        
        # Page data
        page_id = story_spec.get('page_id')
        if page_id:
            formatted_data.append(f"  Page ID: {page_id}")
        
        # Link data
        link_data = story_spec.get('link_data')
        if link_data:
            formatted_data.append("  Link Data:")
            
            link_title = link_data.get('title')
            if link_title:
                formatted_data.append(f"    Title: {link_title}")
            
            link_description = link_data.get('description')
            if link_description:
                formatted_data.append(f"    Description: {link_description}")
            
            link_message = link_data.get('message')
            if link_message:
                formatted_data.append(f"    Message: {link_message}")
            
            link_url = link_data.get('link')
            if link_url:
                formatted_data.append(f"    URL: {link_url}")
            
            # Child attachments for carousel ads
            child_attachments = link_data.get('child_attachments')
            if child_attachments:
                formatted_data.append("    Carousel Cards:")
                for i, attachment in enumerate(child_attachments, 1):
                    formatted_data.append(f"      Card {i}:")
                    for key, value in attachment.items():
                        formatted_data.append(f"        {key}: {value}")
    
    return "\n".join(formatted_data)

@mcp_server.tool()
async def get_account_info(access_token: str, account_id: str) -> str:
    """Get information about a Meta Ads account including spending and performance.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
    """
    # Get basic account info
    url = f"{META_ADS_API_BASE}/{account_id}"
    params = {
        "fields": "id,name,account_status,currency,timezone_name,business_name,created_time,amount_spent,balance,min_daily_budget,owner"
    }
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{param_str}"
    
    account_data = await make_meta_request(full_url, access_token)
    
    if not account_data:
        return "Unable to fetch account information."
    
    if "error" in account_data:
        return f"Error fetching account information: {account_data['error']}"
    
    # Format basic account info
    account_status_map = {1: "Active", 2: "Disabled", 3: "Unsettled", 7: "Pending_risk_review", 8: "Pending_settlement", 9: "In_grace_period", 100: "Pending_closure", 101: "Closed", 201: "Any_active", 202: "Any_closed"}
    account_status = account_data.get("account_status")
    if account_status is not None:
        account_data["account_status"] = account_status_map.get(account_status, f"Unknown ({account_status})")
    
    basic_info = []
    for k, v in account_data.items():
        if k == "amount_spent":
            # Format amount as currency
            currency = account_data.get("currency", "USD")
            basic_info.append(f"Total Amount Spent: {v} {currency}")
        else:
            basic_info.append(f"{k.replace('_', ' ').title()}: {v}")
    
    # Get account insights
    insights_url = f"{META_ADS_API_BASE}/{account_id}/insights"
    insights_params = {
        "date_preset": "last_30_days",
        "fields": "spend,impressions,clicks,ctr,cpm,cpp,reach,frequency"
    }
    
    insights_param_str = "&".join(f"{k}={v}" for k, v in insights_params.items())
    insights_full_url = f"{insights_url}?{insights_param_str}"
    
    insights_data = await make_meta_request(insights_full_url, access_token)
    
    performance_info = []
    if insights_data and "data" in insights_data and insights_data["data"]:
        insights = insights_data["data"][0]
        performance_info.append("\nPerformance (Last 30 Days):")
        performance_info.append(f"Spend: {insights.get('spend', 'N/A')} {account_data.get('currency', 'USD')}")
        performance_info.append(f"Impressions: {insights.get('impressions', 'N/A')}")
        performance_info.append(f"Clicks: {insights.get('clicks', 'N/A')}")
        performance_info.append(f"CTR: {insights.get('ctr', 'N/A')}")
        performance_info.append(f"CPM: {insights.get('cpm', 'N/A')}")
        performance_info.append(f"Reach: {insights.get('reach', 'N/A')}")
        performance_info.append(f"Frequency: {insights.get('frequency', 'N/A')}")
        
        if "date_start" in insights and "date_stop" in insights:
            performance_info.append(f"Date Range: {insights.get('date_start')} to {insights.get('date_stop')}")
    
    # Combine all information
    return "\n".join(basic_info + performance_info)

if __name__ == "__main__":
    # Initialize and run the server
    mcp_server.run(transport='stdio')

