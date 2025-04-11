from typing import Any, Dict, List, Optional
import httpx
import json
import os
import base64
from mcp.server.fastmcp import FastMCP, Image
import datetime
from urllib.parse import urlparse, parse_qs
from PIL import Image as PILImage
import io
import webbrowser
import time
import platform
import pathlib
import argparse
import asyncio
import threading
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

# Initialize FastMCP server
mcp_server = FastMCP("meta-ads-generated", use_consistent_tool_format=True)

# Constants
META_GRAPH_API_VERSION = "v20.0"
META_GRAPH_API_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"
USER_AGENT = "meta-ads-mcp/1.0"

# Meta App configuration - Using a placeholder app ID. This will be overridden by:
# 1. Command line arguments
# 2. Environment variables 
# 3. User input during runtime
META_APP_ID = "YOUR_META_APP_ID"  # Will be replaced at runtime

# Try to load from environment variable
if os.environ.get("META_APP_ID"):
    META_APP_ID = os.environ.get("META_APP_ID")

# Auth constants
AUTH_SCOPE = "ads_management,ads_read,business_management"
AUTH_REDIRECT_URI = "http://localhost:8888/callback"
AUTH_RESPONSE_TYPE = "token"

# Global store for ad creative images
ad_creative_images = {}

# Global flag for authentication state
needs_authentication = False

# Global variable for server thread and state
callback_server_thread = None
callback_server_lock = threading.Lock()
callback_server_running = False
callback_server_port = None
# Global token container for communication between threads
token_container = {"token": None, "expires_in": None, "user_id": None}

# Callback Handler class definition
class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global token_container, auth_manager, needs_authentication
        
        if self.path.startswith("/callback"):
            # Return a page that extracts token from URL hash fragment
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body>
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to the application.</p>
                <script>
                    // Extract token from URL hash
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const token = params.get('access_token');
                    const expires_in = params.get('expires_in');
                    
                    // Send token back to server using fetch
                    fetch('/token?' + new URLSearchParams({
                        token: token,
                        expires_in: expires_in
                    }))
                    .then(response => console.log('Token sent to app'));
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            return
        
        if self.path.startswith("/token"):
            # Extract token from query params
            query = parse_qs(urlparse(self.path).query)
            token_container["token"] = query.get("token", [""])[0]
            
            if "expires_in" in query:
                try:
                    token_container["expires_in"] = int(query.get("expires_in", ["0"])[0])
                except ValueError:
                    token_container["expires_in"] = None
            
            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Token received")
            
            # Process the token (save it) immediately
            if token_container["token"]:
                # Create token info and save to cache
                token_info = TokenInfo(
                    access_token=token_container["token"],
                    expires_in=token_container["expires_in"]
                )
                auth_manager.token_info = token_info
                auth_manager._save_token_to_cache()
                
                # Reset auth needed flag
                needs_authentication = False
                
                print(f"Token received and cached (expires in {token_container['expires_in']} seconds)")
            return
    
    # Silence server logs
    def log_message(self, format, *args):
        return

# Authentication related classes
class TokenInfo:
    """Stores token information including expiration"""
    def __init__(self, access_token: str, expires_in: int = None, user_id: str = None):
        self.access_token = access_token
        self.expires_in = expires_in
        self.user_id = user_id
        self.created_at = int(time.time())
    
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if not self.expires_in:
            return False  # If no expiration is set, assume it's not expired
        
        current_time = int(time.time())
        return current_time > (self.created_at + self.expires_in)
    
    def serialize(self) -> Dict[str, Any]:
        """Convert to a dictionary for storage"""
        return {
            "access_token": self.access_token,
            "expires_in": self.expires_in,
            "user_id": self.user_id,
            "created_at": self.created_at
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'TokenInfo':
        """Create from a stored dictionary"""
        token = cls(
            access_token=data.get("access_token", ""),
            expires_in=data.get("expires_in"),
            user_id=data.get("user_id")
        )
        token.created_at = data.get("created_at", int(time.time()))
        return token


class AuthManager:
    """Manages authentication with Meta APIs"""
    def __init__(self, app_id: str, redirect_uri: str = AUTH_REDIRECT_URI):
        self.app_id = app_id
        self.redirect_uri = redirect_uri
        self.token_info = None
        self._load_cached_token()
    
    def _get_token_cache_path(self) -> pathlib.Path:
        """Get the platform-specific path for token cache file"""
        if platform.system() == "Windows":
            base_path = pathlib.Path(os.environ.get("APPDATA", ""))
        elif platform.system() == "Darwin":  # macOS
            base_path = pathlib.Path.home() / "Library" / "Application Support"
        else:  # Assume Linux/Unix
            base_path = pathlib.Path.home() / ".config"
        
        # Create directory if it doesn't exist
        cache_dir = base_path / "meta-ads-mcp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        return cache_dir / "token_cache.json"
    
    def _load_cached_token(self) -> bool:
        """Load token from cache if available"""
        cache_path = self._get_token_cache_path()
        
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
                self.token_info = TokenInfo.deserialize(data)
                
                # Check if token is expired
                if self.token_info.is_expired():
                    print("Cached token is expired")
                    self.token_info = None
                    return False
                
                print(f"Loaded cached token (expires in {(self.token_info.created_at + self.token_info.expires_in) - int(time.time())} seconds)")
                return True
        except Exception as e:
            print(f"Error loading cached token: {e}")
            return False
    
    def _save_token_to_cache(self) -> None:
        """Save token to cache file"""
        if not self.token_info:
            return
        
        cache_path = self._get_token_cache_path()
        
        try:
            with open(cache_path, "w") as f:
                json.dump(self.token_info.serialize(), f)
            print(f"Token cached at: {cache_path}")
        except Exception as e:
            print(f"Error saving token to cache: {e}")
    
    def get_auth_url(self) -> str:
        """Generate the Facebook OAuth URL for desktop app flow"""
        return (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={self.app_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"scope={AUTH_SCOPE}&"
            f"response_type={AUTH_RESPONSE_TYPE}"
        )
    
    def authenticate(self, force_refresh: bool = False) -> Optional[str]:
        """
        Authenticate with Meta APIs
        
        Args:
            force_refresh: Force token refresh even if cached token exists
            
        Returns:
            Access token if successful, None otherwise
        """
        # Check if we already have a valid token
        if not force_refresh and self.token_info and not self.token_info.is_expired():
            return self.token_info.access_token
        
        # Start the callback server if not already running
        port = start_callback_server()
        
        # Generate the auth URL
        auth_url = self.get_auth_url()
        
        # Open browser with auth URL
        print(f"Opening browser with URL: {auth_url}")
        webbrowser.open(auth_url)
        
        # We don't wait for the token here anymore
        # The token will be processed by the callback server
        # Just return None to indicate we've started the flow
        return None
    
    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token, refreshing if necessary
        
        Returns:
            Access token if available, None otherwise
        """
        if not self.token_info or self.token_info.is_expired():
            return None
        
        return self.token_info.access_token
        
    def invalidate_token(self) -> None:
        """Invalidate the current token, usually because it has expired or is invalid"""
        if self.token_info:
            print(f"Invalidating token: {self.token_info.access_token[:10]}...")
            self.token_info = None
            
            # Signal that authentication is needed
            global needs_authentication
            needs_authentication = True
            
            # Remove the cached token file
            try:
                cache_path = self._get_token_cache_path()
                if cache_path.exists():
                    os.remove(cache_path)
                    print(f"Removed cached token file: {cache_path}")
            except Exception as e:
                print(f"Error removing cached token: {e}")


# Initialize auth manager
auth_manager = AuthManager(META_APP_ID)

# Function to get token without requiring it as a parameter
async def get_current_access_token() -> Optional[str]:
    """
    Get the current access token from cache
    
    Returns:
        Current access token or None if not available
    """
    return auth_manager.get_access_token()

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
    async def wrapper(*args, **kwargs):
        # Handle various MCP invocation patterns
        if len(args) == 1:
            # MCP might pass a single string argument that contains JSON
            if isinstance(args[0], str):
                try:
                    # Try to parse the single string argument as JSON dictionary
                    parsed_kwargs = json.loads(args[0]) if args[0] else {}
                    # Clear args and use parsed_kwargs
                    args = ()
                    kwargs.update(parsed_kwargs)
                except Exception:
                    pass
            # MCP might also pass a single dictionary argument
            elif isinstance(args[0], dict):
                # Treat the dict as kwargs
                kwargs.update(args[0])
                args = ()
        
        # Check if we have a 'kwargs' parameter, which means MCP is nesting the real parameters
        if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], (str, dict)):
            # If it's a string, try to parse as JSON
            if isinstance(kwargs['kwargs'], str):
                try:
                    parsed_inner_kwargs = json.loads(kwargs['kwargs']) if kwargs['kwargs'] else {}
                    kwargs.update(parsed_inner_kwargs)
                except Exception:
                    # If parsing fails, just keep the original kwargs
                    pass
            # If it's already a dict, just update kwargs
            elif isinstance(kwargs['kwargs'], dict):
                kwargs.update(kwargs['kwargs'])
            
            # Remove the 'kwargs' parameter to avoid confusion
            del kwargs['kwargs']
            
        # Handle 'args' parameter if it exists
        if 'args' in kwargs:
            # We don't use positional args, so just remove it
            del kwargs['args']
        
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
            result = await func(**kwargs)
            
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
    
    # Return the wrapper function with the same name and docstring
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper

# Apply the decorator to tool functions
@mcp_server.tool()
@meta_api_tool
async def get_ad_accounts(access_token: str = None, user_id: str = "me", limit: int = 10) -> str:
    """
    Get ad accounts accessible by a user.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
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
@meta_api_tool
async def get_account_info(access_token: str = None, account_id: str = None) -> str:
    """
    Get detailed information about a specific ad account.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts(access_token, limit=1)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
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
@meta_api_tool
async def get_campaigns(access_token: str = None, account_id: str = None, limit: int = 10, status_filter: str = "") -> str:
    """
    Get campaigns for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of campaigns to return (default: 10)
        status_filter: Filter by status (empty for all, or 'ACTIVE', 'PAUSED', etc.)
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts(access_token, limit=1)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
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
@meta_api_tool
async def get_campaign_details(access_token: str = None, campaign_id: str = None) -> str:
    """
    Get detailed information about a specific campaign.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        campaign_id: Meta Ads campaign ID
    """
    if not campaign_id:
        return json.dumps({"error": "No campaign ID provided"}, indent=2)
    
    endpoint = f"{campaign_id}"
    params = {
        "fields": "id,name,objective,status,daily_budget,lifetime_budget,buying_type,start_time,stop_time,created_time,updated_time,bid_strategy,special_ad_categories,special_ad_category_country,budget_remaining,configured_status"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
@meta_api_tool
async def create_campaign(
    access_token: str = None,
    account_id: str = None,
    name: str = None,
    objective: str = None,
    status: str = "PAUSED",
    special_ad_categories: List[str] = None,
    daily_budget: Optional[int] = None,
    lifetime_budget: Optional[int] = None
) -> str:
    """
    Create a new campaign in a Meta Ads account.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Campaign name
        objective: Campaign objective (AWARENESS, TRAFFIC, ENGAGEMENT, etc.)
        status: Initial campaign status (default: PAUSED)
        special_ad_categories: List of special ad categories if applicable
        daily_budget: Daily budget in account currency (in cents)
        lifetime_budget: Lifetime budget in account currency (in cents)
    """
    # Check required parameters
    if not account_id:
        return json.dumps({"error": "No account ID provided"}, indent=2)
    
    if not name:
        return json.dumps({"error": "No campaign name provided"}, indent=2)
        
    if not objective:
        return json.dumps({"error": "No campaign objective provided"}, indent=2)
    
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
        accounts_json = await get_ad_accounts(access_token, limit=1)
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
        access_token: Meta API access token (optional - will use cached token if not provided)
        adset_id: Meta Ads ad set ID
    """
    if not adset_id:
        return json.dumps({"error": "No ad set ID provided"}, indent=2)
    
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
@meta_api_tool
async def get_ads(
    access_token: str = None,
    account_id: str = None,
    limit: int = 10,
    campaign_id: str = "",
    adset_id: str = ""
) -> str:
    """
    Get ads for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ads to return (default: 10)
        campaign_id: Optional campaign ID to filter by
        adset_id: Optional ad set ID to filter by
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts(access_token=access_token, limit=1)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
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
@meta_api_tool
async def get_ad_details(access_token: str = None, ad_id: str = None) -> str:
    """
    Get detailed information about a specific ad.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
    endpoint = f"{ad_id}"
    params = {
        "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs,preview_shareable_link"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)

@mcp_server.tool()
@meta_api_tool
async def get_ad_creatives(access_token: str = None, ad_id: str = None) -> str:
    """
    Get creative details for a specific ad. Best if combined with get_ad_image to get the full image.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
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
@meta_api_tool
async def get_ad_image(access_token: str = None, ad_id: str = None) -> Image:
    """
    Get, download, and visualize a Meta ad image in one step. Useful to see the image in the LLM.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    
    Returns:
        The ad image ready for direct visual analysis
    """
    if not ad_id:
        return "Error: No ad ID provided"
        
    print(f"Attempting to get and analyze creative image for ad {ad_id}")
    
    # First, get creative and account IDs
    ad_endpoint = f"{ad_id}"
    ad_params = {
        "fields": "creative{id},account_id"
    }
    
    ad_data = await make_api_request(ad_endpoint, access_token, ad_params)
    
    if "error" in ad_data:
        return f"Error: Could not get ad data - {json.dumps(ad_data)}"
    
    # Extract account_id
    account_id = ad_data.get("account_id", "")
    if not account_id:
        return "Error: No account ID found"
    
    # Extract creative ID
    if "creative" not in ad_data:
        return "Error: No creative found for this ad"
        
    creative_data = ad_data.get("creative", {})
    creative_id = creative_data.get("id")
    if not creative_id:
        return "Error: No creative ID found"
    
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
        return "Error: No image hashes found in creative"
    
    print(f"Found image hashes: {image_hashes}")
    
    # Now fetch image data using adimages endpoint with specific format
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
        return f"Error: Failed to get image data - {json.dumps(image_data)}"
    
    if "data" not in image_data or not image_data["data"]:
        return "Error: No image data returned from API"
    
    # Get the first image URL
    first_image = image_data["data"][0]
    image_url = first_image.get("url")
    
    if not image_url:
        return "Error: No valid image URL found"
    
    print(f"Downloading image from URL: {image_url}")
    
    # Download the image
    image_bytes = await download_image(image_url)
    
    if not image_bytes:
        return "Error: Failed to download image"
    
    try:
        # Convert bytes to PIL Image
        img = PILImage.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # Create a byte stream of the image data
        byte_arr = io.BytesIO()
        img.save(byte_arr, format="JPEG")
        img_bytes = byte_arr.getvalue()
        
        # Return as an Image object that LLM can directly analyze
        return Image(data=img_bytes, format="jpeg")
        
    except Exception as e:
        return f"Error processing image: {str(e)}"

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
@meta_api_tool
async def get_insights(
    access_token: str = None,
    object_id: str = None,
    time_range: str = "maximum",
    breakdown: str = "",
    level: str = "ad"
) -> str:
    """
    Get performance insights for a campaign, ad set, ad or account.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        object_id: ID of the campaign, ad set, ad or account
        time_range: Time range for insights (default: last_30_days, options: today, yesterday, this_month, last_month, this_quarter, maximum, data_maximum, last_3d, last_7d, last_14d, last_28d, last_30d, last_90d, last_week_mon_sun, last_week_sun_sat, last_quarter, last_year, this_week_mon_today, this_week_sun_today, this_year)
        breakdown: Optional breakdown dimension (e.g., age, gender, country)
        level: Level of aggregation (ad, adset, campaign, account)
    """
    if not object_id:
        return json.dumps({"error": "No object ID provided"}, indent=2)
        
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
@meta_api_tool
async def debug_image_download(access_token: str = None, url: str = "", ad_id: str = "") -> str:
    """
    Debug image download issues and report detailed diagnostics.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
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
        creative_json = await get_ad_creatives(access_token=access_token, ad_id=ad_id)
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
@meta_api_tool
async def save_ad_image_via_api(access_token: str = None, ad_id: str = None) -> str:
    """
    Try to save an ad image by using the Marketing API's attachment endpoints.
    This is an alternative approach when direct image download fails.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
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
@meta_api_tool
async def get_login_link(access_token: str = None) -> str:
    """
    Get a clickable login link for Meta Ads authentication.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
    
    Returns:
        A clickable resource link for Meta authentication
    """
    # Check if we have a cached token
    cached_token = auth_manager.get_access_token()
    token_status = "No token" if not cached_token else "Valid token"
    
    # If we already have a valid token and none was provided, just return success
    if cached_token and not access_token:
        return json.dumps({
            "message": "Already authenticated",
            "token_status": token_status,
            "token_preview": cached_token[:10] + "...",
            "created_at": auth_manager.token_info.created_at,
            "expires_in": auth_manager.token_info.expires_in
        }, indent=2)
    
    # IMPORTANT: Start the callback server first by calling our helper function
    # This ensures the server is ready before we provide the URL to the user
    port = start_callback_server()
    
    # Generate direct login URL
    auth_manager.redirect_uri = f"http://localhost:{port}/callback"  # Ensure port is set correctly
    login_url = auth_manager.get_auth_url()
    
    # Return a special format that helps the LLM format the response properly
    response = {
        "login_url": login_url,
        "token_status": token_status,
        "server_status": f"Callback server running on port {port}",
        "markdown_link": f"[Click here to authenticate with Meta Ads]({login_url})",
        "message": "IMPORTANT: Please use the Markdown link format in your response to allow the user to click it.",
        "instructions_for_llm": "You must present this link as clickable Markdown to the user using the markdown_link format provided.",
        "note": "After authenticating, the token will be automatically saved."
    }
    
    # Wait a moment to ensure the server is fully started
    await asyncio.sleep(1)
    
    return json.dumps(response, indent=2)

# Helper function to start the login flow
def login():
    """
    Start the login flow to authenticate with Meta
    """
    print("Starting Meta Ads authentication flow...")
    
    try:
        # Start the callback server first
        port = start_callback_server()
        
        # Get the auth URL and open the browser
        auth_url = auth_manager.get_auth_url()
        print(f"Opening browser with URL: {auth_url}")
        webbrowser.open(auth_url)
        
        # Wait for token to be received
        print("Waiting for authentication to complete...")
        max_wait = 300  # 5 minutes
        wait_interval = 2  # 2 seconds
        
        for _ in range(max_wait // wait_interval):
            if token_container["token"]:
                token = token_container["token"]
                print("Authentication successful!")
                # Verify token works by getting basic user info
                try:
                    result = asyncio.run(make_api_request("me", token, {}))
                    print(f"Authenticated as: {result.get('name', 'Unknown')} (ID: {result.get('id', 'Unknown')})")
                    return
                except Exception as e:
                    print(f"Warning: Could not verify token: {e}")
                    return
            time.sleep(wait_interval)
        
        print("Authentication timed out. Please try again.")
    except Exception as e:
        print(f"Error during authentication: {e}")
        print(f"Direct authentication URL: {auth_manager.get_auth_url()}")
        print("You can manually open this URL in your browser to complete authentication.")

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

def start_callback_server():
    """Start the callback server if it's not already running"""
    global callback_server_thread, callback_server_running, callback_server_port
    
    with callback_server_lock:
        if callback_server_running:
            print(f"Callback server already running on port {callback_server_port}")
            return callback_server_port
        
        # Find an available port
        port = 8888
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    break
            except OSError:
                port += 1
                if attempt == max_attempts - 1:
                    raise Exception(f"Could not find an available port after {max_attempts} attempts")
        
        # Update auth manager's redirect URI with new port
        auth_manager.redirect_uri = f"http://localhost:{port}/callback"
        callback_server_port = port
        
        try:
            # Get the CallbackHandler class from global scope
            handler_class = globals()['CallbackHandler']
            
            # Create and start server in a daemon thread
            server = HTTPServer(('localhost', port), handler_class)
            print(f"Callback server starting on port {port}")
            
            # Create a simple flag to signal when the server is ready
            server_ready = threading.Event()
            
            def server_thread():
                try:
                    # Signal that the server thread has started
                    server_ready.set()
                    print(f"Callback server is now ready on port {port}")
                    # Start serving HTTP requests
                    server.serve_forever()
                except Exception as e:
                    print(f"Server error: {e}")
                finally:
                    with callback_server_lock:
                        global callback_server_running
                        callback_server_running = False
            
            callback_server_thread = threading.Thread(target=server_thread)
            callback_server_thread.daemon = True
            callback_server_thread.start()
            
            # Wait for server to be ready (up to 5 seconds)
            if not server_ready.wait(timeout=5):
                print("Warning: Timeout waiting for server to start, but continuing anyway")
            
            callback_server_running = True
            
            # Verify the server is actually accepting connections
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect(('localhost', port))
                print(f"Confirmed server is accepting connections on port {port}")
            except Exception as e:
                print(f"Warning: Could not verify server connection: {e}")
                
            return port
            
        except Exception as e:
            print(f"Error starting callback server: {e}")
            # Try again with a different port in case of bind issues
            if "address already in use" in str(e).lower():
                print("Port may be in use, trying a different port...")
                return start_callback_server()  # Recursive call with a new port
            raise e

if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Meta Ads MCP Server")
    parser.add_argument("--login", action="store_true", help="Authenticate with Meta and store the token")
    parser.add_argument("--app-id", type=str, help="Meta App ID (Client ID) for authentication")
    
    args = parser.parse_args()
    
    # Update app ID if provided
    if args.app_id:
        auth_manager.app_id = args.app_id
    
    # Handle login command
    if args.login:
        login()
    else:
        # Initialize and run the server
        mcp_server.run(transport='stdio') 