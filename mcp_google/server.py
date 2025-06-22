"""
Gmail, Calendar, and Google Chat MCP Server Implementation

This module provides a Model Context Protocol server for interacting with Gmail, Google Calendar, and Google Chat.
It exposes Gmail messages, Calendar events, and Chat spaces/messages as resources and provides tools for managing all three.
"""

import re
from datetime import datetime, time
from typing import Optional, List

from mcp.server.fastmcp import FastMCP

from mcp_google.config import settings
from mcp_google.gmail import (
    create_draft,
    get_gmail_service,
    get_headers_dict,
    get_labels,
    get_message,
    get_thread,
    list_messages,
    modify_message_labels,
    parse_message_body,
    search_messages,
)
from mcp_google.gmail import send_email as gmail_send_email

from mcp_google.calendar import (
    get_calendar_service,
    find_calendars,
    create_calendar,
    find_events,
    create_event,
    quick_add_event,
    update_event,
    delete_event,
    get_event,
    project_recurring_events,
    analyze_busyness,
    find_availability,
)
from mcp_google.calendar_models import (
    EventCreateRequest,
    EventDateTime,
    EventUpdateRequest,
)

from mcp_google.google_chat import (
    get_google_chat_service,
    list_chat_spaces,
    get_space_details,
    list_space_messages,
    list_space_messages_detailed,
    get_message_details,
    send_message,
    list_space_members,
    list_space_members_detailed,
)

# Initialize the Gmail service
gmail_service = get_gmail_service(
    credentials_path=settings.gmail_credentials_path, 
    token_path=settings.gmail_token_path, 
    scopes=settings.gmail_scopes
)

# Initialize the Calendar service
calendar_service = get_calendar_service(
    credentials_path=settings.calendar_credentials_path,
    token_path=settings.calendar_token_path,
    scopes=settings.calendar_scopes
)

# Initialize the Google Chat service
google_chat_service = get_google_chat_service(
    credentials_path=settings.google_chat_credentials_path,
    token_path=settings.google_chat_token_path,
    scopes=settings.google_chat_scopes
)

mcp = FastMCP(
    "Gmail, Calendar, and Google Chat MCP Server",
    instructions="Access and interact with Gmail, Google Calendar, and Google Chat. You can get messages, threads, search emails, send or compose new messages, manage calendar events, create meetings, analyze calendar data, list chat spaces, view chat messages, and send messages to Google Chat spaces.",
)

EMAIL_PREVIEW_LENGTH = 200


# === HELPER FUNCTIONS ===

def format_gmail_message(message):
    """Format a Gmail message for display."""
    headers = get_headers_dict(message)
    body = parse_message_body(message)

    from_header = headers.get("From", "Unknown")
    to_header = headers.get("To", "Unknown")
    subject = headers.get("Subject", "No Subject")
    date = headers.get("Date", "Unknown Date")

    return f"""
From: {from_header}
To: {to_header}
Subject: {subject}
Date: {date}

{body}
"""


def format_calendar_event(event):
    """Format a Calendar event for display."""
    start_str = "Unknown"
    end_str = "Unknown"
    
    if event.start:
        if event.start.dateTime:
            start_str = event.start.dateTime.strftime("%Y-%m-%d %H:%M:%S")
        elif event.start.date:
            start_str = event.start.date.strftime("%Y-%m-%d") + " (All Day)"
    
    if event.end:
        if event.end.dateTime:
            end_str = event.end.dateTime.strftime("%Y-%m-%d %H:%M:%S")
        elif event.end.date:
            end_str = event.end.date.strftime("%Y-%m-%d") + " (All Day)"

    attendees_str = ""
    if event.attendees:
        attendees_list = [att.email for att in event.attendees if att.email]
        if attendees_list:
            attendees_str = f"\nAttendees: {', '.join(attendees_list)}"

    return f"""
Title: {event.summary or 'No Title'}
Start: {start_str}
End: {end_str}
Location: {event.location or 'No location'}
Description: {event.description or 'No description'}{attendees_str}
"""


def format_chat_space(space):
    """Format a Google Chat space for display with better handling of optional fields."""
    space_name = space.get('name', 'Unknown')
    display_name = space.get('displayName', '')
    
    # Handle spaces without display names (like direct messages)
    if not display_name:
        space_type = space.get('type', 'Unknown type')
        if space_type == 'ROOM':
            display_name = 'Unnamed Room'
        elif space_type == 'DM':
            display_name = 'Direct Message'
        else:
            display_name = f'Unnamed {space_type}'
    
    space_type = space.get('type', 'Unknown type')
    
    # Member count might not be available for all space types
    member_count = space.get('memberCount')
    member_info = f"Member Count: {member_count}" if member_count else "Member Count: Not available"
    
    create_time = space.get('createTime', 'Not available')
    
    # Add more details if available
    details = f"""
Display Name: {display_name}
Space ID: {space_name}
Type: {space_type}
{member_info}
Created: {create_time}"""
    
    # Add additional space attributes if present
    if space.get('singleUserBotDm'):
        details += "\nBot DM: Yes"
    if space.get('threaded'):
        details += "\nThreaded: Yes"
    if space.get('externalUserAllowed'):
        details += "\nExternal Users: Allowed"
        
    return details


def format_chat_message(message):
    """Format a Google Chat message for display with better error handling."""
    sender = message.get('sender', {})
    
    # Better handling for sender information
    sender_name = sender.get('displayName', sender.get('name', 'Anonymous'))
    sender_type = sender.get('type', 'USER')
    
    # Some messages might not have displayName, try to extract from name field
    if (sender_name == 'Anonymous' or sender_name.startswith('users/')) and 'name' in sender:
        # Extract user ID from name like 'users/12345'
        user_id = sender['name'].split('/')[-1] if '/' in sender['name'] else sender['name']
        # Make it more readable
        if len(user_id) > 10:
            sender_name = f"User {user_id[:4]}...{user_id[-4:]}"
        else:
            sender_name = f"User {user_id}"
    
    message_text = message.get('text', 'No text content')
    create_time = message.get('createTime', 'Unknown time')
    message_name = message.get('name', 'Unknown')
    
    # Check if it's a system message or bot message
    if sender_type == 'BOT':
        sender_name = f"{sender_name} (Bot)"
    elif sender_type == 'HUMAN':
        # Don't add (User) suffix if we already have a readable name
        if not sender_name.startswith('User '):
            sender_name = f"{sender_name} (User)"
    
    return f"""
From: {sender_name}
Time: {create_time}
Message ID: {message_name}
Text: {message_text}
"""


def validate_date_format(date_str):
    """Validate that a date string is in the format YYYY/MM/DD."""
    if not date_str:
        return True

    if not re.match(r"^\d{4}/\d{2}/\d{2}$", date_str):
        return False

    try:
        datetime.strptime(date_str, "%Y/%m/%d")
        return True
    except ValueError:
        return False


# === GMAIL RESOURCES ===

@mcp.resource("gmail://messages/{message_id}")
def get_email_message(message_id: str) -> str:
    """Get the content of an email message by its ID."""
    message = get_message(gmail_service, message_id, user_id=settings.gmail_user_id)
    formatted_message = format_gmail_message(message)
    return formatted_message


@mcp.resource("gmail://threads/{thread_id}")
def get_email_thread(thread_id: str) -> str:
    """Get all messages in an email thread by thread ID."""
    thread = get_thread(gmail_service, thread_id, user_id=settings.gmail_user_id)
    messages = thread.get("messages", [])

    result = f"Email Thread (ID: {thread_id})\n"
    for i, message in enumerate(messages, 1):
        result += f"\n--- Message {i} ---\n"
        result += format_gmail_message(message)

    return result


# === CALENDAR RESOURCES ===

@mcp.resource("calendar://events/{event_id}")
def get_calendar_event(event_id: str) -> str:
    """Get the content of a calendar event by its ID from the primary calendar."""
    event = get_event(calendar_service, event_id, "primary")
    if event:
        return format_calendar_event(event)
    else:
        return f"Event {event_id} not found."


# === GOOGLE CHAT RESOURCES ===

@mcp.resource("chat://spaces/{space_id}")
def get_chat_space(space_id: str) -> str:
    """Get the details of a Google Chat space by its ID."""
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    space = get_space_details(google_chat_service, space_name)
    if space:
        return format_chat_space(space)
    else:
        return f"Chat space {space_id} not found."


@mcp.resource("chat://spaces/{space_id}/messages/{message_id}")
def get_chat_message(space_id: str, message_id: str) -> str:
    """Get the content of a Google Chat message by its space and message ID."""
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    message_name = f"{space_name}/messages/{message_id}"
    message = get_message_details(google_chat_service, message_name)
    if message:
        return format_chat_message(message)
    else:
        return f"Chat message {message_id} not found in space {space_id}."


# === GMAIL TOOLS ===

@mcp.tool()
def compose_email(
    to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None
) -> str:
    """Compose a new email draft."""
    sender = gmail_service.users().getProfile(userId=settings.gmail_user_id).execute().get("emailAddress")
    draft = create_draft(
        gmail_service, sender=sender, to=to, subject=subject, body=body, user_id=settings.gmail_user_id, cc=cc, bcc=bcc
    )

    draft_id = draft.get("id")
    return f"""
Email draft created with ID: {draft_id}
To: {to}
Subject: {subject}
CC: {cc or ""}
BCC: {bcc or ""}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{"..." if len(body) > EMAIL_PREVIEW_LENGTH else ""}
"""


@mcp.tool()
def send_email(
    to: str, subject: str, body: str, cc: Optional[str] = None, bcc: Optional[str] = None
) -> str:
    """Compose and send an email."""
    sender = gmail_service.users().getProfile(userId=settings.gmail_user_id).execute().get("emailAddress")
    message = gmail_send_email(
        gmail_service, sender=sender, to=to, subject=subject, body=body, user_id=settings.gmail_user_id, cc=cc, bcc=bcc
    )

    message_id = message.get("id")
    return f"""
Email sent successfully with ID: {message_id}
To: {to}
Subject: {subject}
CC: {cc or ""}
BCC: {bcc or ""}
Body: {body[:EMAIL_PREVIEW_LENGTH]}{"..." if len(body) > EMAIL_PREVIEW_LENGTH else ""}
"""


@mcp.tool()
def search_emails(
    from_email: Optional[str] = None,
    to_email: Optional[str] = None,
    subject: Optional[str] = None,
    has_attachment: bool = False,
    is_unread: bool = False,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    label: Optional[str] = None,
    max_results: int = 10,
) -> str:
    """Search for emails using specific search criteria."""
    if after_date and not validate_date_format(after_date):
        return f"Error: after_date '{after_date}' is not in the required format YYYY/MM/DD"

    if before_date and not validate_date_format(before_date):
        return f"Error: before_date '{before_date}' is not in the required format YYYY/MM/DD"

    messages = search_messages(
        gmail_service,
        user_id=settings.gmail_user_id,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        has_attachment=has_attachment,
        is_unread=is_unread,
        after=after_date,
        before=before_date,
        labels=[label] if label else None,
        max_results=max_results,
    )

    result = f"Found {len(messages)} messages matching criteria:\n"

    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(gmail_service, msg_id, user_id=settings.gmail_user_id)
        headers = get_headers_dict(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        result += f"\nMessage ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"

    return result


@mcp.tool()
def query_emails(query: str, max_results: int = 10) -> str:
    """Search for emails using a raw Gmail query string."""
    messages = list_messages(gmail_service, user_id=settings.gmail_user_id, max_results=max_results, query=query)

    result = f'Found {len(messages)} messages matching query: "{query}"\n'

    for msg_info in messages:
        msg_id = msg_info.get("id")
        message = get_message(gmail_service, msg_id, user_id=settings.gmail_user_id)
        headers = get_headers_dict(message)

        from_header = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No Subject")
        date = headers.get("Date", "Unknown Date")

        result += f"\nMessage ID: {msg_id}\n"
        result += f"From: {from_header}\n"
        result += f"Subject: {subject}\n"
        result += f"Date: {date}\n"

    return result


@mcp.tool()
def list_available_labels() -> str:
    """Get all available Gmail labels for the user."""
    labels = get_labels(gmail_service, user_id=settings.gmail_user_id)

    result = "Available Gmail Labels:\n"
    for label in labels:
        label_id = label.get("id", "Unknown")
        name = label.get("name", "Unknown")
        type_info = label.get("type", "user")

        result += f"\nLabel ID: {label_id}\n"
        result += f"Name: {name}\n"
        result += f"Type: {type_info}\n"

    return result


@mcp.tool()
def mark_message_read(message_id: str) -> str:
    """Mark a message as read by removing the UNREAD label."""
    result = modify_message_labels(
        gmail_service, user_id=settings.gmail_user_id, message_id=message_id, remove_labels=["UNREAD"], add_labels=[]
    )

    headers = get_headers_dict(result)
    subject = headers.get("Subject", "No Subject")

    return f"""
Message marked as read:
ID: {message_id}
Subject: {subject}
"""


@mcp.tool()
def get_emails(message_ids: list[str]) -> str:
    """Get the content of multiple email messages by their IDs."""
    if not message_ids:
        return "No message IDs provided."

    retrieved_emails = []
    error_emails = []

    for msg_id in message_ids:
        try:
            message = get_message(gmail_service, msg_id, user_id=settings.gmail_user_id)
            retrieved_emails.append((msg_id, message))
        except Exception as e:
            error_emails.append((msg_id, str(e)))

    result = f"Retrieved {len(retrieved_emails)} emails:\n"

    for i, (msg_id, message) in enumerate(retrieved_emails, 1):
        result += f"\n--- Email {i} (ID: {msg_id}) ---\n"
        result += format_gmail_message(message)

    if error_emails:
        result += f"\n\nFailed to retrieve {len(error_emails)} emails:\n"
        for i, (msg_id, error) in enumerate(error_emails, 1):
            result += f"\n--- Email {i} (ID: {msg_id}) ---\n"
            result += f"Error: {error}\n"

    return result


# === CALENDAR TOOLS ===

@mcp.tool()
def list_calendars(min_access_role: Optional[str] = None) -> str:
    """Get all available calendars for the user."""
    calendars_response = find_calendars(calendar_service, min_access_role=min_access_role)
    
    if not calendars_response:
        return "Error retrieving calendars."

    result = "Available Calendars:\n"
    for calendar in calendars_response.items:
        result += f"\nCalendar ID: {calendar.id}\n"
        result += f"Name: {calendar.summary}\n"
        result += f"Access Role: {calendar.accessRole}\n"
        result += f"Primary: {calendar.primary}\n"

    return result


@mcp.tool()
def search_calendar_events(
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 50
) -> str:
    """Search for calendar events using various criteria."""
    time_min_dt = None
    time_max_dt = None
    
    if time_min:
        try:
            time_min_dt = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
        except ValueError:
            return f"Error: Invalid time_min format. Use ISO format like '2024-01-01T00:00:00Z'"
    
    if time_max:
        try:
            time_max_dt = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
        except ValueError:
            return f"Error: Invalid time_max format. Use ISO format like '2024-01-01T00:00:00Z'"

    events_response = find_events(
        calendar_service,
        calendar_id=calendar_id,
        time_min=time_min_dt,
        time_max=time_max_dt,
        query=query,
        max_results=max_results
    )

    if not events_response:
        return "Error retrieving events."

    result = f"Found {len(events_response.items)} events:\n"

    for event in events_response.items:
        result += f"\n--- Event ID: {event.id} ---\n"
        result += format_calendar_event(event)

    return result


@mcp.tool()
def create_calendar_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary"
) -> str:
    """Create a new calendar event."""
    try:
        start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
    except ValueError:
        return "Error: Invalid datetime format. Use ISO format like '2024-01-01T10:00:00Z'"

    event_data = EventCreateRequest(
        summary=summary,
        start=EventDateTime(dateTime=start_dt),
        end=EventDateTime(dateTime=end_dt),
        description=description,
        location=location,
        attendees=attendees or []
    )

    created_event = create_event(calendar_service, event_data, calendar_id)

    if created_event:
        return f"""
Event created successfully!
Event ID: {created_event.id}
Title: {created_event.summary}
Start: {start_datetime}
End: {end_datetime}
Location: {location or "No location"}
Description: {description or "No description"}
"""
    else:
        return "Error creating event."


@mcp.tool()
def quick_create_event(
    text: str,
    calendar_id: str = "primary"
) -> str:
    """Create an event using Google's natural language parser."""
    created_event = quick_add_event(calendar_service, text, calendar_id)

    if created_event:
        return f"""
Event created successfully using quick add!
Event ID: {created_event.id}
Title: {created_event.summary}
Parsed from: "{text}"
"""
    else:
        return f"Error creating event from text: '{text}'"


@mcp.tool()
def update_calendar_event(
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    calendar_id: str = "primary"
) -> str:
    """Update an existing calendar event."""
    update_data = EventUpdateRequest()

    if summary is not None:
        update_data.summary = summary
    if description is not None:
        update_data.description = description
    if location is not None:
        update_data.location = location

    if start_datetime:
        try:
            start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
            update_data.start = EventDateTime(dateTime=start_dt)
        except ValueError:
            return "Error: Invalid start_datetime format. Use ISO format like '2024-01-01T10:00:00Z'"

    if end_datetime:
        try:
            end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
            update_data.end = EventDateTime(dateTime=end_dt)
        except ValueError:
            return "Error: Invalid end_datetime format. Use ISO format like '2024-01-01T10:00:00Z'"

    updated_event = update_event(calendar_service, event_id, update_data, calendar_id)

    if updated_event:
        return f"""
Event updated successfully!
Event ID: {updated_event.id}
Title: {updated_event.summary}
"""
    else:
        return f"Error updating event {event_id}."


@mcp.tool()
def delete_calendar_event(
    event_id: str,
    calendar_id: str = "primary"
) -> str:
    """Delete a calendar event."""
    success = delete_event(calendar_service, event_id, calendar_id)

    if success:
        return f"Event {event_id} deleted successfully."
    else:
        return f"Error deleting event {event_id}."


@mcp.tool()
def analyze_calendar_busyness(
    start_date: str,
    end_date: str,
    calendar_id: str = "primary"
) -> str:
    """Analyze calendar busyness (event count and duration) for each day in a date range."""
    try:
        start_dt = datetime.fromisoformat(start_date + "T00:00:00Z")
        end_dt = datetime.fromisoformat(end_date + "T23:59:59Z")
    except ValueError:
        return "Error: Invalid date format. Use YYYY-MM-DD format."

    busyness_data = analyze_busyness(calendar_service, start_dt, end_dt, calendar_id)

    if not busyness_data:
        return "No events found in the specified date range."

    result = f"Calendar busyness analysis from {start_date} to {end_date}:\n"

    for date_obj, stats in busyness_data.items():
        date_str = date_obj.strftime("%Y-%m-%d")
        event_count = stats['event_count']
        duration_hours = stats['total_duration_minutes'] / 60.0

        result += f"\n{date_str}: {event_count} events, {duration_hours:.1f} hours scheduled"

    return result


@mcp.tool()
def project_recurring_calendar_events(
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
    event_query: Optional[str] = None
) -> str:
    """Project recurring events to show all occurrences in a date range."""
    try:
        start_dt = datetime.fromisoformat(start_date + "T00:00:00Z")
        end_dt = datetime.fromisoformat(end_date + "T23:59:59Z")
    except ValueError:
        return "Error: Invalid date format. Use YYYY-MM-DD format."

    occurrences = project_recurring_events(calendar_service, start_dt, end_dt, calendar_id, event_query)

    if not occurrences:
        return "No recurring event occurrences found in the specified date range."

    result = f"Projected recurring event occurrences from {start_date} to {end_date}:\n"

    for occurrence in occurrences:
        start_str = occurrence.occurrence_start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = occurrence.occurrence_end.strftime("%Y-%m-%d %H:%M:%S")
        result += f"\n{occurrence.original_summary}: {start_str} - {end_str}"

    return result


@mcp.tool()
def check_availability(
    calendar_ids: List[str],
    start_datetime: str,
    end_datetime: str
) -> str:
    """Check free/busy status for multiple calendars in a time range."""
    try:
        start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
    except ValueError:
        return "Error: Invalid datetime format. Use ISO format like '2024-01-01T10:00:00Z'"

    availability_data = find_availability(calendar_service, start_dt, end_dt, calendar_ids)

    if not availability_data:
        return "Error retrieving availability data."

    result = f"Availability from {start_datetime} to {end_datetime}:\n"

    for cal_id, data in availability_data.items():
        result += f"\nCalendar: {cal_id}\n"
        
        if data.get('errors'):
            result += f"Errors: {data['errors']}\n"
        
        busy_periods = data.get('busy', [])
        if busy_periods:
            result += "Busy periods:\n"
            for period in busy_periods:
                start_str = period['start'].strftime("%Y-%m-%d %H:%M:%S")
                end_str = period['end'].strftime("%Y-%m-%d %H:%M:%S")
                result += f"  {start_str} - {end_str}\n"
        else:
            result += "No busy periods found.\n"

    return result


# === GOOGLE CHAT TOOLS ===

@mcp.tool()
def list_google_chat_spaces(max_results: int = 50) -> str:
    """List all Google Chat spaces the authenticated user has access to."""
    spaces = list_chat_spaces(google_chat_service, page_size=max_results)
    
    if not spaces:
        return "No chat spaces found or error retrieving spaces."

    result = f"Found {len(spaces)} Google Chat spaces:\n"

    for i, space in enumerate(spaces, 1):
        space_name = space.get('name', 'Unknown')
        display_name = space.get('displayName', 'No display name')
        space_type = space.get('type', 'Unknown type')
        member_count = space.get('memberCount', 'Unknown')
        
        # Handle spaces without display names
        if not display_name:
            if space_type == 'ROOM':
                display_name = 'Unnamed Room'
            elif space_type == 'DM':
                display_name = 'Direct Message'
            else:
                display_name = f'Unnamed {space_type}'
        
        result += f"\n{i}. {display_name}\n"
        result += f"   Space ID: {space_name}\n"
        result += f"   Type: {space_type}\n"
        result += f"   Members: {member_count}\n"

    return result


@mcp.tool()
def get_google_chat_space_details(space_id: str) -> str:
    """Get detailed information about a specific Google Chat space."""
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    space = get_space_details(google_chat_service, space_name)
    
    if not space:
        return f"Error retrieving details for space: {space_id}"

    return format_chat_space(space)


@mcp.tool()
def list_google_chat_messages(
    space_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 50,
    use_detailed: bool = True
) -> str:
    """List messages from a specific Google Chat space with optional date filtering.
    
    Args:
        space_id: The space ID (can be just the ID or full 'spaces/ID' format)
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format (if not provided, uses start_date as single day)
        max_results: Maximum number of messages to return
        use_detailed: Whether to use the detailed API call that requests more fields
    """
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    
    start_datetime = None
    end_datetime = None
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            if end_date:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return "Error: Dates must be in YYYY-MM-DD format (e.g., '2024-03-22')"
    
    # Use detailed version if requested
    if use_detailed:
        messages = list_space_messages_detailed(
            google_chat_service,
            space_name,
            start_date=start_datetime,
            end_date=end_datetime,
            page_size=max_results
        )
    else:
        messages = list_space_messages(
            google_chat_service,
            space_name,
            start_date=start_datetime,
            end_date=end_datetime,
            page_size=max_results
        )
    
    if not messages:
        return f"No messages found in space {space_id} for the specified criteria."

    result = f"Found {len(messages)} messages in space {space_id}:\n"

    for i, message in enumerate(messages, 1):
        result += f"\n--- Message {i} ---\n"
        result += format_chat_message(message)

    return result


@mcp.tool()
def get_google_chat_message_details(space_id: str, message_id: str) -> str:
    """Get detailed information about a specific Google Chat message."""
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    message_name = f"{space_name}/messages/{message_id}"
    
    message = get_message_details(google_chat_service, message_name)
    
    if not message:
        return f"Error retrieving message {message_id} from space {space_id}"

    return format_chat_message(message)


@mcp.tool()
def send_google_chat_message(
    space_id: str,
    message_text: str,
    thread_key: Optional[str] = None
) -> str:
    """Send a message to a Google Chat space.
    
    Args:
        space_id: The space ID (can be just the ID or full 'spaces/ID' format)
        message_text: The text content to send
        thread_key: Optional thread key to reply to a specific thread
    """
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    
    created_message = send_message(
        google_chat_service,
        space_name,
        message_text,
        thread_key=thread_key
    )
    
    if not created_message:
        return f"Error sending message to space {space_id}"

    message_name = created_message.get('name', 'Unknown')
    create_time = created_message.get('createTime', 'Unknown')
    
    return f"""
Message sent successfully!
Message ID: {message_name}
Space: {space_name}
Time: {create_time}
Text: {message_text}
"""


@mcp.tool()
def list_google_chat_space_members(space_id: str, max_results: int = 100, use_detailed: bool = True) -> str:
    """List all members of a specific Google Chat space."""
    space_name = f"spaces/{space_id}" if not space_id.startswith("spaces/") else space_id
    
    # Use detailed version if requested
    if use_detailed:
        members = list_space_members_detailed(google_chat_service, space_name, page_size=max_results)
    else:
        members = list_space_members(google_chat_service, space_name, page_size=max_results)
    
    if not members:
        return f"No members found in space {space_id} or error retrieving members."

    result = f"Found {len(members)} members in space {space_id}:\n"

    for i, member in enumerate(members, 1):
        member_info = member.get('member', {})
        member_name = member_info.get('name', '')
        member_display = member_info.get('displayName', '')
        member_type = member_info.get('type', 'Unknown type')
        member_email = member_info.get('email', '')
        
        # If no display name, try to extract from name
        if not member_display and member_name:
            if member_name.startswith('users/'):
                user_id = member_name.split('/')[-1]
                # Make it more readable
                if len(user_id) > 10:
                    member_display = f"User {user_id[:4]}...{user_id[-4:]}"
                else:
                    member_display = f"User {user_id}"
            else:
                member_display = member_name
        
        result += f"\n{i}. {member_display or 'Unknown member'} ({member_type})"
        if member_email:
            result += f" - {member_email}"
        result += f"\n   ID: {member_name}\n"

    return result


if __name__ == "__main__":
    mcp.run()