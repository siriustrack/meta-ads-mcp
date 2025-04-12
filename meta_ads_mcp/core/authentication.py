"""Authentication-specific functionality for Meta Ads API."""

import json
import asyncio
from .api import meta_api_tool
from .auth import start_callback_server, auth_manager, get_current_access_token
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def authenticate(access_token: str = None) -> str:
    """
    Get a clickable login link for Meta Ads authentication.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
    
    Returns:
        A clickable resource link for Meta authentication
    """
    # The meta_api_tool decorator will handle all the authentication logic
    # We just need to return a simple success message if we already have a token
    
    if access_token or await get_current_access_token():
        cached_token = auth_manager.get_access_token()
        return json.dumps({
            "message": "Already authenticated",
            "token_status": "Valid token",
            "token_preview": cached_token[:10] + "..." if cached_token else "None",
            "created_at": auth_manager.token_info.created_at if hasattr(auth_manager, "token_info") else None,
            "expires_in": auth_manager.token_info.expires_in if hasattr(auth_manager, "token_info") else None
        }, indent=2)
    
    # If no token exists, the meta_api_tool decorator will handle authentication
    # This return statement is essentially a fallback that won't normally be reached
    return json.dumps({
        "message": "Authentication required",
        "note": "The auth flow should have been handled by the decorator"
    }, indent=2) 