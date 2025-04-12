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
    """Decorator to handle authentication for all Meta API tools"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Handle various MCP invocation patterns
        if len(args) == 1 and isinstance(args[0], str):
            # If it's a string and looks like JSON, try to parse it
            try:
                parsed = json.loads(args[0]) if args[0] else {}
                if isinstance(parsed, dict):
                    # If it has an 'args' key, use that for positional args
                    if 'args' in parsed:
                        args = (parsed['args'],)
                    # If it has a 'kwargs' key, update kwargs
                    if 'kwargs' in parsed:
                        if isinstance(parsed['kwargs'], str):
                            try:
                                kwargs.update(json.loads(parsed['kwargs']))
                            except:
                                pass
                        elif isinstance(parsed['kwargs'], dict):
                            kwargs.update(parsed['kwargs'])
                else:
                    # If it's not a dict, treat it as a single positional arg
                    args = (args[0],)
            except:
                # If parsing fails, treat it as a single positional arg
                args = (args[0],)
        
        # Check if access_token is provided in kwargs
        access_token = kwargs.get('access_token')
        
        # If not, try to get it from the auth manager
        if not access_token:
            access_token = await get_current_access_token()
        
        # If still no token, we need authentication
        if not access_token:
            global needs_authentication
            needs_authentication = True
            
            # Start the callback server
            port = start_callback_server()
            
            # Update auth manager's redirect URI with the current port
            auth_manager.redirect_uri = f"http://localhost:{port}/callback"
            
            # Generate the authentication URL
            login_url = auth_manager.get_auth_url()
            
            # Create a resource response that includes the markdown link format
            response = {
                "error": "Authentication required to use Meta Ads API",
                "login_url": login_url,
                "server_status": f"Callback server running on port {port}",
                "markdown_link": f"[Click here to authenticate with Meta Ads API]({login_url})",
                "message": "IMPORTANT: Please use the Markdown link format in your response to allow the user to click it.",
                "instructions_for_llm": "You must present this link as clickable Markdown to the user using the markdown_link format provided.",
                "note": "After authenticating, the token will be automatically saved."
            }
            
            # Wait a moment to ensure the server is fully started
            await asyncio.sleep(1)
            
            return json.dumps(response, indent=2)
        
        # Update kwargs with the token
        kwargs['access_token'] = access_token
        
        # Call the original function
        try:
            result = await func(*args, **kwargs)
            
            # If authentication is needed after the call (e.g., token was invalidated)
            if needs_authentication:
                # Start the callback server
                port = start_callback_server()
                
                # Update auth manager's redirect URI with the current port
                auth_manager.redirect_uri = f"http://localhost:{port}/callback"
                
                # Generate the authentication URL
                login_url = auth_manager.get_auth_url()
                
                # Create a resource response that includes the markdown link format
                response = {
                    "error": "Session expired or token invalid. Please re-authenticate with Meta Ads API",
                    "login_url": login_url,
                    "server_status": f"Callback server running on port {port}",
                    "markdown_link": f"[Click here to re-authenticate with Meta Ads API]({login_url})",
                    "message": "IMPORTANT: Please use the Markdown link format in your response to allow the user to click it.",
                    "instructions_for_llm": "You must present this link as clickable Markdown to the user using the markdown_link format provided.",
                    "note": "After authenticating, the token will be automatically saved."
                }
                
                # Wait a moment to ensure the server is fully started
                await asyncio.sleep(1)
                
                return json.dumps(response, indent=2)
            
            return result
        except Exception as e:
            # Handle any unexpected errors
            error_result = {
                "error": f"Error calling Meta API: {str(e)}"
            }
            return json.dumps(error_result, indent=2)
    
    return wrapper 