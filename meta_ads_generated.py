from typing import Any, Dict, List, Optional
import httpx
import json
import os
import base64
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp_server = FastMCP("meta-ads-generated")

# Constants
META_GRAPH_API_VERSION = "v20.0"
META_GRAPH_API_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"
USER_AGENT = "meta-ads-mcp/1.0"

# Global store for ad creative images
ad_creative_images = {}

class GraphAPIError(Exception):
    """Exception raised for errors from the Graph API."""
    def __init__(self, error_data: Dict[str, Any]):
        self.error_data = error_data
        self.message = error_data.get('message', 'Unknown Graph API error')
        super().__init__(self.message)

async def make_api_request(
    endpoint: str,
    access_token: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET"
) -> Dict[str, Any]:
    """
    Make a request to the Meta Graph API.
    
    Args:
        endpoint: API endpoint path (without base URL)
        access_token: Meta API access token
        params: Additional query parameters
        method: HTTP method (GET, POST, DELETE)
    
    Returns:
        API response as a dictionary
    """
    url = f"{META_GRAPH_API_BASE}/{endpoint}"
    
    headers = {
        "User-Agent": USER_AGENT,
    }
    
    request_params = params or {}
    request_params["access_token"] = access_token
    
    # Print the request details (masking the token for security)
    masked_params = {k: "***TOKEN***" if k == "access_token" else v for k, v in request_params.items()}
    print(f"Making {method} request to: {url}")
    print(f"Params: {masked_params}")
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(url, params=request_params, headers=headers, timeout=30.0)
            elif method == "POST":
                response = await client.post(url, json=request_params, headers=headers, timeout=30.0)
            elif method == "DELETE":
                response = await client.delete(url, params=request_params, headers=headers, timeout=30.0)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPStatusError as e:
            error_info = {}
            try:
                error_info = e.response.json()
            except:
                error_info = {"status_code": e.response.status_code, "text": e.response.text}
            
            print(f"HTTP Error: {e.response.status_code} - {error_info}")
            return {"error": f"HTTP Error: {e.response.status_code}", "details": error_info}
        
        except Exception as e:
            print(f"Request Error: {str(e)}")
            return {"error": str(e)}

async def download_image(url: str) -> Optional[bytes]:
    """
    Download an image from a URL.
    
    Args:
        url: Image URL
        
    Returns:
        Image data as bytes if successful, None otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content
    except Exception as e:
        print(f"Error downloading image: {str(e)}")
        return None

#
# Ad Account Endpoints
#

@mcp_server.tool()
async def get_ad_accounts(access_token: str, user_id: str = "me", limit: int = 10) -> str:
    """
    Get ad accounts accessible by a user.
    
    Args:
        access_token: Meta API access token
        user_id: Meta user ID or "me" for the current user
        limit: Maximum number of accounts to return (default: 10)
    """
    endpoint = f"{user_id}/adaccounts"
    params = {
        "fields": "id,name,account_id,account_status,amount_spent,balance,currency,age,business_city,business_country_code",
        "limit": limit
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_account_info(access_token: str, account_id: str) -> str:
    """
    Get detailed information about a specific ad account.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
    """
    # Ensure account_id has the 'act_' prefix for API compatibility
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    
    endpoint = f"{account_id}"
    params = {
        "fields": "id,name,account_id,account_status,amount_spent,balance,currency,age,funding_source_details,business_city,business_country_code,timezone_name,owner"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

#
# Campaign Endpoints
#

@mcp_server.tool()
async def get_campaigns(access_token: str, account_id: str, limit: int = 10, status_filter: str = "") -> str:
    """
    Get campaigns for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of campaigns to return (default: 10)
        status_filter: Filter by status (empty for all, or 'ACTIVE', 'PAUSED', etc.)
    """
    endpoint = f"{account_id}/campaigns"
    params = {
        "fields": "id,name,objective,status,daily_budget,lifetime_budget,buying_type,start_time,stop_time,created_time,updated_time,bid_strategy",
        "limit": limit
    }
    
    if status_filter:
        params["effective_status"] = [status_filter]
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_campaign_details(access_token: str, campaign_id: str) -> str:
    """
    Get detailed information about a specific campaign.
    
    Args:
        access_token: Meta API access token
        campaign_id: Meta Ads campaign ID
    """
    endpoint = f"{campaign_id}"
    params = {
        "fields": "id,name,objective,status,daily_budget,lifetime_budget,buying_type,start_time,stop_time,created_time,updated_time,bid_strategy,special_ad_categories,special_ad_category_country,budget_remaining,configured_status"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def create_campaign(
    access_token: str,
    account_id: str,
    name: str,
    objective: str,
    status: str = "PAUSED",
    special_ad_categories: List[str] = None,
    daily_budget: Optional[int] = None,
    lifetime_budget: Optional[int] = None
) -> str:
    """
    Create a new campaign in a Meta Ads account.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Campaign name
        objective: Campaign objective (AWARENESS, TRAFFIC, ENGAGEMENT, etc.)
        status: Initial campaign status (default: PAUSED)
        special_ad_categories: List of special ad categories if applicable
        daily_budget: Daily budget in account currency (in cents)
        lifetime_budget: Lifetime budget in account currency (in cents)
    """
    endpoint = f"{account_id}/campaigns"
    
    params = {
        "name": name,
        "objective": objective,
        "status": status,
    }
    
    if special_ad_categories:
        params["special_ad_categories"] = special_ad_categories
    
    if daily_budget:
        params["daily_budget"] = daily_budget
    
    if lifetime_budget:
        params["lifetime_budget"] = lifetime_budget
    
    data = await make_api_request(endpoint, access_token, params, method="POST")
    
    return json.dumps(data, indent=2)

#
# Ad Set Endpoints
#

@mcp_server.tool()
async def get_adsets(access_token: str, account_id: str, limit: int = 10, campaign_id: str = "") -> str:
    """
    Get ad sets for a Meta Ads account with optional filtering by campaign.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ad sets to return (default: 10)
        campaign_id: Optional campaign ID to filter by
    """
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
async def get_adset_details(access_token: str, adset_id: str) -> str:
    """
    Get detailed information about a specific ad set.
    
    Args:
        access_token: Meta API access token
        adset_id: Meta Ads ad set ID
    """
    endpoint = f"{adset_id}"
    params = {
        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,attribution_spec,destination_type,promoted_object,pacing_type,budget_remaining"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

#
# Ad Endpoints
#

@mcp_server.tool()
async def get_ads(
    access_token: str,
    account_id: str,
    limit: int = 10,
    campaign_id: str = "",
    adset_id: str = ""
) -> str:
    """
    Get ads for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ads to return (default: 10)
        campaign_id: Optional campaign ID to filter by
        adset_id: Optional ad set ID to filter by
    """
    endpoint = f"{account_id}/ads"
    params = {
        "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs",
        "limit": limit
    }
    
    if campaign_id:
        params["campaign_id"] = campaign_id
    
    if adset_id:
        params["adset_id"] = adset_id
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_ad_details(access_token: str, ad_id: str) -> str:
    """
    Get detailed information about a specific ad.
    
    Args:
        access_token: Meta API access token
        ad_id: Meta Ads ad ID
    """
    endpoint = f"{ad_id}"
    params = {
        "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs,preview_shareable_link"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
async def get_ad_creatives(access_token: str, ad_id: str) -> str:
    """
    Get creative details for a specific ad.
    
    Args:
        access_token: Meta API access token
        ad_id: Meta Ads ad ID
    """
    # First, get the creative ID from the ad
    endpoint = f"{ad_id}"
    params = {
        "fields": "creative"
    }
    
    ad_data = await make_api_request(endpoint, access_token, params)
    
    if "error" in ad_data:
        return json.dumps(ad_data, indent=2)
    
    if "creative" not in ad_data:
        return json.dumps({"error": "No creative found for this ad"}, indent=2)
    
    creative_id = ad_data.get("creative", {}).get("id")
    if not creative_id:
        return json.dumps({"error": "Creative ID not found", "ad_data": ad_data}, indent=2)
    
    # Now get the creative details with essential fields
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,title,body,image_url,object_story_spec,url_tags,link_url,thumbnail_url,image_hash,asset_feed_spec,object_type"
    }
    
    creative_data = await make_api_request(creative_endpoint, access_token, creative_params)
    
    # Try to get full-size images in different ways:
    
    # 1. First approach: Get ad images directly using the adimages endpoint
    if "image_hash" in creative_data:
        image_hash = creative_data.get("image_hash")
        image_endpoint = f"act_{ad_data.get('account_id', '')}/adimages"
        image_params = {
            "hashes": [image_hash]
        }
        image_data = await make_api_request(image_endpoint, access_token, image_params)
        if "data" in image_data and len(image_data["data"]) > 0:
            creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # 2. For creatives with object_story_spec
    if "object_story_spec" in creative_data:
        spec = creative_data.get("object_story_spec", {})
        
        # For link ads
        if "link_data" in spec:
            link_data = spec.get("link_data", {})
            # If there's an explicit image_url, use it
            if "image_url" in link_data:
                creative_data["full_image_url"] = link_data.get("image_url")
            # If there's an image_hash, try to get the full image
            elif "image_hash" in link_data:
                image_hash = link_data.get("image_hash")
                account_id = ad_data.get('account_id', '')
                if not account_id:
                    # Try to get account ID from ad ID
                    ad_details_endpoint = f"{ad_id}"
                    ad_details_params = {
                        "fields": "account_id"
                    }
                    ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                    account_id = ad_details.get('account_id', '')
                
                if account_id:
                    image_endpoint = f"act_{account_id}/adimages"
                    image_params = {
                        "hashes": [image_hash]
                    }
                    image_data = await make_api_request(image_endpoint, access_token, image_params)
                    if "data" in image_data and len(image_data["data"]) > 0:
                        creative_data["full_image_url"] = image_data["data"][0].get("url")
        
        # For photo ads
        if "photo_data" in spec:
            photo_data = spec.get("photo_data", {})
            if "image_hash" in photo_data:
                image_hash = photo_data.get("image_hash")
                account_id = ad_data.get('account_id', '')
                if not account_id:
                    # Try to get account ID from ad ID
                    ad_details_endpoint = f"{ad_id}"
                    ad_details_params = {
                        "fields": "account_id"
                    }
                    ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                    account_id = ad_details.get('account_id', '')
                
                if account_id:
                    image_endpoint = f"act_{account_id}/adimages"
                    image_params = {
                        "hashes": [image_hash]
                    }
                    image_data = await make_api_request(image_endpoint, access_token, image_params)
                    if "data" in image_data and len(image_data["data"]) > 0:
                        creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # 3. If there's an asset_feed_spec, try to get images from there
    if "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"]:
        images = creative_data["asset_feed_spec"]["images"]
        if images and len(images) > 0 and "hash" in images[0]:
            image_hash = images[0]["hash"]
            account_id = ad_data.get('account_id', '')
            if not account_id:
                # Try to get account ID
                ad_details_endpoint = f"{ad_id}"
                ad_details_params = {
                    "fields": "account_id"
                }
                ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                account_id = ad_details.get('account_id', '')
            
            if account_id:
                image_endpoint = f"act_{account_id}/adimages"
                image_params = {
                    "hashes": [image_hash]
                }
                image_data = await make_api_request(image_endpoint, access_token, image_params)
                if "data" in image_data and len(image_data["data"]) > 0:
                    creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # If we have a thumbnail_url but no full_image_url, let's attempt to convert the thumbnail URL to full size
    if "thumbnail_url" in creative_data and "full_image_url" not in creative_data:
        thumbnail_url = creative_data["thumbnail_url"]
        # Try to convert the URL to get higher resolution by removing size parameters
        if "p64x64" in thumbnail_url:
            full_url = thumbnail_url.replace("p64x64", "p1080x1080")
            creative_data["full_image_url"] = full_url
        elif "dst-emg0" in thumbnail_url:
            # Remove the dst-emg0 parameter that seems to reduce size
            full_url = thumbnail_url.replace("dst-emg0_", "")
            creative_data["full_image_url"] = full_url
    
    # Fallback to using thumbnail or image_url if we still don't have a full image
    if "full_image_url" not in creative_data:
        if "thumbnail_url" in creative_data:
            creative_data["full_image_url"] = creative_data["thumbnail_url"]
        elif "image_url" in creative_data:
            creative_data["full_image_url"] = creative_data["image_url"]
    
    return json.dumps(creative_data, indent=2)

@mcp_server.tool()
async def download_ad_creative_image(access_token: str, ad_id: str, output_path: str = "ad_creatives") -> str:
    """
    Download and save the creative image for a specific ad.
    
    Args:
        access_token: Meta API access token
        ad_id: Meta Ads ad ID
        output_path: Path to save the image (default: 'ad_creatives')
    """
    # First, get the account_id - this is needed for some advanced image queries
    endpoint = f"{ad_id}"
    params = {
        "fields": "account_id"
    }
    
    ad_data = await make_api_request(endpoint, access_token, params)
    account_id = ad_data.get('account_id', '')
    
    # Get the creative details first
    creative_json = await get_ad_creatives(access_token, ad_id)
    creative_data = json.loads(creative_json)
    
    # Look for image URLs in the response
    image_url = None
    if "full_image_url" in creative_data:
        image_url = creative_data.get("full_image_url")
    elif "image_url" in creative_data:
        image_url = creative_data.get("image_url")
    elif "thumbnail_url" in creative_data:
        image_url = creative_data.get("thumbnail_url")
    elif "object_story_spec" in creative_data:
        spec = creative_data.get("object_story_spec", {})
        if "link_data" in spec and "image_url" in spec["link_data"]:
            image_url = spec["link_data"].get("image_url")
        elif "link_data" in spec and "image_hash" in spec["link_data"]:
            # Get image from hash
            image_hash = spec["link_data"].get("image_hash")
            image_endpoint = f"act_{account_id}/adimages"
            image_params = {
                "hashes": [image_hash]
            }
            image_data = await make_api_request(image_endpoint, access_token, image_params)
            if "data" in image_data and len(image_data["data"]) > 0:
                image_url = image_data["data"][0].get("url")
    
    # If we still don't have an image URL, try the adimages endpoint directly
    if not image_url and "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"]:
        images = creative_data["asset_feed_spec"]["images"]
        if images and len(images) > 0 and "hash" in images[0]:
            image_hash = images[0]["hash"]
            image_endpoint = f"act_{account_id}/adimages"
            image_params = {
                "hashes": [image_hash]
            }
            image_data = await make_api_request(image_endpoint, access_token, image_params)
            if "data" in image_data and len(image_data["data"]) > 0:
                image_url = image_data["data"][0].get("url")
    
    if not image_url:
        return json.dumps({
            "error": "No image URL found in creative",
            "creative_data": creative_data
        }, indent=2)
    
    # Try to convert the URL to get higher resolution by removing size parameters
    if "p64x64" in image_url:
        image_url = image_url.replace("p64x64", "p1080x1080")
    elif "dst-emg0" in image_url:
        # Remove the dst-emg0 parameter that seems to reduce size
        image_url = image_url.replace("dst-emg0_", "")
    
    # Download the image
    image_data = await download_image(image_url)
    if not image_data:
        return json.dumps({
            "error": "Failed to download image",
            "image_url": image_url
        }, indent=2)
    
    # Store the image data in our global dictionary with the ad_id as key
    resource_id = f"ad_creative_{ad_id}"
    resource_uri = f"meta-ads://images/{resource_id}"
    ad_creative_images[resource_id] = {
        "data": image_data,
        "mime_type": "image/jpeg",
        "name": f"Ad Creative for {ad_id}"
    }
    
    # Encode the image as base64 for inline display
    base64_data = base64.b64encode(image_data).decode("utf-8")
    
    return json.dumps({
        "success": True,
        "resource_uri": resource_uri,
        "image_url": image_url,
        "creative_data": creative_data,
        "base64_image": base64_data
    }, indent=2)

# Resource Handling
@mcp_server.resource(uri="meta-ads://resources")
async def list_resources() -> Dict[str, Any]:
    """List all available resources (like ad creative images)"""
    resources = []
    
    # Add all ad creative images as resources
    for resource_id, image_info in ad_creative_images.items():
        resources.append({
            "uri": f"meta-ads://images/{resource_id}",
            "mimeType": image_info["mime_type"],
            "name": image_info["name"]
        })
    
    return {"resources": resources}

@mcp_server.resource(uri="meta-ads://images/{resource_id}")
async def get_resource(resource_id: str) -> Dict[str, Any]:
    """Get a specific resource by URI"""
    if resource_id in ad_creative_images:
        image_info = ad_creative_images[resource_id]
        return {
            "data": base64.b64encode(image_info["data"]).decode("utf-8"),
            "mimeType": image_info["mime_type"]
        }
    
    # Resource not found
    return {"error": f"Resource not found: {resource_id}"}

#
# Insights Endpoints
#

@mcp_server.tool()
async def get_insights(
    access_token: str,
    object_id: str,
    time_range: str = "last_30_days",
    breakdown: str = "",
    level: str = "ad"
) -> str:
    """
    Get performance insights for a campaign, ad set, ad or account.
    
    Args:
        access_token: Meta API access token
        object_id: ID of the campaign, ad set, ad or account
        time_range: Time range for insights (default: last_30_days, options: today, yesterday, last_7_days, last_30_days)
        breakdown: Optional breakdown dimension (e.g., age, gender, country)
        level: Level of aggregation (ad, adset, campaign, account)
    """
    endpoint = f"{object_id}/insights"
    params = {
        "date_preset": time_range,
        "fields": "account_id,account_name,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,impressions,clicks,spend,cpc,cpm,ctr,reach,frequency,actions,conversions,unique_clicks,cost_per_action_type",
        "level": level
    }
    
    if breakdown:
        params["breakdowns"] = breakdown
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

if __name__ == "__main__":
    # Initialize and run the server
    mcp_server.run(transport='stdio') 