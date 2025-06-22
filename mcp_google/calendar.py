"""
This module provides utilities for authenticating with and using the Google Calendar API.
Includes calendar management, event operations, and analysis functions.
"""

import base64
import json
import logging
import os
from datetime import datetime, date, timedelta, time, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from dateutil import parser as date_parser
from dateutil import rrule

from .calendar_models import (
    GoogleCalendarEvent,
    EventsResponse,
    EventCreateRequest,
    EventDateTime,
    EventAttendee,
    EventUpdateRequest,
    CalendarListResponse,
    CalendarListEntry,
    ProjectedEventOccurrence
)

# Default settings
DEFAULT_CREDENTIALS_PATH = "credentials.json"
DEFAULT_TOKEN_PATH = "calendar_token.json"
DEFAULT_USER_ID = "me"

# Google Calendar API scopes
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

# For simpler testing
CALENDAR_READONLY_SCOPE = ["https://www.googleapis.com/auth/calendar.readonly"]

# Type alias for the Calendar service
CalendarService = Resource

logger = logging.getLogger(__name__)


def get_calendar_service(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
    scopes: List[str] = CALENDAR_SCOPES,
) -> CalendarService:
    """
    Authenticate with Google Calendar API and return the service object.

    Args:
        credentials_path: Path to the credentials JSON file
        token_path: Path to save/load the token
        scopes: OAuth scopes to request

    Returns:
        Authenticated Google Calendar API service
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

    # Build the Calendar service
    return build("calendar", "v3", credentials=creds)


# === CALENDAR MANAGEMENT FUNCTIONS ===

def find_calendars(
    service: CalendarService,
    min_access_role: Optional[str] = None
) -> Optional[CalendarListResponse]:
    """
    Lists the calendars on the user's calendar list.

    Args:
        service: Calendar API service instance
        min_access_role: The minimum access role for the user in the returned calendars

    Returns:
        A CalendarListResponse object containing the list of calendars, or None if an error occurs
    """
    logger.info(f"Fetching calendar list. Min access role: {min_access_role}")

    try:
        calendar_list = service.calendarList().list(
            minAccessRole=min_access_role
        ).execute()

        logger.info(f"Found {len(calendar_list.get('items', []))} calendars in the list.")
        parsed_list = CalendarListResponse(**calendar_list)
        return parsed_list

    except HttpError as error:
        logger.error(f"An API error occurred while fetching calendar list: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching calendar list: {e}", exc_info=True)
        return None


def create_calendar(
    service: CalendarService,
    summary: str
) -> Optional[CalendarListEntry]:
    """
    Creates a new secondary calendar.

    Args:
        service: Calendar API service instance
        summary: The title for the new calendar

    Returns:
        A CalendarListEntry object representing the created calendar, or None if an error occurs
    """
    logger.info(f"Attempting to create a new calendar with summary: '{summary}'")

    calendar_body = {
        'summary': summary
    }

    try:
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        logger.info(f"Successfully created calendar with ID: {created_calendar.get('id')}")

        parsed_calendar = CalendarListEntry(**created_calendar)
        return parsed_calendar

    except HttpError as error:
        logger.error(f"An API error occurred while creating calendar '{summary}': {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating calendar '{summary}': {e}", exc_info=True)
        return None


# === EVENT MANAGEMENT FUNCTIONS ===

def find_events(
    service: CalendarService,
    calendar_id: str = 'primary',
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    query: Optional[str] = None,
    max_results: int = 50,
    single_events: bool = True,
    order_by: str = 'startTime',
    show_deleted: bool = False
) -> Optional[EventsResponse]:
    """
    Finds events in a specified calendar based on various criteria.

    Args:
        service: Calendar API service instance
        calendar_id: Calendar identifier
        time_min: Start of the time range (inclusive)
        time_max: End of the time range (exclusive)
        query: Free text search query
        max_results: Maximum number of events to return
        single_events: Whether to expand recurring events into single instances
        order_by: The order of the events returned
        show_deleted: Whether to include deleted events

    Returns:
        An EventsResponse object containing the list of events, or None if an error occurs
    """
    # Format datetime objects to RFC3339 string format
    time_min_str = time_min.isoformat() + 'Z' if time_min and time_min.tzinfo is None else (time_min.isoformat() if time_min else None)
    time_max_str = time_max.isoformat() + 'Z' if time_max and time_max.tzinfo is None else (time_max.isoformat() if time_max else None)

    list_kwargs = {
        'calendarId': calendar_id,
        'timeMin': time_min_str,
        'timeMax': time_max_str,
        'q': query,
        'maxResults': max_results,
        'singleEvents': single_events,
        'orderBy': order_by,
        'showDeleted': show_deleted,
    }
    # Filter out None values
    list_kwargs = {k: v for k, v in list_kwargs.items() if v is not None}

    logger.info(f"Fetching events from calendar '{calendar_id}' with parameters: {list_kwargs}")

    try:
        events_result = service.events().list(**list_kwargs).execute()
        logger.info(f"Found {len(events_result.get('items', []))} events.")

        events_response = EventsResponse(**events_result)
        return events_response

    except HttpError as error:
        logger.error(f"An API error occurred while finding events: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while finding events: {e}", exc_info=True)
        return None


def create_event(
    service: CalendarService,
    event_data: EventCreateRequest,
    calendar_id: str = 'primary',
    send_notifications: bool = True
) -> Optional[GoogleCalendarEvent]:
    """
    Creates a new event in the specified calendar.

    Args:
        service: Calendar API service instance
        event_data: An EventCreateRequest object containing event details
        calendar_id: Calendar identifier
        send_notifications: Whether to send notifications about the creation to attendees

    Returns:
        A GoogleCalendarEvent object representing the created event, or None if an error occurs
    """
    def format_datetime_field(dt_obj: datetime) -> str:
        if dt_obj.tzinfo is None:
            return dt_obj.isoformat() + 'Z'
        else:
            return dt_obj.isoformat()

    # Construct event body
    event_body: Dict[str, Any] = {}

    if not event_data.start or not event_data.end:
        logger.error("Event creation failed: Start and End times are required.")
        return None

    # Start time
    event_body['start'] = {}
    if event_data.start.dateTime:
        event_body['start']['dateTime'] = format_datetime_field(event_data.start.dateTime)
        if event_data.start.timeZone:
            event_body['start']['timeZone'] = event_data.start.timeZone
    elif event_data.start.date:
        event_body['start']['date'] = str(event_data.start.date)
    else:
        logger.error("Event creation failed: Start time requires either dateTime or date.")
        return None

    # End time
    event_body['end'] = {}
    if event_data.end.dateTime:
        event_body['end']['dateTime'] = format_datetime_field(event_data.end.dateTime)
        if event_data.end.timeZone:
            event_body['end']['timeZone'] = event_data.end.timeZone
    elif event_data.end.date:
        event_body['end']['date'] = str(event_data.end.date)
    else:
        logger.error("Event creation failed: End time requires either dateTime or date.")
        return None

    # Optional fields
    if event_data.summary:
        event_body['summary'] = event_data.summary
    if event_data.description:
        event_body['description'] = event_data.description
    if event_data.location:
        event_body['location'] = event_data.location
    if event_data.attendees:
        event_body['attendees'] = [{'email': email} for email in event_data.attendees]
    if event_data.recurrence:
        event_body['recurrence'] = event_data.recurrence
    if event_data.reminders:
        event_body['reminders'] = event_data.reminders.dict(by_alias=True, exclude_unset=True)

    logger.info(f"Creating event in calendar '{calendar_id}': {event_body.get('summary', '[No Summary]')}")

    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendNotifications=send_notifications
        ).execute()

        logger.info(f"Successfully created event with ID: {created_event.get('id')}")
        parsed_event = GoogleCalendarEvent(**created_event)
        return parsed_event

    except HttpError as error:
        logger.error(f"Google API error while creating event: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating event: {e}", exc_info=True)
        return None


def quick_add_event(
    service: CalendarService,
    text: str,
    calendar_id: str = 'primary',
    send_notifications: bool = False
) -> Optional[GoogleCalendarEvent]:
    """
    Creates an event based on a simple text string using Google's parser.

    Args:
        service: Calendar API service instance
        text: The text description of the event
        calendar_id: Calendar identifier
        send_notifications: Whether to send notifications

    Returns:
        A GoogleCalendarEvent object representing the created event, or None if an error occurs
    """
    logger.info(f"Quick adding event to calendar '{calendar_id}' with text: \"{text}\"")

    try:
        created_event = service.events().quickAdd(
            calendarId=calendar_id,
            text=text,
            sendNotifications=send_notifications
        ).execute()

        logger.info(f"Successfully quick-added event with ID: {created_event.get('id')}")
        parsed_event = GoogleCalendarEvent(**created_event)
        return parsed_event

    except HttpError as error:
        logger.error(f"An API error occurred during quick add: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during quick add: {e}", exc_info=True)
        return None


def update_event(
    service: CalendarService,
    event_id: str,
    update_data: EventUpdateRequest,
    calendar_id: str = 'primary',
    send_notifications: bool = True
) -> Optional[GoogleCalendarEvent]:
    """
    Updates an existing event using patch semantics.

    Args:
        service: Calendar API service instance
        event_id: The ID of the event to update
        update_data: An EventUpdateRequest object containing fields to update
        calendar_id: Calendar identifier
        send_notifications: Whether to send update notifications to attendees

    Returns:
        A GoogleCalendarEvent object representing the updated event, or None if an error occurs
    """
    def format_datetime_field(dt_obj: datetime) -> str:
        if dt_obj.tzinfo is None:
            return dt_obj.isoformat() + 'Z'
        else:
            return dt_obj.isoformat()

    update_body: Dict[str, Any] = {}

    if update_data.summary is not None:
        update_body['summary'] = update_data.summary
    if update_data.description is not None:
        update_body['description'] = update_data.description
    if update_data.location is not None:
        update_body['location'] = update_data.location

    # Handle start time
    if update_data.start is not None:
        start_details = {}
        if update_data.start.dateTime:
            start_details['dateTime'] = format_datetime_field(update_data.start.dateTime)
            if update_data.start.timeZone:
                start_details['timeZone'] = update_data.start.timeZone
        elif update_data.start.date:
            start_details['date'] = str(update_data.start.date)
        if start_details:
            update_body['start'] = start_details

    # Handle end time
    if update_data.end is not None:
        end_details = {}
        if update_data.end.dateTime:
            end_details['dateTime'] = format_datetime_field(update_data.end.dateTime)
            if update_data.end.timeZone:
                end_details['timeZone'] = update_data.end.timeZone
        elif update_data.end.date:
            end_details['date'] = str(update_data.end.date)
        if end_details:
            update_body['end'] = end_details

    # Handle attendees
    if update_data.attendees is not None:
        update_body['attendees'] = [
            attendee.dict(by_alias=True, exclude_unset=True) 
            for attendee in update_data.attendees
        ]

    if not update_body:
        logger.warning(f"Update called for event {event_id} with no fields to update.")
        try:
            existing_event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            return GoogleCalendarEvent(**existing_event)
        except HttpError as e:
            logger.error(f"Failed to retrieve event {event_id} after empty update request: {e}")
            return None

    logger.info(f"Updating event '{event_id}' in calendar '{calendar_id}'.")

    try:
        updated_event = service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=update_body,
            sendNotifications=send_notifications
        ).execute()

        logger.info(f"Successfully updated event '{event_id}'.")
        parsed_event = GoogleCalendarEvent(**updated_event)
        return parsed_event

    except HttpError as error:
        if error.resp.status == 404:
            logger.error(f"Event '{event_id}' not found in calendar '{calendar_id}'.")
        else:
            logger.error(f"Google API error while updating event '{event_id}': {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while updating event '{event_id}': {e}", exc_info=True)
        return None


def delete_event(
    service: CalendarService,
    event_id: str,
    calendar_id: str = 'primary',
    send_notifications: bool = True
) -> bool:
    """
    Deletes an event.

    Args:
        service: Calendar API service instance
        event_id: The ID of the event to delete
        calendar_id: Calendar identifier
        send_notifications: Whether to send deletion notifications to attendees

    Returns:
        True if the event was deleted successfully, False otherwise
    """
    logger.info(f"Attempting to delete event '{event_id}' from calendar '{calendar_id}'.")

    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendNotifications=send_notifications
        ).execute()
        
        logger.info(f"Successfully deleted event '{event_id}'.")
        return True

    except HttpError as error:
        if error.resp.status in [404, 410]:
            logger.error(f"Event '{event_id}' not found or already deleted in calendar '{calendar_id}'.")
        else:
            logger.error(f"Google API error while deleting event '{event_id}': {error}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting event '{event_id}': {e}", exc_info=True)
        return False


def get_event(
    service: CalendarService,
    event_id: str,
    calendar_id: str = 'primary'
) -> Optional[GoogleCalendarEvent]:
    """
    Get a specific event by ID.

    Args:
        service: Calendar API service instance
        event_id: The ID of the event to retrieve
        calendar_id: Calendar identifier

    Returns:
        A GoogleCalendarEvent object, or None if an error occurs
    """
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return GoogleCalendarEvent(**event)
    except HttpError as error:
        logger.error(f"Error retrieving event '{event_id}': {error}")
        return None


# === ANALYSIS FUNCTIONS ===

def project_recurring_events(
    service: CalendarService,
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = 'primary',
    event_query: Optional[str] = None
) -> List[ProjectedEventOccurrence]:
    """
    Finds recurring events and projects their occurrences within a time window.

    Args:
        service: Calendar API service instance
        time_min: Start of the projection window
        time_max: End of the projection window
        calendar_id: The calendar to search within
        event_query: Optional text query to filter master recurring events

    Returns:
        A list of ProjectedEventOccurrence objects representing calculated occurrences
    """
    projected_occurrences: List[ProjectedEventOccurrence] = []

    logger.info(f"Starting projection of recurring events for calendar '{calendar_id}'")
    logger.info(f"Projection window: {time_min} to {time_max}. Query: '{event_query or 'None'}'")

    # Find master recurring events
    master_events_response = find_events(
        service=service,
        calendar_id=calendar_id,
        query=event_query,
        single_events=False,  # Get the master event definition
        show_deleted=False,
        max_results=2500
    )

    if not master_events_response or not master_events_response.items:
        logger.info("No master recurring events found matching the criteria.")
        return []

    logger.debug(f"Found {len(master_events_response.items)} potential master events.")

    # Process each master event
    for event in master_events_response.items:
        if not event.recurrence:
            continue

        if not event.start or not (event.start.dateTime or event.start.date):
            logger.warning(f"Skipping recurring event without start time: {event.summary} ({event.id})")
            continue

        # Determine the start datetime and duration
        dtstart_obj: Optional[datetime] = None
        event_duration: Optional[timedelta] = None

        if event.start.dateTime:
            try:
                dtstart_obj = date_parser.isoparse(event.start.dateTime)
                if event.end and event.end.dateTime:
                    dtend_obj = date_parser.isoparse(event.end.dateTime)
                    event_duration = dtend_obj - dtstart_obj
                else:
                    event_duration = timedelta(hours=1)
                    logger.warning(f"Recurring event '{event.summary}' missing end.dateTime, assuming {event_duration} duration.")
            except ValueError as e:
                logger.error(f"Could not parse dateTime for event {event.summary} ({event.id}): {e}")
                continue
        elif event.start.date:
            try:
                start_date = date_parser.parse(event.start.date).date()
                dtstart_obj = datetime.combine(start_date, datetime.min.time())
                if time_min.tzinfo:
                    dtstart_obj = dtstart_obj.replace(tzinfo=time_min.tzinfo)

                if event.end and event.end.date:
                    end_date = date_parser.parse(event.end.date).date()
                    event_duration = end_date - start_date
                else:
                    event_duration = timedelta(days=1)
            except ValueError as e:
                logger.error(f"Could not parse date for event {event.summary} ({event.id}): {e}")
                continue

        if not dtstart_obj or event_duration is None:
            logger.error(f"Could not determine dtstart or duration for event {event.summary} ({event.id})")
            continue

        # Extract RRULE
        rrule_str: Optional[str] = None
        exdate_strs: List[str] = []

        for rule_str in event.recurrence:
            if rule_str.startswith('RRULE:'):
                rrule_str = rule_str
            elif rule_str.startswith('EXDATE'):
                exdate_strs.append(rule_str)

        if not rrule_str:
            logger.warning(f"Recurring event '{event.summary}' ({event.id}) has no RRULE string. Skipping.")
            continue

        try:
            # Parse the recurrence rule
            ruleset = rrule.rruleset()
            main_rule = rrule.rrulestr(rrule_str, dtstart=dtstart_obj, forceset=True)
            ruleset.rrule(main_rule[0])

            # Add exception dates
            for exdate_str in exdate_strs:
                parts = exdate_str.split(':', 1)
                if len(parts) == 2:
                    param_str, dates_str = parts
                    dates = dates_str.split(',')
                    params = {}
                    if ';' in param_str:
                        param_parts = param_str.split(';')[1:]
                        for part in param_parts:
                            if '=' in part:
                                key, value = part.split('=', 1)
                                params[key.upper()] = value

                    is_all_day = params.get('VALUE') == 'DATE'

                    for date_str in dates:
                        try:
                            if is_all_day:
                                ex_date = date_parser.parse(date_str).date()
                                ex_dt = datetime.combine(ex_date, datetime.min.time())
                                if dtstart_obj.tzinfo:
                                    ex_dt = ex_dt.replace(tzinfo=dtstart_obj.tzinfo)
                            else:
                                ex_dt = date_parser.isoparse(date_str)

                            ruleset.exdate(ex_dt)
                        except ValueError:
                            logger.warning(f"Could not parse EXDATE value '{date_str}' for event {event.id}")

            # Generate occurrences within the window
            occurrences = ruleset.between(time_min, time_max, inc=True)

            logger.debug(f"Event '{event.summary}' ({event.id}): Found {len(occurrences)} occurrences via rrule.")

            for occ_start_dt in occurrences:
                # Ensure timezone consistency
                if dtstart_obj.tzinfo and occ_start_dt.tzinfo is None:
                    occ_start_dt = occ_start_dt.replace(tzinfo=dtstart_obj.tzinfo)
                elif not dtstart_obj.tzinfo and occ_start_dt.tzinfo:
                    occ_start_dt = occ_start_dt.replace(tzinfo=None)

                occ_end_dt = occ_start_dt + event_duration

                projected_occurrences.append(
                    ProjectedEventOccurrence(
                        original_event_id=event.id,
                        original_summary=event.summary or "No Summary",
                        occurrence_start=occ_start_dt,
                        occurrence_end=occ_end_dt
                    )
                )

        except Exception as e:
            logger.error(f"Failed to parse/process recurrence for event '{event.summary}' ({event.id}): {e}", exc_info=True)
            continue

    logger.info(f"Finished projection. Found {len(projected_occurrences)} total occurrences.")
    projected_occurrences.sort(key=lambda x: x.occurrence_start)
    return projected_occurrences


def analyze_busyness(
    service: CalendarService,
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = 'primary',
) -> Dict[date, Dict[str, Any]]:
    """
    Analyzes event count and total duration per day within a time window.

    Args:
        service: Calendar API service instance
        time_min: Start of the analysis window
        time_max: End of the analysis window
        calendar_id: The calendar to analyze

    Returns:
        A dictionary mapping each date within the window to its busyness stats
    """
    busyness_by_date: Dict[date, Dict[str, Any]] = defaultdict(lambda: {'event_count': 0, 'total_duration_minutes': 0.0})

    logger.info(f"Starting busyness analysis for calendar '{calendar_id}'")
    logger.info(f"Analysis window: {time_min} to {time_max}")

    # Find all event instances in the range
    events_response = find_events(
        service=service,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        single_events=True,
        show_deleted=False,
        max_results=2500
    )

    if not events_response or not events_response.items:
        logger.info("No events found in the specified time range for busyness analysis.")
        return dict(busyness_by_date)

    logger.debug(f"Found {len(events_response.items)} event instances for analysis.")

    # Process events and aggregate stats by date
    for event in events_response.items:
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None
        event_date: Optional[date] = None

        # Determine start and end datetimes/dates
        if event.start:
            if event.start.dateTime:
                try:
                    start_dt = date_parser.isoparse(event.start.dateTime)
                    event_date = start_dt.date()
                except ValueError:
                    logger.warning(f"Could not parse start dateTime: {event.start.dateTime}")
                    continue
            elif event.start.date:
                try:
                    event_date = date_parser.parse(event.start.date).date()
                except ValueError:
                    logger.warning(f"Could not parse start date: {event.start.date}")
                    continue

        if not event_date:
            logger.warning(f"Event '{event.summary}' ({event.id}) missing valid start information. Skipping.")
            continue

        # Ensure the event actually starts within our analysis window bounds
        if not (time_min.date() <= event_date < time_max.date()):
            continue

        # Increment event count for the date
        busyness_by_date[event_date]['event_count'] += 1

        # Calculate duration for non-all-day events
        if start_dt and event.end and event.end.dateTime:
            try:
                end_dt = date_parser.isoparse(event.end.dateTime)
                duration = end_dt - start_dt
                busyness_by_date[event_date]['total_duration_minutes'] += max(0, duration.total_seconds() / 60.0)
            except ValueError:
                logger.warning(f"Could not parse end dateTime: {event.end.dateTime} for event {event.id}")
            except TypeError:
                logger.warning(f"Could not calculate duration for event {event.id} (start: {start_dt}, end: {end_dt})")

    # Convert defaultdict back to regular dict and sort by date
    sorted_busyness = dict(sorted(busyness_by_date.items()))

    logger.info(f"Finished busyness analysis. Analyzed {len(sorted_busyness)} days.")
    return sorted_busyness


# === AVAILABILITY FUNCTIONS ===

def find_availability(
    service: CalendarService,
    time_min: datetime,
    time_max: datetime,
    calendar_ids: List[str]
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Finds free/busy information for a list of calendars.

    Args:
        service: Calendar API service instance
        time_min: Start of the time range
        time_max: End of the time range
        calendar_ids: A list of calendar identifiers to query

    Returns:
        A dictionary mapping each calendar ID to its free/busy information
    """
    if not calendar_ids:
        logger.warning("find_availability called with empty calendar_ids list.")
        return {}

    time_min_str = time_min.isoformat() + ('Z' if time_min.tzinfo is None else '')
    time_max_str = time_max.isoformat() + ('Z' if time_max.tzinfo is None else '')

    request_body = {
        "timeMin": time_min_str,
        "timeMax": time_max_str,
        "items": [{"id": cal_id} for cal_id in calendar_ids]
    }

    logger.info(f"Querying free/busy information for calendars: {calendar_ids} between {time_min_str} and {time_max_str}")

    try:
        freebusy_result = service.freebusy().query(body=request_body).execute()

        # Process the response
        processed_results: Dict[str, Dict[str, Any]] = {}
        calendars_data = freebusy_result.get('calendars', {})

        for cal_id, data in calendars_data.items():
            busy_intervals = []
            for interval in data.get('busy', []):
                try:
                    start_dt = date_parser.isoparse(interval.get('start'))
                    end_dt = date_parser.isoparse(interval.get('end'))
                    busy_intervals.append({'start': start_dt, 'end': end_dt})
                except (TypeError, ValueError) as parse_error:
                    logger.warning(f"Could not parse busy interval for {cal_id}: {interval}. Error: {parse_error}")

            processed_results[cal_id] = {
                'busy': busy_intervals,
                'errors': data.get('errors', [])
            }

        logger.info(f"Successfully retrieved free/busy information for {len(processed_results)} calendars.")
        return processed_results

    except HttpError as error:
        logger.error(f"An API error occurred during free/busy query: {error}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during free/busy query: {e}", exc_info=True)
        return None