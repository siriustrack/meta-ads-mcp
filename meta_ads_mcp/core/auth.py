"""Authentication related functionality for Meta Ads API."""

from typing import Any, Dict, Optional
import time
import platform
import pathlib
import os
import threading
import socket
import webbrowser
import asyncio
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Auth constants
AUTH_SCOPE = "ads_management,ads_read,business_management"
AUTH_REDIRECT_URI = "http://localhost:8888/callback"
AUTH_RESPONSE_TYPE = "token"

# Global flag for authentication state
needs_authentication = False

# Global variable for server thread and state
callback_server_thread = None
callback_server_lock = threading.Lock()
callback_server_running = False
callback_server_port = None

# Global token container for communication between threads
token_container = {"token": None, "expires_in": None, "user_id": None}

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
    
    def clear_token(self) -> None:
        """Clear the current token and remove from cache"""
        self.invalidate_token()


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


def start_callback_server():
    """Start the callback server if it's not already running"""
    global callback_server_thread, callback_server_running, callback_server_port, auth_manager
    
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
        if 'auth_manager' in globals():
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


async def get_current_access_token() -> Optional[str]:
    """
    Get the current access token from cache
    
    Returns:
        Current access token or None if not available
    """
    return auth_manager.get_access_token()


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
                    from .api import make_api_request
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

# Initialize auth manager with a placeholder - will be updated at runtime
META_APP_ID = os.environ.get("META_APP_ID", "YOUR_META_APP_ID")
auth_manager = AuthManager(META_APP_ID) 