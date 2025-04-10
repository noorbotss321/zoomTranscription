import os
import base64
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Zoom API credentials
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")

# Caching the token with expiration
zoom_token_cache = {
    "token": None,
    "expiry": 0
}

def get_zoom_access_token():
    """Get Zoom access token using Server-to-Server OAuth"""
    global zoom_token_cache
    
    # Check if we have a cached token that's still valid
    current_time = datetime.now().timestamp()
    if (zoom_token_cache["token"] and 
        zoom_token_cache["expiry"] > current_time + 300):  # 5 min buffer
        return zoom_token_cache["token"]
    
    # Get a new token
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
    creds = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    b64_creds = base64.b64encode(creds.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64_creds}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)  # Default to 1 hour
        
        # Cache the token and its expiry time
        zoom_token_cache["token"] = access_token
        zoom_token_cache["expiry"] = current_time + expires_in
        
        return access_token
    else:
        raise Exception(f"Failed to get Zoom token: {response.status_code} {response.text}")

def send_zoom_message(channel_id: str, message: str):
    """Send a message to a Zoom chat channel"""
    if not channel_id:
        raise ValueError("Channel ID is required")
    
    access_token = get_zoom_access_token()
    url = "https://api.zoom.us/v2/chat/users/me/messages"
    
    payload = {
        "message": message,
        "to_channel": channel_id
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    
    if response.status_code == 201:
        return response.json().get("id")
    else:
        raise Exception(f"Failed to send Zoom message: {response.status_code} {response.text}")

def get_zoom_channel_id(channel_name: str, create_if_missing: bool = True):
    """Get the channel ID for a given channel name"""
    try:
        access_token = get_zoom_access_token()
        url = "https://api.zoom.us/v2/chat/users/me/channels"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            channels = response.json().get("channels", [])
            
            # Look for a channel with matching name
            for channel in channels:
                if channel.get("name") == channel_name:
                    return channel.get("id")
            
            # If not found and create_if_missing is True, create it
            if create_if_missing:
                return create_zoom_channel(channel_name)
            
            return None
        else:
            raise Exception(f"Failed to get Zoom channels: {response.status_code} {response.text}")
            
    except Exception as e:
        print(f"Error getting/creating Zoom channel: {e}")
        return None

def create_zoom_channel(channel_name: str):
    """Create a new Zoom chat channel"""
    access_token = get_zoom_access_token()
    url = "https://api.zoom.us/v2/chat/users/me/channels"
    
    payload = {
        "name": channel_name,
        "type": 2  # 2 is for group chat
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    
    if response.status_code == 201:
        return response.json().get("id")
    else:
        raise Exception(f"Failed to create Zoom channel: {response.status_code} {response.text}")

def is_zoom_call_active():
    """Check if there is an active Zoom meeting"""
    try:
        access_token = get_zoom_access_token()
        url = "https://api.zoom.us/v2/users/me/meetings?type=live"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            meetings = data.get("meetings", [])
            return len(meetings) > 0
        else:
            print(f"Error checking meeting status: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"Error checking Zoom meeting status: {e}")
        return False 