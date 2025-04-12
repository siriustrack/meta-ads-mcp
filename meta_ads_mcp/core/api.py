"""Core API functionality for Meta Ads API."""

from typing import Any, Dict, Optional, Callable
import json
import httpx
import asyncio
import functools
from .auth import needs_authentication, get_current_access_token, auth_manager, start_callback_server

# Constants
META_GRAPH_API_VERSION = "v20.0"
META_GRAPH_API_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"
USER_AGENT = "meta-ads-mcp/1.0"


class GraphAPIError(Exception):
    """Exception raised for errors from the Graph API."""
    def __init__(self, error_data: Dict[str, Any]):
        self.error_data = error_data
        self.message = error_data.get('message', 'Unknown Graph API error')
        super().__init__(self.message)
        
        # Check if this is an auth error
        if "code" in error_data and error_data["code"] in [190, 102, 4]:
            # Common auth error codes
            auth_manager.invalidate_token()


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
            
            # Check for authentication errors
            if e.response.status_code == 401 or e.response.status_code == 403:
                print("Detected authentication error")
                auth_manager.invalidate_token()
            elif "error" in error_info:
                error_obj = error_info.get("error", {})
                # Check for specific FB API errors related to auth
                if isinstance(error_obj, dict) and error_obj.get("code") in [190, 102, 4, 200, 10]:
                    print(f"Detected Facebook API auth error: {error_obj.get('code')}")
                    auth_manager.invalidate_token()
            
            return {"error": f"HTTP Error: {e.response.status_code}", "details": error_info}
        
        except Exception as e:
            print(f"Request Error: {str(e)}")
            return {"error": str(e)}


# Generic wrapper for all Meta API tools
def meta_api_tool(func):
    """Decorator for Meta API tools that handles authentication and error handling."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # If access_token is not in kwargs, try to get it from auth_manager
            if 'access_token' not in kwargs or not kwargs['access_token']:
                try:
                    access_token = await auth_manager.get_current_access_token()
                    if access_token:
                        kwargs['access_token'] = access_token
                except Exception as e:
                    pass

            if 'access_token' not in kwargs or not kwargs['access_token']:
                needs_authentication = True
                
            # Call the original function
            return await func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}
    
    return wrapper 