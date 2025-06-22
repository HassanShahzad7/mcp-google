"""
This module provides utilities for authenticating with and using the Google Chat API.
Includes space management and message operations with enhanced user detail fetching.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

# Default settings
DEFAULT_CREDENTIALS_PATH = "credentials.json"
DEFAULT_TOKEN_PATH = "google_chat_token.json"
DEFAULT_USER_ID = "me"

# Google Chat API scopes
GOOGLE_CHAT_SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.spaces",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
    "https://www.googleapis.com/auth/userinfo.profile",  # Added for user details
    "https://www.googleapis.com/auth/userinfo.email",   # Added for user details
    "openid",  # Add this line to prevent scope mismatch error
]

# Type alias for the Google Chat service
GoogleChatService = Resource

logger = logging.getLogger(__name__)


def get_google_chat_service(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
    scopes: List[str] = GOOGLE_CHAT_SCOPES,
) -> GoogleChatService:
    """
    Authenticate with Google Chat API and return the service object.

    Args:
        credentials_path: Path to the credentials JSON file
        token_path: Path to save/load the token
        scopes: OAuth scopes to request

    Returns:
        Authenticated Google Chat API service
    """
    creds = None

    # Look for token file with stored credentials
    if os.path.exists(token_path):
        with open(token_path, "r") as token:
            token_data = json.load(token)
            creds = Credentials.from_authorized_user_info(token_data)

    # If credentials don't exist or are invalid, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if credentials file exists
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {credentials_path}. "
                    "Please download your OAuth credentials from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        token_json = json.loads(creds.to_json())
        with open(token_path, "w") as token:
            json.dump(token_json, token)

    # Build the Google Chat service
    return build("chat", "v1", credentials=creds)


# === GOOGLE CHAT SPACE FUNCTIONS ===

def list_chat_spaces(
    service: GoogleChatService,
    page_size: int = 100,
    filter_str: Optional[str] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists all Google Chat spaces the authenticated user has access to.

    Args:
        service: Google Chat API service instance
        page_size: Maximum number of spaces to return per page
        filter_str: Optional filter string for spaces

    Returns:
        List of space objects, or None if an error occurs
    """
    logger.info(f"Fetching chat spaces. Page size: {page_size}")

    try:
        request_params = {"pageSize": page_size}
        if filter_str:
            request_params["filter"] = filter_str

        spaces_result = service.spaces().list(**request_params).execute()
        spaces = spaces_result.get("spaces", [])

        logger.info(f"Found {len(spaces)} chat spaces.")
        return spaces

    except HttpError as error:
        logger.error(f"An API error occurred while fetching chat spaces: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching chat spaces: {e}", exc_info=True)
        return None


def get_space_details(
    service: GoogleChatService,
    space_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get details for a specific Google Chat space.

    Args:
        service: Google Chat API service instance
        space_name: The name/identifier of the space (e.g., 'spaces/space_id')

    Returns:
        Space object with details, or None if an error occurs
    """
    logger.info(f"Fetching details for space: {space_name}")

    try:
        space = service.spaces().get(name=space_name).execute()
        logger.info(f"Successfully retrieved space details for: {space_name}")
        return space

    except HttpError as error:
        logger.error(f"An API error occurred while fetching space details: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching space details: {e}", exc_info=True)
        return None


# === GOOGLE CHAT MESSAGE FUNCTIONS ===

def list_space_messages(
    service: GoogleChatService,
    space_name: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page_size: int = 100,
    order_by: str = "createTime desc"
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists messages from a specific Google Chat space with optional time filtering.

    Args:
        service: Google Chat API service instance
        space_name: The name/identifier of the space to fetch messages from
        start_date: Optional start datetime for filtering messages
        end_date: Optional end datetime for filtering messages
        page_size: Maximum number of messages to return per page
        order_by: Order of the messages returned

    Returns:
        List of message objects from the space, or None if an error occurs
    """
    logger.info(f"Fetching messages from space: {space_name}")

    try:
        # Prepare request parameters
        request_params = {
            "parent": space_name,
            "pageSize": page_size,
            "orderBy": order_by
        }
        
        # Only add filter if dates are provided
        if start_date:
            try:
                if end_date:
                    # Format for date range query - try different formats
                    # Try without microseconds first
                    start_rfc = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    end_rfc = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    filter_str = f'createTime > "{start_rfc}" AND createTime < "{end_rfc}"'
                else:
                    # For single day query, set range from start of day to end of day
                    day_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    start_rfc = day_start.strftime('%Y-%m-%dT%H:%M:%SZ')
                    end_rfc = day_end.strftime('%Y-%m-%dT%H:%M:%SZ')
                    filter_str = f'createTime > "{start_rfc}" AND createTime < "{end_rfc}"'
                
                request_params["filter"] = filter_str
                logger.debug(f"Using date filter: {filter_str}")
                
            except Exception as filter_error:
                logger.warning(f"Failed to create date filter, proceeding without it: {filter_error}")

        logger.debug(f"Request parameters: {request_params}")

        # Make API request
        messages_result = service.spaces().messages().list(**request_params).execute()
        messages = messages_result.get("messages", [])

        logger.info(f"Found {len(messages)} messages in space: {space_name}")
        return messages

    except HttpError as error:
        logger.error(f"An API error occurred while fetching messages: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching messages: {e}", exc_info=True)
        return None


def list_space_messages_detailed(
    service: GoogleChatService,
    space_name: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page_size: int = 100,
    order_by: str = "createTime desc"
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists messages from a specific Google Chat space with detailed sender information.
    Uses the fields parameter to request all available information.
    """
    logger.info(f"Fetching detailed messages from space: {space_name}")

    try:
        # Prepare request parameters
        request_params = {
            "parent": space_name,
            "pageSize": page_size,
            "orderBy": order_by,
            # Request all available fields including sender details
            "fields": "messages(name,text,createTime,sender(name,displayName,type,email,domainId),thread)"
        }
        
        # Add date filter if provided
        if start_date:
            try:
                if end_date:
                    start_rfc = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    end_rfc = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    filter_str = f'createTime > "{start_rfc}" AND createTime < "{end_rfc}"'
                else:
                    day_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    start_rfc = day_start.strftime('%Y-%m-%dT%H:%M:%SZ')
                    end_rfc = day_end.strftime('%Y-%m-%dT%H:%M:%SZ')
                    filter_str = f'createTime > "{start_rfc}" AND createTime < "{end_rfc}"'
                
                request_params["filter"] = filter_str
                logger.debug(f"Using date filter: {filter_str}")
                
            except Exception as filter_error:
                logger.warning(f"Failed to create date filter, proceeding without it: {filter_error}")

        logger.debug(f"Request parameters: {request_params}")

        # Make API request
        messages_result = service.spaces().messages().list(**request_params).execute()
        messages = messages_result.get("messages", [])

        logger.info(f"Found {len(messages)} messages in space: {space_name}")
        
        # Log what we actually got for debugging
        if messages and logger.isEnabledFor(logging.DEBUG):
            sample_msg = messages[0]
            logger.debug(f"Sample message structure: {json.dumps(sample_msg, indent=2)}")
        
        return messages

    except HttpError as error:
        logger.error(f"An API error occurred while fetching messages: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching messages: {e}", exc_info=True)
        return None


def get_message_details(
    service: GoogleChatService,
    message_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get details for a specific Google Chat message.

    Args:
        service: Google Chat API service instance
        message_name: The name/identifier of the message (e.g., 'spaces/space_id/messages/message_id')

    Returns:
        Message object with details, or None if an error occurs
    """
    logger.info(f"Fetching details for message: {message_name}")

    try:
        message = service.spaces().messages().get(name=message_name).execute()
        logger.info(f"Successfully retrieved message details for: {message_name}")
        return message

    except HttpError as error:
        logger.error(f"An API error occurred while fetching message details: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching message details: {e}", exc_info=True)
        return None


def send_message(
    service: GoogleChatService,
    space_name: str,
    message_text: str,
    thread_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Send a message to a Google Chat space.

    Args:
        service: Google Chat API service instance
        space_name: The name/identifier of the space to send message to
        message_text: The text content of the message
        thread_key: Optional thread key to reply to a specific thread

    Returns:
        Created message object, or None if an error occurs
    """
    logger.info(f"Sending message to space: {space_name}")

    try:
        # Prepare message body
        message_body = {
            "text": message_text
        }

        # Prepare request parameters
        request_params = {
            "parent": space_name,
            "body": message_body
        }
        
        if thread_key:
            request_params["threadKey"] = thread_key

        # Send message
        created_message = service.spaces().messages().create(**request_params).execute()
        
        logger.info(f"Successfully sent message to space: {space_name}")
        return created_message

    except HttpError as error:
        logger.error(f"An API error occurred while sending message: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending message: {e}", exc_info=True)
        return None


# === MEMBER MANAGEMENT FUNCTIONS ===

def list_space_members(
    service: GoogleChatService,
    space_name: str,
    page_size: int = 100
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists members of a specific Google Chat space.

    Args:
        service: Google Chat API service instance
        space_name: The name/identifier of the space
        page_size: Maximum number of members to return per page

    Returns:
        List of member objects, or None if an error occurs
    """
    logger.info(f"Fetching members for space: {space_name}")

    try:
        members_result = service.spaces().members().list(
            parent=space_name,
            pageSize=page_size
        ).execute()
        
        members = members_result.get("memberships", [])
        logger.info(f"Found {len(members)} members in space: {space_name}")
        return members

    except HttpError as error:
        logger.error(f"An API error occurred while fetching space members: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching space members: {e}", exc_info=True)
        return None


def list_space_members_detailed(
    service: GoogleChatService,
    space_name: str,
    page_size: int = 100
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists members of a specific Google Chat space with detailed information.
    """
    logger.info(f"Fetching detailed members for space: {space_name}")

    try:
        members_result = service.spaces().members().list(
            parent=space_name,
            pageSize=page_size,
            # Request all available fields
            fields="memberships(name,member(name,displayName,type,email,domainId),createTime,role)"
        ).execute()
        
        members = members_result.get("memberships", [])
        logger.info(f"Found {len(members)} members in space: {space_name}")
        
        # Log what we actually got for debugging
        if members and logger.isEnabledFor(logging.DEBUG):
            sample_member = members[0]
            logger.debug(f"Sample member structure: {json.dumps(sample_member, indent=2)}")
            
        return members

    except HttpError as error:
        logger.error(f"An API error occurred while fetching space members: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching space members: {e}", exc_info=True)
        return None


# === USER DETAIL FUNCTIONS ===

def get_user_details(
    service: GoogleChatService,
    user_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get details for a specific user.
    
    Args:
        service: Google Chat API service instance
        user_name: The name/identifier of the user (e.g., 'users/user_id')
    
    Returns:
        User object with details, or None if an error occurs
    """
    logger.info(f"Fetching details for user: {user_name}")
    
    try:
        # Try to get user details using the spaces.members.get endpoint
        # This might work better than users.get for some cases
        user = service.users().get(name=user_name).execute()
        logger.info(f"Successfully retrieved user details for: {user_name}")
        return user
    except HttpError as error:
        # If direct user lookup fails, return None
        logger.debug(f"Could not fetch user details: {error}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching user details: {e}")
        return None


def get_space_member_details(
    service: GoogleChatService,
    member_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get details for a specific space member.
    
    Args:
        service: Google Chat API service instance
        member_name: The full member name (e.g., 'spaces/space_id/members/member_id')
    
    Returns:
        Member object with details, or None if an error occurs
    """
    logger.info(f"Fetching member details for: {member_name}")
    
    try:
        member = service.spaces().members().get(name=member_name).execute()
        logger.info(f"Successfully retrieved member details")
        return member
    except HttpError as error:
        logger.debug(f"Could not fetch member details: {error}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching member details: {e}")
        return None


def list_space_messages_with_user_details(
    service: GoogleChatService,
    space_name: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page_size: int = 100,
    order_by: str = "createTime desc",
    fetch_user_details: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """
    Lists messages from a specific Google Chat space with optional user detail fetching.
    
    This is an enhanced version that attempts to fetch user display names.
    """
    messages = list_space_messages(
        service, space_name, start_date, end_date, page_size, order_by
    )
    
    if not messages or not fetch_user_details:
        return messages
    
    # Try to enhance messages with user details
    user_cache = {}  # Cache to avoid repeated lookups
    
    for message in messages:
        sender = message.get('sender', {})
        sender_name = sender.get('name', '')
        
        # If we don't have displayName but have a user name, try to fetch it
        if sender_name and not sender.get('displayName') and sender_name.startswith('users/'):
            if sender_name not in user_cache:
                # Try to get user details
                user_details = get_user_details(service, sender_name)
                if user_details:
                    user_cache[sender_name] = user_details.get('displayName', sender_name)
                else:
                    # If direct lookup fails, extract user ID
                    user_cache[sender_name] = sender_name.split('/')[-1]
            
            # Update the sender info
            sender['displayName'] = user_cache[sender_name]
    
    return messages