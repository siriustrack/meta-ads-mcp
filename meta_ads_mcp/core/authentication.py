"""Authentication-specific functionality for Meta Ads API."""

import json
import asyncio
from .api import meta_api_tool
from .auth import start_callback_server, auth_manager, get_current_access_token
from .server import mcp_server


@mcp_server.tool()
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
            "created_at": auth_manager.token_info.created_at if hasattr(auth_manager, "token_info") else None,
            "expires_in": auth_manager.token_info.expires_in if hasattr(auth_manager, "token_info") else None
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