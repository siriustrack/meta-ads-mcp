from typing import Any, Dict, List, Optional
import httpx
import json
import os
import base64
from mcp.server.fastmcp import FastMCP, Image
import datetime
from urllib.parse import urlparse
from PIL import Image as PILImage
import io

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
        print(f"Attempting to download image from URL: {url}")
        
        # Use minimal headers like curl does
        headers = {
            "User-Agent": "curl/8.4.0",
            "Accept": "*/*"
        }
        
        # Ensure the URL is properly escaped
        # But don't modify the already encoded parameters
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # Simple GET request just like curl
            response = await client.get(url, headers=headers)
            
            # Check response
            if response.status_code == 200:
                print(f"Successfully downloaded image: {len(response.content)} bytes")
                return response.content
            else:
                print(f"Failed to download image: HTTP {response.status_code}")
                return None
                
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error when downloading image: {e}")
        return None
    except httpx.RequestError as e:
        print(f"Request Error when downloading image: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error downloading image: {e}")
        return None

# Add a new helper function to try different download methods
async def try_multiple_download_methods(url: str) -> Optional[bytes]:
    """
    Try multiple methods to download an image, with different approaches for Meta CDN.
    
    Args:
        url: Image URL
        
    Returns:
        Image data as bytes if successful, None otherwise
    """
    # Method 1: Direct download with custom headers
    image_data = await download_image(url)
    if image_data:
        return image_data
    
    print("Direct download failed, trying alternative methods...")
    
    # Method 2: Try adding Facebook cookie simulation
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Cookie": "presence=EDvF3EtimeF1697900316EuserFA21B00112233445566AA0EstateFDutF0CEchF_7bCC"  # Fake cookie
        }
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            print(f"Method 2 succeeded with cookie simulation: {len(response.content)} bytes")
            return response.content
    except Exception as e:
        print(f"Method 2 failed: {str(e)}")
    
    # Method 3: Try with session that keeps redirects and cookies
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # First visit Facebook to get cookies
            await client.get("https://www.facebook.com/", timeout=30.0)
            # Then try the image URL
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            print(f"Method 3 succeeded with Facebook session: {len(response.content)} bytes")
            return response.content
    except Exception as e:
        print(f"Method 3 failed: {str(e)}")
    
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
    print(f"Attempting to download creative image for ad {ad_id}")
    
    # First, get creative and account IDs
    ad_endpoint = f"{ad_id}"
    ad_params = {
        "fields": "creative{id},account_id"
    }
    
    ad_data = await make_api_request(ad_endpoint, access_token, ad_params)
    
    if "error" in ad_data:
        return json.dumps({
            "error": "Could not get ad data",
            "details": ad_data
        }, indent=2)
    
    # Extract account_id
    account_id = ad_data.get("account_id", "")
    if not account_id:
        return json.dumps({
            "error": "No account ID found",
            "details": ad_data
        }, indent=2)
    
    # Extract creative ID
    if "creative" not in ad_data:
        return json.dumps({
            "error": "No creative found for this ad",
            "details": ad_data
        }, indent=2)
        
    creative_data = ad_data.get("creative", {})
    creative_id = creative_data.get("id")
    if not creative_id:
        return json.dumps({
            "error": "No creative ID found",
            "details": ad_data
        }, indent=2)
    
    # Get creative details to find image hash
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,image_hash,asset_feed_spec"
    }
    
    creative_details = await make_api_request(creative_endpoint, access_token, creative_params)
    
    # Identify image hashes to use from creative
    image_hashes = []
    
    # Check for direct image_hash on creative
    if "image_hash" in creative_details:
        image_hashes.append(creative_details["image_hash"])
    
    # Check asset_feed_spec for image hashes - common in Advantage+ ads
    if "asset_feed_spec" in creative_details and "images" in creative_details["asset_feed_spec"]:
        for image in creative_details["asset_feed_spec"]["images"]:
            if "hash" in image:
                image_hashes.append(image["hash"])
    
    if not image_hashes:
        # If no hashes found, try to extract from the first creative we found in the API
        # Get creative for ad to try to extract hash
        creative_json = await get_ad_creatives(access_token, ad_id)
        creative_data = json.loads(creative_json)
        
        # Try to extract hash from asset_feed_spec
        if "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"]:
            images = creative_data["asset_feed_spec"]["images"]
            if images and len(images) > 0 and "hash" in images[0]:
                image_hashes.append(images[0]["hash"])
    
    if not image_hashes:
        return json.dumps({
            "error": "No image hashes found in creative",
            "creative_data": creative_details,
            "full_creative": creative_data
        }, indent=2)
    
    print(f"Found image hashes: {image_hashes}")
    
    # Now fetch image data using adimages endpoint with specific format based on successful curl test
    image_endpoint = f"act_{account_id}/adimages"
    
    # Format the hashes parameter exactly as in our successful curl test
    hashes_str = f'["{image_hashes[0]}"]'  # Format first hash only, as JSON string array
    
    image_params = {
        "fields": "hash,url,width,height,name,status",
        "hashes": hashes_str
    }
    
    print(f"Requesting image data with params: {image_params}")
    image_data = await make_api_request(image_endpoint, access_token, image_params)
    
    if "error" in image_data:
        return json.dumps({
            "error": "Failed to get image data",
            "details": image_data
        }, indent=2)
    
    if "data" not in image_data or not image_data["data"]:
        return json.dumps({
            "error": "No image data returned from API",
            "api_response": image_data
        }, indent=2)
    
    # Get the first image URL
    first_image = image_data["data"][0]
    image_url = first_image.get("url")
    
    if not image_url:
        return json.dumps({
            "error": "No valid image URL found",
            "image_data": image_data
        }, indent=2)
    
    print(f"Downloading image from URL: {image_url}")
    
    # Download the image
    image_bytes = await download_image(image_url)
    
    if not image_bytes:
        # If download failed, provide detailed error
        return json.dumps({
            "error": "Failed to download image",
            "image_url": image_url,
            "details": "Failed to download image from the URL provided by the API."
        }, indent=2)
    
    # Store the image data in our global dictionary with the ad_id as key
    resource_id = f"ad_creative_{ad_id}"
    resource_uri = f"meta-ads://images/{resource_id}"
    ad_creative_images[resource_id] = {
        "data": image_bytes,
        "mime_type": "image/jpeg",
        "name": f"Ad Creative for {ad_id}"
    }
    
    # Save to local file if needed
    os.makedirs(output_path, exist_ok=True)
    image_filename = f"{output_path}/ad_{ad_id}_image.jpg"
    with open(image_filename, "wb") as f:
        f.write(image_bytes)
    
    # Encode the image as base64 for inline display
    base64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    return json.dumps({
        "success": True,
        "resource_uri": resource_uri,
        "image_url": image_url,
        "local_path": image_filename,
        "image_details": first_image,
        "image_size_bytes": len(image_bytes),
        "base64_image": base64_data[:1000] + "..." if len(base64_data) > 1000 else base64_data
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

@mcp_server.tool()
async def debug_image_download(access_token: str, url: str = "", ad_id: str = "") -> str:
    """
    Debug image download issues and report detailed diagnostics.
    
    Args:
        access_token: Meta API access token
        url: Direct image URL to test (optional)
        ad_id: Meta Ads ad ID (optional, used if url is not provided)
    """
    results = {
        "diagnostics": {
            "timestamp": str(datetime.datetime.now()),
            "methods_tried": [],
            "request_details": [],
            "network_info": {}
        }
    }
    
    # If no URL provided but ad_id is, get URL from ad creative
    if not url and ad_id:
        print(f"Getting image URL from ad creative for ad {ad_id}")
        # Get the creative details
        creative_json = await get_ad_creatives(access_token, ad_id)
        creative_data = json.loads(creative_json)
        results["creative_data"] = creative_data
        
        # Look for image URL in the creative
        if "full_image_url" in creative_data:
            url = creative_data.get("full_image_url")
        elif "thumbnail_url" in creative_data:
            url = creative_data.get("thumbnail_url")
    
    if not url:
        return json.dumps({
            "error": "No image URL provided or found in ad creative",
            "results": results
        }, indent=2)
    
    results["image_url"] = url
    print(f"Debug: Testing image URL: {url}")
    
    # Try to get network information to help debug
    try:
        import socket
        hostname = urlparse(url).netloc
        ip_address = socket.gethostbyname(hostname)
        results["diagnostics"]["network_info"] = {
            "hostname": hostname,
            "ip_address": ip_address,
            "is_facebook_cdn": "fbcdn" in hostname
        }
    except Exception as e:
        results["diagnostics"]["network_info"] = {
            "error": str(e)
        }
    
    # Method 1: Basic download
    method_result = {
        "method": "Basic download with standard headers",
        "success": False
    }
    results["diagnostics"]["methods_tried"].append(method_result)
    
    try:
        headers = {
            "User-Agent": USER_AGENT
        }
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            method_result["status_code"] = response.status_code
            method_result["headers"] = dict(response.headers)
            
            if response.status_code == 200:
                method_result["success"] = True
                method_result["content_length"] = len(response.content)
                method_result["content_type"] = response.headers.get("content-type")
                
                # Save this successful result
                results["image_data"] = {
                    "length": len(response.content),
                    "type": response.headers.get("content-type"),
                    "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                }
    except Exception as e:
        method_result["error"] = str(e)
    
    # Method 2: Browser emulation
    method_result = {
        "method": "Browser emulation with cookies",
        "success": False
    }
    results["diagnostics"]["methods_tried"].append(method_result)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.facebook.com/",
            "Cookie": "presence=EDvF3EtimeF1697900316EuserFA21B00112233445566AA0EstateFDutF0CEchF_7bCC"
        }
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            method_result["status_code"] = response.status_code
            method_result["headers"] = dict(response.headers)
            
            if response.status_code == 200:
                method_result["success"] = True
                method_result["content_length"] = len(response.content)
                method_result["content_type"] = response.headers.get("content-type")
                
                # If first method didn't succeed, save this successful result
                if "image_data" not in results:
                    results["image_data"] = {
                        "length": len(response.content),
                        "type": response.headers.get("content-type"),
                        "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                    }
    except Exception as e:
        method_result["error"] = str(e)
    
    # Method 3: Graph API direct access (if applicable)
    if "fbcdn" in url or "facebook" in url:
        method_result = {
            "method": "Graph API direct access",
            "success": False
        }
        results["diagnostics"]["methods_tried"].append(method_result)
        
        try:
            # Try to reconstruct the attachment ID from URL if possible
            url_parts = url.split("/")
            potential_ids = [part for part in url_parts if part.isdigit() and len(part) > 10]
            
            if ad_id and potential_ids:
                attachment_id = potential_ids[0]
                endpoint = f"{attachment_id}?fields=url,width,height"
                api_result = await make_api_request(endpoint, access_token)
                
                method_result["api_response"] = api_result
                
                if "url" in api_result:
                    graph_url = api_result["url"]
                    method_result["graph_url"] = graph_url
                    
                    # Try to download from this Graph API URL
                    async with httpx.AsyncClient() as client:
                        response = await client.get(graph_url, timeout=30.0)
                        
                        method_result["status_code"] = response.status_code
                        if response.status_code == 200:
                            method_result["success"] = True
                            method_result["content_length"] = len(response.content)
                            
                            # If previous methods didn't succeed, save this successful result
                            if "image_data" not in results:
                                results["image_data"] = {
                                    "length": len(response.content),
                                    "type": response.headers.get("content-type"),
                                    "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                                }
        except Exception as e:
            method_result["error"] = str(e)
    
    # Generate a recommendation based on what we found
    if "image_data" in results:
        results["recommendation"] = "At least one download method succeeded. Consider implementing the successful method in the main code."
    else:
        # Check if the error appears to be access-related
        access_errors = False
        for method in results["diagnostics"]["methods_tried"]:
            if method.get("status_code") in [401, 403, 503]:
                access_errors = True
                
        if access_errors:
            results["recommendation"] = "Authentication or authorization errors detected. Images may require direct Facebook authentication not possible via API."
        else:
            results["recommendation"] = "Network or other technical errors detected. Check URL expiration or CDN restrictions."
    
    return json.dumps(results, indent=2)

@mcp_server.tool()
async def save_ad_image_via_api(access_token: str, ad_id: str) -> str:
    """
    Try to save an ad image by using the Marketing API's attachment endpoints.
    This is an alternative approach when direct image download fails.
    
    Args:
        access_token: Meta API access token
        ad_id: Meta Ads ad ID
    """
    # First get the ad's creative ID
    ad_endpoint = f"{ad_id}"
    ad_params = {
        "fields": "creative,account_id"
    }
    
    ad_data = await make_api_request(ad_endpoint, access_token, ad_params)
    
    if "error" in ad_data:
        return json.dumps({
            "error": "Could not get ad data",
            "details": ad_data
        }, indent=2)
    
    if "creative" not in ad_data or "id" not in ad_data["creative"]:
        return json.dumps({
            "error": "No creative ID found for this ad",
            "ad_data": ad_data
        }, indent=2)
    
    creative_id = ad_data["creative"]["id"]
    account_id = ad_data.get("account_id", "")
    
    # Now get the creative object
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,thumbnail_url,image_hash,asset_feed_spec"
    }
    
    creative_data = await make_api_request(creative_endpoint, access_token, creative_params)
    
    if "error" in creative_data:
        return json.dumps({
            "error": "Could not get creative data",
            "details": creative_data
        }, indent=2)
    
    # Approach 1: Try to get image through adimages endpoint if we have image_hash
    image_hash = None
    if "image_hash" in creative_data:
        image_hash = creative_data["image_hash"]
    elif "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"] and len(creative_data["asset_feed_spec"]["images"]) > 0:
        image_hash = creative_data["asset_feed_spec"]["images"][0].get("hash")
    
    result = {
        "ad_id": ad_id,
        "creative_id": creative_id,
        "attempts": []
    }
    
    if image_hash and account_id:
        attempt = {
            "method": "adimages endpoint with hash",
            "success": False
        }
        result["attempts"].append(attempt)
        
        try:
            image_endpoint = f"act_{account_id}/adimages"
            image_params = {
                "hashes": [image_hash]
            }
            image_data = await make_api_request(image_endpoint, access_token, image_params)
            attempt["response"] = image_data
            
            if "data" in image_data and len(image_data["data"]) > 0 and "url" in image_data["data"][0]:
                url = image_data["data"][0]["url"]
                attempt["url"] = url
                
                # Try to download the image
                image_bytes = await download_image(url)
                if image_bytes:
                    attempt["success"] = True
                    attempt["image_size"] = len(image_bytes)
                    
                    # Save the image
                    resource_id = f"ad_creative_{ad_id}_method1"
                    resource_uri = f"meta-ads://images/{resource_id}"
                    ad_creative_images[resource_id] = {
                        "data": image_bytes,
                        "mime_type": "image/jpeg",
                        "name": f"Ad Creative for {ad_id} (Method 1)"
                    }
                    
                    # Return success with resource info
                    result["resource_uri"] = resource_uri
                    result["success"] = True
                    base64_sample = base64.b64encode(image_bytes[:100]).decode("utf-8") + "..."
                    result["base64_sample"] = base64_sample
        except Exception as e:
            attempt["error"] = str(e)
    
    # Approach 2: Try directly with the thumbnails endpoint
    attempt = {
        "method": "thumbnails endpoint on creative",
        "success": False
    }
    result["attempts"].append(attempt)
    
    try:
        thumbnails_endpoint = f"{creative_id}/thumbnails"
        thumbnails_params = {}
        thumbnails_data = await make_api_request(thumbnails_endpoint, access_token, thumbnails_params)
        attempt["response"] = thumbnails_data
        
        if "data" in thumbnails_data and len(thumbnails_data["data"]) > 0:
            for thumbnail in thumbnails_data["data"]:
                if "uri" in thumbnail:
                    url = thumbnail["uri"]
                    attempt["url"] = url
                    
                    # Try to download the image
                    image_bytes = await download_image(url)
                    if image_bytes:
                        attempt["success"] = True
                        attempt["image_size"] = len(image_bytes)
                        
                        # Save the image if method 1 didn't already succeed
                        if "success" not in result or not result["success"]:
                            resource_id = f"ad_creative_{ad_id}_method2"
                            resource_uri = f"meta-ads://images/{resource_id}"
                            ad_creative_images[resource_id] = {
                                "data": image_bytes,
                                "mime_type": "image/jpeg",
                                "name": f"Ad Creative for {ad_id} (Method 2)"
                            }
                            
                            # Return success with resource info
                            result["resource_uri"] = resource_uri
                            result["success"] = True
                            base64_sample = base64.b64encode(image_bytes[:100]).decode("utf-8") + "..."
                            result["base64_sample"] = base64_sample
                        
                        # No need to try more thumbnails if we succeeded
                        break
    except Exception as e:
        attempt["error"] = str(e)
    
    # Approach 3: Try using the preview shareable link as an alternate source
    attempt = {
        "method": "preview_shareable_link",
        "success": False
    }
    result["attempts"].append(attempt)
    
    try:
        # Get ad details with preview link
        ad_preview_endpoint = f"{ad_id}"
        ad_preview_params = {
            "fields": "preview_shareable_link"
        }
        ad_preview_data = await make_api_request(ad_preview_endpoint, access_token, ad_preview_params)
        
        if "preview_shareable_link" in ad_preview_data:
            preview_link = ad_preview_data["preview_shareable_link"]
            attempt["preview_link"] = preview_link
            
            # We can't directly download the preview image, but let's note it for manual inspection
            attempt["note"] = "Preview link available for manual inspection in browser"
            
            # This approach doesn't actually download the image, but the link might be useful
            # for debugging purposes or manual verification
    except Exception as e:
        attempt["error"] = str(e)
    
    # Overall result
    if "success" in result and result["success"]:
        result["message"] = "Successfully retrieved ad image through one of the API methods"
    else:
        result["message"] = "Failed to retrieve ad image through any API method"
        
    return json.dumps(result, indent=2)

@mcp_server.tool()
def analyze_ad_creative_image(image_path: str) -> Image:
    """
    Open and analyze a local ad creative image previously downloaded with download_ad_creative_image.
    This returns the image directly to the LLM for visual analysis.
    
    Args:
        image_path: Path to the local image file (e.g., ad_creatives/ad_123456789_image.jpg)
    
    Returns:
        The image for direct LLM analysis
    """
    try:
        # Open the image file using PIL
        img = PILImage.open(image_path)
        
        # Convert to RGB if needed (in case of RGBA, etc.)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # Create a byte stream of the image data
        byte_arr = io.BytesIO()
        img.save(byte_arr, format="JPEG")
        img_bytes = byte_arr.getvalue()
        
        # Return as an Image object that LLM can directly analyze
        return Image(data=img_bytes, format="jpeg")
        
    except Exception as e:
        # Return an error message if something goes wrong
        return f"Error analyzing image: {str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp_server.run(transport='stdio') 